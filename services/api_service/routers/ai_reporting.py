from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.common.ai_reporting import (
    AIReportingPolicy,
    create_report_job,
    get_policy,
    get_latest_report,
    get_report_job,
    list_report_jobs,
    reporting_status,
    save_policy,
)


class ReportGenerateRequest(BaseModel):
    site_id: str = Field(default="*", min_length=1)
    report_type: str = Field(default="scheduled", pattern="^(scheduled|anomaly|manual)$")
    trigger_reason: str = Field(default="manual", min_length=1, max_length=120)
    window_start: datetime | None = None
    window_end: datetime | None = None


router = APIRouter(prefix="/api/v1/ai", tags=["ai-reporting"])


@router.get("/reporting-policy")
async def get_reporting_policy(site_id: str = "*") -> dict[str, Any]:
    return {"site_id": site_id, "policy": get_policy(site_id).model_dump(mode="json")}


@router.put("/reporting-policy")
async def put_reporting_policy(policy: AIReportingPolicy, site_id: str = "*") -> dict[str, Any]:
    try:
        return save_policy(policy, site_id=site_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI reporting policy could not be persisted: {exc}") from exc


@router.get("/reporting-status")
async def get_reporting_status(site_id: str = "*") -> dict[str, Any]:
    return reporting_status(site_id)


@router.get("/reports")
async def get_reports(site_id: str | None = None, report_type: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return list_report_jobs(site_id=site_id, report_type=report_type, status=status, limit=limit)


@router.get("/reports/latest")
async def latest_report(site_id: str | None = None) -> dict[str, Any] | None:
    return get_latest_report(site_id=site_id)


@router.get("/reports/{report_id}")
async def report_detail(report_id: str) -> dict[str, Any]:
    report = get_report_job(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="AI report not found")
    return report


@router.get("/report-activity")
async def report_activity(site_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    jobs = list_report_jobs(site_id=site_id, limit=limit)
    return [job for job in jobs if job.get("status") != "completed"]


@router.post("/reports/generate")
async def generate_report(request: ReportGenerateRequest) -> dict[str, Any]:
    end = request.window_end or datetime.now(timezone.utc)
    start = request.window_start or (end - timedelta(hours=1))
    return create_report_job(
        site_id=request.site_id,
        report_type=request.report_type,
        trigger_reason=request.trigger_reason,
        window_start=start,
        window_end=end,
        policy=get_policy(request.site_id),
    )
