from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


AI_EVENT_VERSION = 1
AI_SUMMARY_EVENT_TYPE = "ai.summary.generated"
AI_PREDICTION_EVENT_TYPE = "ai.prediction.generated"
AI_RECOMMENDATION_EVENT_TYPE = "ai.recommendation.generated"
DEFAULT_AI_TOPIC = "iot.ai_enriched"
DEFAULT_AI_PROMPT_TEMPLATE_ID = "industrial-summary-v1"


@dataclass(frozen=True)
class AIEventContract:
    event_type: str
    event_version: int
    topic: str
    category: str
    description: str
    model_role: str
    prompt_template_id: str
    required_fields: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


AI_EVENT_CONTRACTS: tuple[AIEventContract, ...] = (
    AIEventContract(
        event_type=AI_SUMMARY_EVENT_TYPE,
        event_version=AI_EVENT_VERSION,
        topic=DEFAULT_AI_TOPIC,
        category="ai",
        description="Versioned AI summary event emitted by the AI gateway for downstream consumers.",
        model_role="summarization",
        prompt_template_id=DEFAULT_AI_PROMPT_TEMPLATE_ID,
        required_fields=(
            "event_id",
            "event_type",
            "event_version",
            "generated_at",
            "model_id",
            "model_version",
            "prompt_template_id",
            "prompt_version",
            "source_event_ids",
            "summary",
        ),
    ),
    AIEventContract(
        event_type=AI_PREDICTION_EVENT_TYPE,
        event_version=AI_EVENT_VERSION,
        topic=DEFAULT_AI_TOPIC,
        category="ai",
        description="Versioned AI prediction event reserved for future forecasting outputs.",
        model_role="prediction",
        prompt_template_id=DEFAULT_AI_PROMPT_TEMPLATE_ID,
        required_fields=(
            "event_id",
            "event_type",
            "event_version",
            "generated_at",
            "model_id",
            "model_version",
            "prompt_template_id",
            "prompt_version",
            "source_event_ids",
            "predictions",
        ),
    ),
    AIEventContract(
        event_type=AI_RECOMMENDATION_EVENT_TYPE,
        event_version=AI_EVENT_VERSION,
        topic=DEFAULT_AI_TOPIC,
        category="ai",
        description="Versioned AI recommendation event reserved for future supervised-assist outputs.",
        model_role="recommendation",
        prompt_template_id=DEFAULT_AI_PROMPT_TEMPLATE_ID,
        required_fields=(
            "event_id",
            "event_type",
            "event_version",
            "generated_at",
            "model_id",
            "model_version",
            "prompt_template_id",
            "prompt_version",
            "source_event_ids",
            "recommendations",
        ),
    ),
)


def _collect_source_event_ids(batch: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for index, event in enumerate(batch):
        value = event.get("event_id")
        if value:
            ids.append(str(value))
            continue
        fallback = event.get("source_event_id") or event.get("id")
        if fallback:
            ids.append(str(fallback))
            continue
        ids.append(f"batch-{index}")
    return ids


def build_ai_summary_event(
    batch: list[dict[str, Any]],
    *,
    summary: str,
    provider: str,
    model_id: str,
    endpoint: str,
    prompt_template_id: str = DEFAULT_AI_PROMPT_TEMPLATE_ID,
    prompt_version: str = "1.0.0",
    used_fallback: bool = False,
    latency_seconds: float | None = None,
    report_id: str | None = None,
    report_type: str = "scheduled",
    trigger_reason: str = "interval",
    policy_snapshot: dict[str, Any] | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any]:
    source_event_ids = _collect_source_event_ids(batch)
    source_sites = sorted({str(event.get("site_id", "")) for event in batch if event.get("site_id")})
    source_assets = sorted({str(event.get("asset_id", "")) for event in batch if event.get("asset_id")})
    source_topics = sorted({str(event.get("topic", "")) for event in batch if event.get("topic")})
    severity_counts = {
        severity: sum(1 for event in batch if event.get("severity") == severity)
        for severity in ("normal", "warning", "critical")
    }

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": AI_SUMMARY_EVENT_TYPE,
        "event_version": AI_EVENT_VERSION,
        "topic": DEFAULT_AI_TOPIC,
        "category": "ai",
        "source": "ai-gateway",
        "provider": provider,
        "model": model_id,
        "model_id": model_id,
        "model_version": model_id,
        "endpoint": endpoint,
        "prompt_template_id": prompt_template_id,
        "prompt_version": prompt_version,
        "batch_size": len(batch),
        "source_event_count": len(source_event_ids),
        "source_event_ids": source_event_ids,
        "source_site_ids": source_sites,
        "source_asset_ids": source_assets,
        "source_topics": source_topics,
        "summary": summary,
        "events": batch,
        "severity_counts": severity_counts,
        "latency_seconds": round(latency_seconds, 3) if latency_seconds is not None else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "used_fallback": used_fallback,
        "report_id": report_id,
        "report_type": report_type,
        "trigger_reason": trigger_reason,
        "policy_snapshot": policy_snapshot,
        "window_start": window_start,
        "window_end": window_end,
    }
    return event
