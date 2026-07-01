from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from services.analytics.reporting import report_engine
from services.assets.model import hierarchy_to_tree, load_hierarchy
from services.historian.client import query_alarms, query_recent_events, query_trend
from services.scenarios.engine import list_scenarios


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


def build_retrieval_documents(
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


def search_retrieval_corpus(
    query: str,
    *,
    table: str = "industrial_events",
    limit: int = 25,
    asset_config: Path | str = Path("config/assets.yaml"),
    max_results: int = 5,
) -> dict[str, Any]:
    documents = build_retrieval_documents(table=table, limit=limit, asset_config=asset_config)
    query_terms = _tokenize(query)
    hits: list[RetrievalHit] = []
    for document in documents:
        score = _score_document(query_terms, document)
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
            )
        )
    hits.sort(key=lambda hit: (-hit.score, hit.title.lower(), hit.doc_id))
    return {
        "query": query,
        "query_terms": query_terms,
        "result_count": len(hits[:max_results]),
        "documents_indexed": len(documents),
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
        "notes": [
            "This is a deterministic retrieval boundary, not a governed BI semantic layer.",
            "Use it for read-only context assembly and future agent tooling.",
        ],
    }

