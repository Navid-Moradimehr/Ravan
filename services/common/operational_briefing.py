from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class BriefingIssue(BaseModel):
    issue_id: str
    status: Literal["new", "ongoing", "worsening", "resolved"] = "new"
    severity: Literal["normal", "warning", "critical", "unknown"] = "unknown"
    asset_id: str = "unknown"
    tag: str = "unknown"
    observation: str
    evidence_event_ids: list[str] = Field(default_factory=list, max_length=20)


class OperationalBriefing(BaseModel):
    schema_version: str = "operational-briefing.v1"
    headline: str
    situation_status: Literal["normal", "attention", "critical", "recovering", "unknown"]
    executive_summary: str
    key_updates: list[str] = Field(default_factory=list, max_length=8)
    active_issues: list[BriefingIssue] = Field(default_factory=list, max_length=12)
    resolved_issues: list[BriefingIssue] = Field(default_factory=list, max_length=12)
    affected_assets: list[str] = Field(default_factory=list, max_length=20)
    recommended_checks: list[str] = Field(default_factory=list, max_length=8)
    evidence_references: list[str] = Field(default_factory=list, max_length=30)
    data_gaps: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    continuity: dict[str, Any] = Field(default_factory=dict)
    confidence: Literal["low", "medium", "high"] = "medium"


def briefing_json_schema() -> dict[str, Any]:
    return OperationalBriefing.model_json_schema()


