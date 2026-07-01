from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Iterable


_TOKEN_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    source_id: str
    text: str
    index: int
    start_token: int
    end_token: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_text_into_chunks(
    text: str,
    *,
    source_id: str,
    chunk_size: int = 180,
    overlap: int = 30,
    metadata: dict[str, Any] | None = None,
) -> list[TextChunk]:
    tokens = _TOKEN_RE.findall(text.strip())
    if not tokens:
        return []

    chunk_size = max(chunk_size, 4)
    overlap = max(0, min(overlap, chunk_size - 1))
    step = max(1, chunk_size - overlap)
    chunks: list[TextChunk] = []
    index = 0
    start = 0
    while start < len(tokens):
        end = min(len(tokens), start + chunk_size)
        chunk_tokens = tokens[start:end]
        chunk_text = " ".join(chunk_tokens).strip()
        if chunk_text:
            chunks.append(
                TextChunk(
                    chunk_id=f"{source_id}#{index}",
                    source_id=source_id,
                    text=chunk_text,
                    index=index,
                    start_token=start,
                    end_token=end,
                    metadata=dict(metadata or {}),
                )
            )
        index += 1
        if end >= len(tokens):
            break
        start += step
    return chunks


def chunk_documents(
    documents: Iterable[dict[str, Any]],
    *,
    text_field: str = "text",
    source_field: str = "doc_id",
    chunk_size: int = 180,
    overlap: int = 30,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for document in documents:
        text = str(document.get(text_field, ""))
        source_id = str(document.get(source_field, "doc"))
        metadata = {k: v for k, v in document.items() if k not in {text_field}}
        chunks.extend(
            split_text_into_chunks(
                text,
                source_id=source_id,
                chunk_size=chunk_size,
                overlap=overlap,
                metadata=metadata,
            )
        )
    return chunks
