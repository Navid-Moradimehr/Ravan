"""Dataset manifest and optional build-job API."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException

from services.common.dataset_registry import cancel_build_job, create_build_job, get_build_artifacts, get_build_job, list_build_jobs, list_manifests, save_manifest
from services.common.model_dataset import validate_model_manifest

router = APIRouter(tags=["datasets"])


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@router.post("/api/v1/datasets/manifests/validate")
async def validate_dataset_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return validate_model_manifest(manifest).to_dict()


@router.get("/api/v1/datasets/manifests")
async def get_dataset_manifests(dataset_id: str | None = None) -> list[dict[str, Any]]:
    try:
        return list_manifests(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset metadata unavailable: {exc}") from exc


@router.post("/api/v1/datasets/manifests")
async def register_dataset_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    validation = validate_model_manifest(manifest)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.to_dict())
    try:
        return save_manifest(manifest, _hash(manifest))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset metadata unavailable: {exc}") from exc


@router.get("/api/v1/datasets/manifests/{dataset_id}/versions")
async def get_dataset_manifest_versions(dataset_id: str) -> list[dict[str, Any]]:
    try:
        return list_manifests(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset metadata unavailable: {exc}") from exc


@router.post("/api/v1/datasets/builds")
async def queue_dataset_build(request: dict[str, Any]) -> dict[str, Any]:
    required = ["dataset_id", "manifest_version", "manifest_path", "output_dir"]
    missing = [key for key in required if not request.get(key)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing fields: {', '.join(missing)}")
    try:
        return create_build_job(str(request["dataset_id"]), int(request["manifest_version"]), str(request["manifest_path"]), str(request["output_dir"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset build queue unavailable: {exc}") from exc


@router.get("/api/v1/datasets/builds")
async def get_dataset_builds() -> list[dict[str, Any]]:
    try:
        return list_build_jobs()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset build queue unavailable: {exc}") from exc


@router.get("/api/v1/datasets/builds/{job_id}")
async def get_dataset_build(job_id: str) -> dict[str, Any]:
    try:
        job = get_build_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="dataset build job not found")
        return job
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset build queue unavailable: {exc}") from exc


@router.post("/api/v1/datasets/builds/{job_id}/cancel")
async def cancel_dataset_build(job_id: str) -> dict[str, Any]:
    try:
        if not cancel_build_job(job_id):
            raise HTTPException(status_code=409, detail="only queued dataset builds can be cancelled")
        return {"job_id": job_id, "status": "cancelled"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset build queue unavailable: {exc}") from exc


@router.get("/api/v1/datasets/builds/{job_id}/artifacts")
async def get_dataset_build_artifacts(job_id: str) -> list[dict[str, Any]]:
    try:
        return get_build_artifacts(job_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dataset build artifacts unavailable: {exc}") from exc