def build_briefing_context(
    events: list[dict[str, Any]],
    *,
    report_type: str,
    site_id: str,
    previous_reports: list[dict[str, Any]] | None = None,
    max_events: int = 100,
    memory_hours: int = 24,
) -> dict[str, Any]:
    selected = select_report_evidence(events, max_events=max_events)
    severity_counts = Counter(str(event.get("severity") or "unknown").lower() for event in selected)
    asset_counts = Counter(str(event.get("asset_id") or event.get("device_id") or "unknown") for event in selected)
    tags_by_asset: dict[str, set[str]] = defaultdict(set)
    for event in selected:
        asset = str(event.get("asset_id") or event.get("device_id") or "unknown")
        tags_by_asset[asset].add(str(event.get("tag") or "unknown"))

    memory = compact_report_memory(previous_reports or [], max_age_hours=memory_hours)
    return {
        "scope": {
            "site_id": site_id,
            "report_type": report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "current": {
            "event_count": len(selected),
            "severity_counts": dict(severity_counts),
            "affected_assets": [asset for asset, _count in asset_counts.most_common(20)],
            "tags_by_asset": {key: sorted(value)[:20] for key, value in list(tags_by_asset.items())[:20]},
            "events": [_compact_event(event) for event in selected],
        },
        "short_memory": memory,
        "instructions": {
            "focus": "Broadcast the current operational situation and changes since the previous briefing.",
            "avoid": "Do not invent causes, values, trends, or plant actions. Do not perform long-term trend analysis.",
            "quiet_periods": "If evidence is normal, report that operations appear normal and identify any data gaps.",
        },
    }


def select_report_evidence(events: list[dict[str, Any]], *, max_events: int = 100) -> list[dict[str, Any]]:
    """Select bounded evidence by severity, recency, and stream coverage."""
    max_events = max(1, max_events)
    ranked = sorted(
        [event for event in events if isinstance(event, dict)],
        key=lambda event: (
            {"critical": 3, "warning": 2, "normal": 1}.get(str(event.get("severity") or "").lower(), 0),
            str(event.get("processed_at") or event.get("ts_event") or event.get("time") or ""),
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen_streams: set[tuple[str, str]] = set()
    for event in ranked:
        stream = (str(event.get("asset_id") or event.get("device_id") or "unknown"), str(event.get("tag") or "unknown"))
        if stream not in seen_streams:
            selected.append(event)
            seen_streams.add(stream)
        if len(selected) >= max_events:
            return selected
    selected_ids = {id(event) for event in selected}
    selected.extend(event for event in ranked if id(event) not in selected_ids and len(selected) < max_events)
    return selected


def compact_report_memory(reports: list[dict[str, Any]], *, limit: int = 6, max_age_hours: int = 24) -> list[dict[str, Any]]:
    memory: list[dict[str, Any]] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, max_age_hours))
    for report in reports[: max(1, limit)]:
        timestamp = report.get("updated_at") or report.get("created_at")
        if timestamp:
            try:
                parsed = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed < cutoff:
                    continue
            except (TypeError, ValueError):
                pass
        result = report.get("result") if isinstance(report.get("result"), dict) else {}
        briefing = result.get("briefing") if isinstance(result.get("briefing"), dict) else result
        if not isinstance(briefing, dict) or not briefing:
            continue
        memory.append(
            {
                "report_id": str(report.get("job_id") or ""),
                "generated_at": str(timestamp or ""),
                "report_type": str(report.get("report_type") or ""),
                "situation_status": str(briefing.get("situation_status") or "unknown"),
                "headline": str(briefing.get("headline") or "")[:240],
                "active_issue_ids": [
                    str(issue.get("issue_id")) for issue in briefing.get("active_issues", [])
                    if isinstance(issue, dict) and issue.get("issue_id")
                ][:20],
                "affected_assets": [str(value) for value in briefing.get("affected_assets", [])][:20],
            }
        )
    return memory


def build_briefing_prompt(context: dict[str, Any]) -> str:
    current = context.get("current", {})
    severity_counts = current.get("severity_counts", {})
    event_count = int(current.get("event_count", 0) or 0)
    critical = int(severity_counts.get("critical", 0) or 0)
    warning = int(severity_counts.get("warning", 0) or 0)
    return (
        "Create one concise operational briefing as JSON matching the supplied schema. "
        "Use only the evidence and short memory. Classify issue continuity as new, ongoing, "
        "worsening, or resolved. Recommended checks must remain read-only. "
        "Write plain English with normal ASCII punctuation. Do not use fancy dashes, ellipses, or line breaks. "
        "Keep the headline short and the executive summary to 1-2 short sentences.\n"
        f"If critical and warning counts are both zero, set headline exactly 'Operations appear normal' and "
        f"executive_summary exactly 'Observed {event_count} bounded events: {critical} critical and {warning} warning.'\n\n"
        f"CONTEXT_JSON={json.dumps(context, separators=(',', ':'), default=str)}"
    )


def validate_briefing(content: str | dict[str, Any]) -> tuple[bool, list[str], dict[str, Any] | None]:
    try:
        payload = content if isinstance(content, dict) else json.loads(content)
        briefing = OperationalBriefing.model_validate(payload)
    except Exception as exc:
        return False, [str(exc)], None
    return True, [], _normalize_briefing(briefing.model_dump(mode="json"))


def deterministic_briefing(context: dict[str, Any], reason: str) -> dict[str, Any]:
    current = context.get("current", {})
    counts = current.get("severity_counts", {})
    critical = int(counts.get("critical", 0) or 0)
    warning = int(counts.get("warning", 0) or 0)
    status = "critical" if critical else "attention" if warning else "normal"
    assets = [str(value) for value in current.get("affected_assets", [])]
    headline = "Critical conditions require attention" if critical else "Conditions require attention" if warning else "Operations appear normal"
    return OperationalBriefing(
        headline=headline,
        situation_status=status,
        executive_summary=f"Observed {current.get('event_count', 0)} bounded events: {critical} critical and {warning} warning.",
        key_updates=[f"Critical events: {critical}", f"Warning events: {warning}"],
        affected_assets=assets,
        recommended_checks=["Review the referenced events and verify affected asset readings"] if critical or warning else [],
        evidence_references=[str(event.get("event_id")) for event in current.get("events", []) if event.get("event_id")][:30],
        limitations=[f"Deterministic fallback used: {reason}"],
        confidence="medium" if current.get("event_count") else "low",
    ).model_dump(mode="json")


def _normalize_briefing(briefing: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(briefing)
    cleaned["headline"] = _normalize_text(str(cleaned.get("headline") or ""))
    cleaned["executive_summary"] = _normalize_text(str(cleaned.get("executive_summary") or ""))
    cleaned["limitations"] = _normalize_text_list(cleaned.get("limitations", []))
    cleaned["data_gaps"] = _normalize_text_list(cleaned.get("data_gaps", []))
    cleaned["recommended_checks"] = _normalize_text_list(cleaned.get("recommended_checks", []))
    cleaned["key_updates"] = _normalize_text_list(cleaned.get("key_updates", []))
    cleaned["affected_assets"] = _normalize_text_list(cleaned.get("affected_assets", []))
    cleaned["evidence_references"] = _normalize_identifier_list(cleaned.get("evidence_references", []))
    cleaned["active_issues"] = [_normalize_issue(issue) for issue in cleaned.get("active_issues", []) if isinstance(issue, dict)]
    cleaned["resolved_issues"] = [_normalize_issue(issue) for issue in cleaned.get("resolved_issues", []) if isinstance(issue, dict)]
    return cleaned


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(issue)
    cleaned["issue_id"] = _normalize_text(str(cleaned.get("issue_id") or ""))
    cleaned["asset_id"] = _normalize_text(str(cleaned.get("asset_id") or ""))
    cleaned["tag"] = _normalize_text(str(cleaned.get("tag") or ""))
    cleaned["observation"] = _normalize_text(str(cleaned.get("observation") or ""))
    cleaned["evidence_event_ids"] = [_normalize_text(str(item)) for item in cleaned.get("evidence_event_ids", []) if str(item).strip()]
    return cleaned


def _normalize_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2028", " ").replace("\u2029", " ")
    value = value.replace("\u2010", "-").replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    value = value.replace("\u2026", "...")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _normalize_text_list(items: list[Any]) -> list[str]:
    reserved = {
        "headline",
        "situation_status",
        "executive_summary",
        "recommended_checks",
        "data_gaps",
        "limitations",
        "key_updates",
        "affected_assets",
        "active_issues",
        "resolved_issues",
        "report_id",
        "generated_at",
        "confidence",
        "evidence_references",
    }
    normalized: list[str] = []
    for item in items:
        text = _normalize_text(str(item))
        lower = text.lower()
        if not text:
            continue
        if lower in reserved:
            continue
        if text in {"{", "}", "[]", "[", "]"}:
            continue
        if len(text) < 8 and " " not in text:
            continue
        normalized.append(text)
    return normalized


def _normalize_identifier_list(items: list[Any]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "event_id", "site_id", "asset_id", "device_id", "tag", "value", "unit",
        "severity", "anomaly_score", "threshold_status", "triggered_rules",
        "processed_at", "ts_event", "time", "quality",
    )
    return {key: event.get(key) for key in keys if event.get(key) is not None}
