from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.analytics.reporting import ReportTemplate, report_engine


router = APIRouter(tags=["reports"])


class ReportTemplateRequest(BaseModel):
    template_id: str
    name: str
    description: str = ""
    query: str = ""
    format: str = "csv"
    schedule: str | None = None
    recipients: list[str] = Field(default_factory=list)
    enabled: bool = True


@router.post("/api/v1/reports/templates")
async def create_report_template(req: ReportTemplateRequest) -> dict[str, str]:
    template = ReportTemplate(
        template_id=req.template_id,
        name=req.name,
        description=req.description,
        query=req.query,
        format=req.format,
        schedule=req.schedule,
        recipients=req.recipients,
        enabled=req.enabled,
    )
    report_engine.register_template(template)
    return {"status": "ok", "template_id": req.template_id}


@router.get("/api/v1/reports/templates")
async def list_report_templates() -> list[dict[str, Any]]:
    return report_engine.list_templates()


@router.post("/api/v1/reports/generate/{template_id}")
async def generate_report(
    template_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    format: str | None = None,
) -> dict[str, Any]:
    return report_engine.generate_report(template_id, start_time, end_time, format)


@router.get("/api/v1/reports")
async def list_generated_reports() -> list[dict[str, Any]]:
    return report_engine.list_generated_reports()


@router.post("/api/v1/reports/schedule/{template_id}")
async def schedule_report(template_id: str, cron: str = "daily") -> dict[str, Any]:
    return report_engine.schedule_report(template_id, cron)
