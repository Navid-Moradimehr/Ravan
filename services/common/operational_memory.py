from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.analytics.reporting import report_engine
from services.analytics.oee_engine import oee_engine
from services.api_service.alert_manager import alert_manager
from services.api_service.collaboration import collaboration_store
from services.historian.backup import get_walg_status


@dataclass(frozen=True)
class OperationalMemorySection:
    name: str
    description: str
    status: str
    sources: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_operational_memory_snapshot(*, shifts_per_day: int = 3) -> dict[str, Any]:
    """Build a read-only snapshot of operational memory surfaces.

    This intentionally reuses existing operational features instead of
    introducing a new persistence or workflow service.
    """

    now = datetime.now(timezone.utc)
    shifts = oee_engine.generate_shifts(now, shifts_per_day=shifts_per_day)

    sections = (
        OperationalMemorySection(
            name="Alerts and incidents",
            description="Alert lifecycle, acknowledgement history, and incident state.",
            status="implemented",
            sources=("alert_manager", "audit_log"),
        ),
        OperationalMemorySection(
            name="Operator collaboration",
            description="Annotations, shared notes, and ad-hoc operational comments.",
            status="implemented",
            sources=("collaboration_store",),
        ),
        OperationalMemorySection(
            name="Shifts and production context",
            description="Shift windows used for OEE and operational rollups.",
            status="implemented",
            sources=("oee_engine",),
        ),
        OperationalMemorySection(
            name="Reports and exports",
            description="Report templates and generated operational reports.",
            status="implemented",
            sources=("report_engine",),
        ),
        OperationalMemorySection(
            name="Backups and restore readiness",
            description="Historian backup status and restore surfaces.",
            status="implemented",
            sources=("historian.backup",),
        ),
    )

    return {
        "generated_at": now.isoformat(),
        "plane": "operational-memory",
        "sections": [section.to_dict() for section in sections],
        "alerts": {
            "statistics": alert_manager.get_statistics(),
            "recent": alert_manager.list_alerts(limit=10),
        },
        "annotations": collaboration_store.list_annotations(limit=10),
        "shifts": [shift.__dict__ for shift in shifts],
        "reports": {
            "templates": report_engine.list_templates(),
            "generated": report_engine.list_generated_reports(),
        },
        "backups": {
            "status": get_walg_status(),
        },
        "contracts": {
            "read_only": True,
            "operational_memory_is_logical": True,
            "current_release_scope": [
                "alerts",
                "annotations",
                "shifts",
                "reports",
                "backups",
            ],
            "not_yet_native": [
                "work_orders",
                "approvals",
                "incident_command",
                "recipe_state",
                "maintenance_plans",
            ],
        },
        "notes": [
            "This is the operational memory boundary, not a full MES replacement.",
            "Work orders, approvals, and maintenance plans remain user-owned until a later phase.",
            "The snapshot is intentionally read-only so it can evolve without changing ingest or historian behavior.",
        ],
    }
