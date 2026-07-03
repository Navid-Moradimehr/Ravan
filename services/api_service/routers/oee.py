from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter


router = APIRouter(tags=["oee"])


@router.get("/api/v1/oee/shifts")
async def list_shifts(date: str | None = None) -> list[dict[str, Any]]:
    from services.analytics.oee_engine import oee_engine

    dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    return [shift.__dict__ for shift in oee_engine.generate_shifts(dt)]


@router.post("/api/v1/oee/calculate")
async def calculate_oee(req: dict[str, Any]) -> dict[str, Any]:
    from services.analytics.oee_engine import ShiftPeriod, oee_engine

    shift = ShiftPeriod(
        shift_id=req.get("shift_id", "unknown"),
        start=datetime.now(),
        end=datetime.now(),
        planned_production_time_minutes=req.get("planned_minutes", 480.0),
    )
    result = oee_engine.calculate(
        shift,
        runtime_minutes=req.get("runtime_minutes", 0.0),
        total_count=req.get("total_count", 0),
        good_count=req.get("good_count", 0),
    )
    return result.to_dict()
