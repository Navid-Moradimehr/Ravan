from __future__ import annotations

from pathlib import Path

from services.common.retrieval_index import RetrievalEvaluationCase, RetrievalIndex, evaluate_retrieval_index
from services.common.text_chunking import split_text_into_chunks


def test_split_text_into_chunks_uses_overlap():
    text = " ".join(f"token{i}" for i in range(1, 13))
    chunks = split_text_into_chunks(text, source_id="manual-1", chunk_size=5, overlap=2)

    assert len(chunks) >= 3
    assert chunks[0].chunk_id == "manual-1#0"
    assert chunks[0].end_token == 5
    assert chunks[1].start_token == 3


def test_retrieval_index_build_search_and_evaluate(tmp_path: Path):
    index_path = tmp_path / "index.jsonl"
    index = RetrievalIndex(index_path=index_path)

    documents = [
        {
            "doc_id": "manual-1",
            "source": "manuals",
            "title": "Pump troubleshooting manual",
            "text": "Motor vibration high alarm indicates bearing wear and overheating.",
            "payload": {"kind": "manual"},
            "tags": ["manual", "pump"],
        },
        {
            "doc_id": "note-2",
            "source": "notes",
            "title": "Maintenance note",
            "text": "Replace the pump coupling before the next shutdown.",
            "payload": {"kind": "note"},
            "tags": ["maintenance"],
        },
    ]

    indexed = index.build(documents)
    assert indexed
    assert index_path.exists()

    hits = index.search("motor vibration bearing alarm", limit=2)
    assert hits
    assert hits[0]["doc_id"] == "manual-1"

    result = evaluate_retrieval_index(
        index,
        [RetrievalEvaluationCase(query="motor vibration bearing alarm", expected_doc_ids=("manual-1",))],
        k=2,
    )
    assert result.total_cases == 1
    assert result.hit_rate_at_k == 1.0
    assert result.mean_reciprocal_rank == 1.0

