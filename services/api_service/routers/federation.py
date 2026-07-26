from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from services.common.federation_contract import FEDERATION_ENVELOPE_VERSION, REQUIRED_ORIGIN_FIELDS
from services.federation.delivery_ledger import DeliveryLedger
from services.federation.health import federation_health
from services.federation.policy import allowed_topics

router = APIRouter(tags=["federation"])


@router.get("/api/v1/federation/contracts")
async def federation_contract() -> dict[str, Any]:
    topics = allowed_topics(os.getenv("DATASTREAM_PROJECT_MANIFEST", ""), os.getenv("FEDERATION_ALLOWED_TOPICS", ""))
    return {
        "envelope_version": FEDERATION_ENVELOPE_VERSION,
        "required_origin_fields": list(REQUIRED_ORIGIN_FIELDS),
        "allowed_topics": list(topics),
        "legacy_unwrapped_events": True,
        "deployment_mode": os.getenv("DEPLOYMENT_MODE", "single-site"),
    }


@router.get("/api/v1/federation/status")
async def federation_status() -> dict[str, Any]:
    return {"health": federation_health(), "delivery": DeliveryLedger().snapshot()}
