from __future__ import annotations

from fastapi import APIRouter

from services.api_service.routers.connectors import router as connectors_router
from services.api_service.routers.digital_twin import router as digital_twin_router
from services.api_service.routers.oee import router as oee_router
from services.api_service.routers.pipelines import router as pipelines_router
from services.api_service.routers.preview import router as preview_router
from services.api_service.routers.schemas import router as schemas_router


router = APIRouter(tags=["design"])
router.include_router(pipelines_router)
router.include_router(schemas_router)
router.include_router(preview_router)
router.include_router(connectors_router)
router.include_router(digital_twin_router)
router.include_router(oee_router)
