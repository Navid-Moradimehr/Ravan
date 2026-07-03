from __future__ import annotations

from fastapi import APIRouter

from services.api_service.routers.backup import router as backup_router
from services.api_service.routers.reports import router as reports_router


router = APIRouter(tags=["support"])
router.include_router(backup_router)
router.include_router(reports_router)
