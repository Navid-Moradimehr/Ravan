from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from typing import Any

from services.analytics.reporting import report_engine
from services.common.cache import ttl_cache
from services.common.embeddings import build_embedding_client
from services.assets.model import hierarchy_to_tree, load_hierarchy
from services.historian.client import query_alarms, query_recent_events, query_trend
from services.scenarios.engine import list_scenarios
from services.common.retrieval_index import RetrievalEvaluationCase, RetrievalIndex, evaluate_retrieval_index


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class RetrievalDocument:
    doc_id: str
    source: str
    title: str
    text: str
    payload: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalHit:
    doc_id: str
    source: str
    title: str
    score: float
    snippet: str
    payload: dict[str, Any]
    tags: tuple[str, ...]
    signals: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in text.lower().replace("/", " ").replace("_", " ").replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if token and token not in STOPWORDS:
            tokens.append(token)
    return tokens


def _snippet(text: str, terms: list[str], width: int = 160) -> str:
    lower = text.lower()
    for term in terms:
        idx = lower.find(term)
        if idx >= 0:
            start = max(0, idx - width // 4)
            end = min(len(text), idx + width)
            return text[start:end].strip()
    return text[:width].strip()


@ttl_cache(ttl_seconds=15.0, max_size=32)
def _build_retrieval_documents_cached(
    *,
    table: str = "industrial_events",
    limit: int = 25,
    asset_config: Path | str = Path("config/assets.yaml"),
) -> list[RetrievalDocument]:
    documents: list[RetrievalDocument] = []

    for event in query_recent_events(table, limit):
        title = f"Event {event.get('event_id', event.get('time', 'unknown'))}"
        text = " ".join(
            str(part)
            for part in [
                event.get("time"),
                event.get("asset_id"),
                event.get("tag"),
                event.get("value"),
                event.get("severity"),
                event.get("quality"),
                event.get("fault_type"),
                event.get("evaluation"),
            ]
            if part is not None
        )
        documents.append(
            RetrievalDocument(
                doc_id=f"event:{event.get('event_id', event.get('time', 'unknown'))}",
                source="historian.events",
                title=title,
                text=text,
                payload=event,
                tags=("historian", "event"),
            )
        )

    for alarm in query_alarms(limit):
        text = " ".join(
            str(part)
            for part in [
                alarm.get("time"),
                alarm.get("asset_id"),
                alarm.get("tag"),
                alarm.get("severity"),
                alarm.get("message"),
            ]
            if part is not None
        )
        documents.append(
            RetrievalDocument(
                doc_id=f"alarm:{alarm.get('asset_id', 'unknown')}:{alarm.get('tag', 'unknown')}:{alarm.get('time', 'unknown')}",
                source="historian.alarms",
                title=f"Alarm {alarm.get('asset_id', 'unknown')}.{alarm.get('tag', 'unknown')}",
                text=text,
                payload=alarm,
                tags=("historian", "alarm"),
            )
        )

    try:
        assets = hierarchy_to_tree(load_hierarchy(asset_config))
    except Exception:
        assets = []
    for item in assets:
        text = " ".join(
            str(part)
            for part in [
                item.get("id"),
                item.get("name"),
                item.get("type"),
                item.get("path"),
                item.get("parent_id"),
            ]
            if part is not None
        )
        documents.append(
            RetrievalDocument(
                doc_id=f"asset:{item.get('id', 'unknown')}",
                source="assets.hierarchy",
                title=str(item.get("name", item.get("id", "asset"))),
                text=text,
                payload=item,
                tags=("assets", "hierarchy"),
            )
        )

    for template in report_engine.list_templates():
        text = " ".join(
            str(part)
            for part in [
                template.get("template_id"),
                template.get("name"),
                template.get("description"),
                template.get("format"),
            ]
            if part is not None
        )
        documents.append(
            RetrievalDocument(
                doc_id=f"report:{template.get('template_id', 'unknown')}",
                source="reports.templates",
                title=str(template.get("name", template.get("template_id", "report"))),
                text=text,
                payload=template,
                tags=("reports", "template"),
            )
        )

    for scenario in list_scenarios():
        text = " ".join(
            str(part)
            for part in [
                scenario.get("scenario_id"),
                scenario.get("name"),
                scenario.get("description"),
                scenario.get("category"),
            ]
            if part is not None
        )
        documents.append(
            RetrievalDocument(
                doc_id=f"scenario:{scenario.get('scenario_id', 'unknown')}",
                source="scenarios",
                title=str(scenario.get("name", scenario.get("scenario_id", "scenario"))),
                text=text,
                payload=scenario,
                tags=("simulation", "scenario"),
            )
        )

    return documents


def build_retrieval_documents(
    *,
    table: str = "industrial_events",
    limit: int = 25,
    asset_config: Path | str = Path("config/assets.yaml"),
) -> list[RetrievalDocument]:
    return _build_retrieval_documents_cached(table=table, limit=limit, asset_config=str(asset_config))


def _score_document(query_terms: list[str], document: RetrievalDocument) -> float:
    doc_tokens = _tokenize(document.text)
    if not doc_tokens or not query_terms:
        return 0.0
    score = 0.0
    token_counts = {token: doc_tokens.count(token) for token in set(doc_tokens)}
    for term in query_terms:
        if term in token_counts:
            score += 2.0 + token_counts[term] * 0.25
        else:
            for token in token_counts:
                if term in token or token in term:
                    score += 0.5
                    break
    if document.source.startswith("historian"):
        score += 0.2
    return round(score, 4)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(length))
    left_norm = math.sqrt(sum(value * value for value in left[:length]))
    right_norm = math.sqrt(sum(value * value for value in right[:length]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _phrase_score(query: str, document: RetrievalDocument) -> float:
    query_text = " ".join(_tokenize(query))
    if not query_text:
        return 0.0
    lowered = document.text.lower()
    if query_text in lowered:
        return 1.0
    parts = query_text.split()
    if len(parts) > 2 and all(part in lowered for part in parts[: min(3, len(parts))]):
        return 0.5
    return 0.0


def _hybrid_score(query: str, query_terms: list[str], document: RetrievalDocument, query_embedding: list[float], doc_embedding: list[float]) -> tuple[float, dict[str, float]]:
    token_score = _score_document(query_terms, document)
    phrase_score = _phrase_score(query, document)
    semantic_score = _cosine_similarity(query_embedding, doc_embedding)
    source_boost = 0.0
    if document.source.startswith("historian"):
        source_boost += 0.1
    if document.source.startswith("assets") and any(term in {"asset", "assets", "equipment"} for term in query_terms):
        source_boost += 0.1
    hybrid = round((token_score * 0.45) + (phrase_score * 0.15) + (semantic_score * 0.35) + source_boost, 4)
    return hybrid, {
        "token": round(token_score, 4),
        "phrase": round(phrase_score, 4),
        "semantic": round(semantic_score, 4),
        "source_boost": round(source_boost, 4),
    }


def search_retrieval_corpus(
    query: str,
    *,
    table: str = "industrial_events",
    limit: int = 25,
    asset_config: Path | str = Path("config/assets.yaml"),
    max_results: int = 5,
    use_embeddings: bool = True,
) -> dict[str, Any]:
    documents = build_retrieval_documents(table=table, limit=limit, asset_config=asset_config)
    query_terms = _tokenize(query)
    client = build_embedding_client()
    query_embedding = client.embed_text(query) if use_embeddings else []
    document_embeddings = client.embed_texts([document.text for document in documents]) if use_embeddings else [[] for _ in documents]
    hits: list[RetrievalHit] = []
    for document, doc_embedding in zip(documents, document_embeddings):
        score, signals = _hybrid_score(query, query_terms, document, query_embedding, doc_embedding)
        if score <= 0:
            continue
        hits.append(
            RetrievalHit(
                doc_id=document.doc_id,
                source=document.source,
                title=document.title,
                score=score,
                snippet=_snippet(document.text, query_terms),
                payload=document.payload,
                tags=document.tags,
                signals=signals,
            )
        )
    hits.sort(key=lambda hit: (-hit.score, hit.title.lower(), hit.doc_id))
    return {
        "query": query,
        "query_terms": query_terms,
        "backend": client.backend_info().to_dict(),
        "result_count": len(hits[:max_results]),
        "documents_indexed": len(documents),
        "mode": "hybrid" if use_embeddings else "token",
        "hits": [hit.to_dict() for hit in hits[:max_results]],
    }


def build_retrieval_catalog(*, asset_config: Path | str = Path("config/assets.yaml")) -> dict[str, Any]:
    try:
        assets = hierarchy_to_tree(load_hierarchy(asset_config))
    except Exception:
        assets = []

    return {
        "sources": [
            {
                "name": "historian.events",
                "kind": "time_series",
                "description": "Recent historian events and measurements",
                "read_only": True,
            },
            {
                "name": "historian.alarms",
                "kind": "alerts",
                "description": "Recent warnings and critical alarms",
                "read_only": True,
            },
            {
                "name": "assets.hierarchy",
                "kind": "metadata",
                "description": "Configured site/line/asset hierarchy",
                "read_only": True,
            },
            {
                "name": "reports.templates",
                "kind": "documents",
                "description": "Saved report templates and schedules",
                "read_only": True,
            },
            {
                "name": "scenarios",
                "kind": "simulation",
                "description": "Available industrial simulation scenarios",
                "read_only": True,
            },
        ],
        "asset_nodes": len(assets),
        "search_modes": ["token", "hybrid", "semantic"],
        "embedding_backend": build_embedding_client().backend_info().to_dict(),
        "notes": [
            "This is a deterministic retrieval boundary, not a governed BI semantic layer.",
            "Hybrid search combines token overlap, phrase match, and embeddings when available.",
            "Persistent chunked indexing is available for long manuals and notes.",
            "Use it for read-only context assembly and future agent tooling.",
        ],
    }


def build_persistent_retrieval_index(
    *,
    index_path: Path | str = Path("data/retrieval/index.jsonl"),
    table: str = "industrial_events",
    limit: int = 25,
    asset_config: Path | str = Path("config/assets.yaml"),
    overwrite: bool = True,
) -> dict[str, Any]:
    documents = [
        document.to_dict()
        for document in build_retrieval_documents(table=table, limit=limit, asset_config=asset_config)
    ]
    index = RetrievalIndex(index_path=index_path)
    indexed = index.rebuild_from_retrieval_documents(documents, overwrite=overwrite)
    return {
        "index_path": str(Path(index_path)),
        "documents_indexed": len(indexed),
        "chunks_indexed": len(indexed),
        "embedding_backend": index.client.backend_info().to_dict(),
    }


def evaluate_persistent_retrieval_index(
    *,
    cases: list[RetrievalEvaluationCase],
    index_path: Path | str = Path("data/retrieval/index.jsonl"),
    limit: int = 25,
    asset_config: Path | str = Path("config/assets.yaml"),
) -> dict[str, Any]:
    index = RetrievalIndex(index_path=index_path)
    if not index.load():
        build_persistent_retrieval_index(index_path=index_path, limit=limit, asset_config=asset_config)
    result = evaluate_retrieval_index(index, cases)
    return result.to_dict()
