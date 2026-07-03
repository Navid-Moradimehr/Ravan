from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.historian.backup import create_backup, get_walg_status, list_backups, restore_backup


router = APIRouter(tags=["backup"])


class BackupRequest(BaseModel):
    tables: list[str] | None = None
    backup_dir: str | None = None


class RestoreRequest(BaseModel):
    backup_path: str
    target_database: str | None = None


@router.post("/api/v1/historian/backup")
async def backup_historian(req: BackupRequest) -> dict[str, Any]:
    result = create_backup(backup_dir=req.backup_dir, tables=req.tables)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Backup failed"))
    return result


@router.post("/api/v1/historian/restore")
async def restore_historian(req: RestoreRequest) -> dict[str, Any]:
    result = restore_backup(req.backup_path, req.target_database)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Restore failed"))
    return result


@router.get("/api/v1/historian/backups")
async def list_historian_backups() -> list[dict[str, Any]]:
    return list_backups()


@router.get("/api/v1/historian/backup/status")
async def backup_status() -> dict[str, Any]:
    return get_walg_status()
