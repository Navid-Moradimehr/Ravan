from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from services.common.embeddings import build_embedding_client
from services.common.text_chunking import TextChunk, chunk_documents


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    doc_id: str
    source: str
    title: str
    text: str
    vector: tuple[float, ...]
    tags: tuple[str, ...] = field(default_factory=tuple)
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    query: str
    expected_doc_ids: tuple[str, ...]
    relevant_sources: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    total_cases: int
    hit_rate_at_k: float
    mean_reciprocal_rank: float
    average_precision_at_k: float
    average_latency_ms: float
    evaluated_at: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetrievalIndex:
    """File-backed retrieval index with provider-neutral embeddings."""

    def __init__(
        self,
        index_path: Path | str = Path("data/retrieval/index.jsonl"),
        *,
        client: Any | None = None,
    ):
        self.index_path = Path(index_path)
        self.client = client or build_embedding_client()

    def clear(self) -> None:
        if self.index_path.exists():
            self.index_path.unlink()

    def build(self, documents: Iterable[dict[str, Any]], *, overwrite: bool = True) -> list[IndexedChunk]:
        if overwrite:
            self.clear()

        chunks = chunk_documents(documents)
        if not chunks:
            self._write([])
            return []

        vectors = self.client.embed_texts([chunk.text for chunk in chunks])
        indexed = [
            IndexedChunk(
                chunk_id=chunk.chunk_id,
                doc_id=str(chunk.metadata.get("doc_id", chunk.source_id)),
                source=str(chunk.metadata.get("source", chunk.metadata.get("source_id", "unknown"))),
                title=str(chunk.metadata.get("title", chunk.metadata.get("name", chunk.source_id))),
                text=chunk.text,
                vector=tuple(vectors[idx]),
                tags=tuple(str(tag) for tag in chunk.metadata.get("tags", []) if tag),
                payload=dict(chunk.metadata.get("payload", {})) if isinstance(chunk.metadata.get("payload"), dict) else {},
                metadata={
                    "chunk_index": chunk.index,
                    "start_token": chunk.start_token,
                    "end_token": chunk.end_token,
                },
            )
            for idx, chunk in enumerate(chunks)
        ]
        self._write(indexed)
        return indexed

    def load(self) -> list[IndexedChunk]:
        if not self.index_path.exists():
            return []
        stat = self.index_path.stat()
        return list(self._load_cached(str(self.index_path), stat.st_mtime_ns))

    @staticmethod
    @lru_cache(maxsize=8)
    def _load_cached(path: str, mtime_ns: int) -> tuple[IndexedChunk, ...]:
        rows: list[IndexedChunk] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            rows.append(
                IndexedChunk(
                    chunk_id=str(data["chunk_id"]),
                    doc_id=str(data["doc_id"]),
                    source=str(data["source"]),
                    title=str(data["title"]),
                    text=str(data["text"]),
                    vector=tuple(float(v) for v in data.get("vector", [])),
                    tags=tuple(str(tag) for tag in data.get("tags", [])),
                    payload=dict(data.get("payload", {})),
                    metadata=dict(data.get("metadata", {})),
                )
            )
        return tuple(rows)

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        records = self.load()
        if not records:
            return []
        query_vector = self.client.embed_text(query)
        scored: list[dict[str, Any]] = []
        for record in records:
            score = self._cosine_similarity(query_vector, list(record.vector))
            if score <= 0:
                continue
            scored.append(
                {
                    "chunk_id": record.chunk_id,
                    "doc_id": record.doc_id,
                    "source": record.source,
                    "title": record.title,
                    "text": record.text,
                    "score": round(score, 6),
                    "tags": list(record.tags),
                    "payload": record.payload,
                    "metadata": record.metadata,
                }
            )
        scored.sort(key=lambda item: (-item["score"], item["title"], item["chunk_id"]))
        return scored[:limit]

    def rebuild_from_retrieval_documents(self, documents: Iterable[dict[str, Any]], *, overwrite: bool = True) -> list[IndexedChunk]:
        return self.build(documents, overwrite=overwrite)

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        length = min(len(left), len(right))
        dot = sum(left[i] * right[i] for i in range(length))
        left_norm = sum(left[i] * left[i] for i in range(length)) ** 0.5
        right_norm = sum(right[i] * right[i] for i in range(length)) ** 0.5
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _write(self, rows: Iterable[IndexedChunk]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row.to_dict(), ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
        self._load_cached.cache_clear()


def evaluate_retrieval_index(
    index: RetrievalIndex,
    cases: Iterable[RetrievalEvaluationCase],
    *,
    k: int = 5,
) -> RetrievalEvaluationResult:
    import time
    from datetime import datetime, timezone

    cases_list = list(cases)
    if not cases_list:
        return RetrievalEvaluationResult(
            total_cases=0,
            hit_rate_at_k=0.0,
            mean_reciprocal_rank=0.0,
            average_precision_at_k=0.0,
            average_latency_ms=0.0,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            notes=("no evaluation cases provided",),
        )

    hits = 0
    reciprocal_ranks: list[float] = []
    average_precisions: list[float] = []
    latencies: list[float] = []

    for case in cases_list:
        start = time.perf_counter()
        results = index.search(case.query, limit=k)
        latencies.append((time.perf_counter() - start) * 1000.0)
        ranked_ids = [item["doc_id"] for item in results]
        expected = set(case.expected_doc_ids)
        hit_positions = [idx + 1 for idx, doc_id in enumerate(ranked_ids) if doc_id in expected]
        if hit_positions:
            hits += 1
            reciprocal_ranks.append(1.0 / hit_positions[0])
        else:
            reciprocal_ranks.append(0.0)

        precision_acc = 0.0
        relevant_hits = 0
        for idx, doc_id in enumerate(ranked_ids, start=1):
            if doc_id in expected:
                relevant_hits += 1
                precision_acc += relevant_hits / idx
        denominator = min(len(expected), k) or 1
        average_precisions.append(precision_acc / denominator)

    return RetrievalEvaluationResult(
        total_cases=len(cases_list),
        hit_rate_at_k=round(hits / len(cases_list), 4),
        mean_reciprocal_rank=round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
        average_precision_at_k=round(sum(average_precisions) / len(average_precisions), 4),
        average_latency_ms=round(sum(latencies) / len(latencies), 4),
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        notes=("file-backed retrieval index",),
    )
