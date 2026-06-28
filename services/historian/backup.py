"""Backup and restore utilities for TimescaleDB historian.

Uses PostgreSQL native tools (pg_dump, pg_restore) as the primary method.
wal-g is recommended for production continuous archiving.

Open-source alternatives:
- wal-g: https://github.com/wal-g/wal-g (continuous archiving)
- barman: https://github.com/EnterpriseDB/barman (backup manager)
- pgBackRest: https://github.com/pgbackrest/pgbackrest (backup and restore)
"""
from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _connection_params() -> dict[str, str]:
    """Get connection parameters from environment."""
    return {
        "host": os.getenv("TIMESCALE_HOST", "localhost"),
        "port": os.getenv("TIMESCALE_PORT", "15433"),
        "database": os.getenv("TIMESCALE_DB", "stream_engine"),
        "user": os.getenv("TIMESCALE_USER", "stream"),
        "password": os.getenv("TIMESCALE_PASSWORD", "stream"),
    }


def create_backup(backup_dir: str | None = None, tables: list[str] | None = None) -> dict[str, Any]:
    """Create a PostgreSQL dump of the historian database.

    Args:
        backup_dir: Directory to store backup files. Defaults to ./backups
        tables: List of tables to backup. If None, backs up entire database.

    Returns:
        dict with backup path and metadata
    """
    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backups")

    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)

    conn = _connection_params()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"historian_backup_{timestamp}.sql"
    filepath = backup_path / filename

    # Build pg_dump command
    cmd = [
        "pg_dump",
        f"--host={conn['host']}",
        f"--port={conn['port']}",
        f"--username={conn['user']}",
        "--format=custom",  # Compressed custom format
        "--blobs",
        f"--file={filepath}",
    ]

    if tables:
        for table in tables:
            cmd.extend(["--table", table])
    else:
        cmd.append("--schema=public")

    cmd.append(conn["database"])

    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Backup created: {filepath}")
        return {
            "status": "success",
            "path": str(filepath),
            "filename": filename,
            "timestamp": timestamp,
            "tables": tables or ["all"],
            "size_bytes": filepath.stat().st_size if filepath.exists() else 0,
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed: {e.stderr}")
        return {
            "status": "error",
            "error": e.stderr,
            "command": " ".join(cmd),
        }
    except FileNotFoundError:
        logger.error("pg_dump not found. Install PostgreSQL client tools.")
        return {
            "status": "error",
            "error": "pg_dump not found. Install PostgreSQL client tools.",
        }


def restore_backup(backup_path: str, target_database: str | None = None) -> dict[str, Any]:
    """Restore a PostgreSQL backup.

    Args:
        backup_path: Path to the backup file
        target_database: Target database name. If None, uses original database name.

    Returns:
        dict with restore status
    """
    filepath = Path(backup_path)
    if not filepath.exists():
        return {
            "status": "error",
            "error": f"Backup file not found: {backup_path}",
        }

    conn = _connection_params()
    if target_database:
        conn["database"] = target_database

    cmd = [
        "pg_restore",
        f"--host={conn['host']}",
        f"--port={conn['port']}",
        f"--username={conn['user']}",
        "--dbname", conn["database"],
        "--verbose",
        "--no-owner",
        "--no-privileges",
        str(filepath),
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Backup restored to {conn['database']}")
        return {
            "status": "success",
            "database": conn["database"],
            "backup_path": str(filepath),
            "output": result.stdout,
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Restore failed: {e.stderr}")
        return {
            "status": "error",
            "error": e.stderr,
        }
    except FileNotFoundError:
        logger.error("pg_restore not found. Install PostgreSQL client tools.")
        return {
            "status": "error",
            "error": "pg_restore not found. Install PostgreSQL client tools.",
        }


def list_backups(backup_dir: str | None = None) -> list[dict[str, Any]]:
    """List available backup files with metadata."""
    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backups")

    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return []

    backups = []
    for file in sorted(backup_path.glob("historian_backup_*.sql"), reverse=True):
        stat = file.stat()
        backups.append({
            "filename": file.name,
            "path": str(file),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    return backups


def get_walg_status() -> dict[str, Any]:
    """Check if wal-g is installed and configured."""
    walg_installed = False
    try:
        result = subprocess.run(["wal-g", "version"], capture_output=True, text=True)
        walg_installed = result.returncode == 0
    except FileNotFoundError:
        pass

    return {
        "installed": walg_installed,
        "recommended_for": "Production continuous archiving",
        "documentation": "https://github.com/wal-g/wal-g",
        "installation": "See docs/open-source-research.md",
    }
