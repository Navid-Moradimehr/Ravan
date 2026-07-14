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
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker" / "docker-compose.yml"
DEFAULT_SNAPSHOT_TABLES: tuple[str, ...] = (
    "industrial_events",
    "processed_events",
    "ai_enriched",
    "dead_letter_events",
)


def _connection_params() -> dict[str, str]:
    """Get connection parameters from environment."""
    return {
        "host": os.getenv("TIMESCALE_HOST", "localhost"),
        "port": os.getenv("TIMESCALE_PORT", "15433"),
        "database": os.getenv("TIMESCALE_DB", "stream_engine"),
        "user": os.getenv("TIMESCALE_USER", "stream"),
        "password": os.getenv("TIMESCALE_PASSWORD", "stream"),
    }


def _compose_base_cmd() -> list[str]:
    return ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE)]


def _detect_docker_db_service() -> str | None:
    preferred = os.getenv("DATASTREAM_DOCKER_DB_SERVICE")
    candidates = [preferred] if preferred else ["timescaledb", "postgres"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            result = subprocess.run(
                _compose_base_cmd() + ["ps", "-q", candidate],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(PROJECT_ROOT),
            )
        except FileNotFoundError:
            return None
        if result.returncode == 0 and result.stdout.strip():
            return candidate
    return None


def _docker_exec_env(conn: dict[str, str]) -> list[str]:
    return [
        "-e", f"PGPASSWORD={conn['password']}",
        "-e", f"PGUSER={conn['user']}",
        "-e", "PGHOST=localhost",
        "-e", "PGPORT=5432",
        "-e", f"PGDATABASE={conn['database']}",
    ]


def _without_public_schema_entries(toc: str) -> str:
    """Keep TimescaleDB's extension-owned public schema out of clean restores."""
    return "\n".join(
        line
        for line in toc.splitlines()
        if "SCHEMA - public" not in line and "ACL - public" not in line
    ) + "\n"


def _temporary_toc_path() -> Path:
    fd, name = tempfile.mkstemp(prefix="datastream-restore-", suffix=".toc")
    os.close(fd)
    return Path(name)


def _create_backup_via_docker(filepath: Path, conn: dict[str, str], tables: list[str] | None) -> dict[str, Any]:
    service = _detect_docker_db_service()
    if not service:
        return {
            "status": "error",
            "error": "pg_dump not found and no running docker database service detected.",
        }

    cmd = _compose_base_cmd() + ["exec", "-T"] + _docker_exec_env(conn) + [service, "pg_dump", "--format=custom", "--blobs"]
    if tables:
        for table in tables:
            cmd.extend(["--table", table])
    else:
        cmd.append("--schema=public")
    cmd.append(conn["database"])

    try:
        with open(filepath, "wb") as out:
            subprocess.run(
                cmd,
                stdout=out,
                stderr=subprocess.PIPE,
                check=True,
                cwd=str(PROJECT_ROOT),
            )
        logger.info("Backup created via docker service %s: %s", service, filepath)
        return {
            "status": "success",
            "path": str(filepath),
            "filename": filepath.name,
            "timestamp": filepath.stem.removeprefix("historian_backup_"),
            "tables": tables or ["all"],
            "size_bytes": filepath.stat().st_size if filepath.exists() else 0,
            "transport": f"docker:{service}",
        }
    except subprocess.CalledProcessError as e:
        logger.error("Docker backup failed: %s", e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else e.stderr)
        return {
            "status": "error",
            "error": e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr),
            "transport": f"docker:{service}",
        }


def _restore_backup_via_docker(filepath: Path, conn: dict[str, str]) -> dict[str, Any]:
    service = _detect_docker_db_service()
    if not service:
        return {
            "status": "error",
            "error": "pg_restore not found and no running docker database service detected.",
        }

    container_path = f"/tmp/{filepath.name}"
    container_name_cmd = _compose_base_cmd() + ["ps", "-q", service]
    try:
        container_id = subprocess.run(
            container_name_cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT),
        ).stdout.strip()
        if not container_id:
            return {
                "status": "error",
                "error": f"Docker database service '{service}' is not running.",
            }
        subprocess.run(["docker", "cp", str(filepath), f"{container_id}:{container_path}"], check=True, cwd=str(PROJECT_ROOT))
        exists = subprocess.run(
            _compose_base_cmd() + ["exec", "-T", service] + [
                "psql",
                "-U",
                conn["user"],
                "-d",
                "postgres",
                "-tAc",
                f"SELECT 1 FROM pg_database WHERE datname = '{conn['database']}'",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT),
        )
        if exists.stdout.strip() != "1":
            subprocess.run(
                _compose_base_cmd() + ["exec", "-T", service] + [
                    "createdb",
                    "-U",
                    conn["user"],
                    "-O",
                    conn["user"],
                    conn["database"],
                ],
                capture_output=True,
                text=True,
                check=True,
                cwd=str(PROJECT_ROOT),
            )
        toc = subprocess.run(
            _compose_base_cmd() + ["exec", "-T", service, "pg_restore", "--list", container_path],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT),
        ).stdout
        toc_path = _temporary_toc_path()
        toc_path.write_text(_without_public_schema_entries(toc), encoding="utf-8")
        toc_container_path = f"/tmp/{toc_path.name}"
        subprocess.run(["docker", "cp", str(toc_path), f"{container_id}:{toc_container_path}"], check=True, cwd=str(PROJECT_ROOT))
        result = subprocess.run(
            _compose_base_cmd() + ["exec", "-T"] + _docker_exec_env(conn) + [
                service,
                "pg_restore",
                "--verbose",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--use-list",
                toc_container_path,
                "--dbname",
                conn["database"],
                container_path,
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT),
        )
        subprocess.run(
            _compose_base_cmd() + ["exec", "-T", service, "rm", "-f", container_path],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(PROJECT_ROOT),
        )
        toc_path.unlink(missing_ok=True)
        subprocess.run(
            _compose_base_cmd() + ["exec", "-T", service, "rm", "-f", toc_container_path],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(PROJECT_ROOT),
        )
        logger.info("Backup restored via docker service %s to %s", service, conn["database"])
        return {
            "status": "success",
            "database": conn["database"],
            "backup_path": str(filepath),
            "output": result.stdout,
            "transport": f"docker:{service}",
        }
    except subprocess.CalledProcessError as e:
        logger.error("Docker restore failed: %s", e.stderr)
        return {
            "status": "error",
            "error": e.stderr,
            "transport": f"docker:{service}",
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "error": "docker not found. Install Docker Desktop or PostgreSQL client tools.",
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
        logger.warning("pg_dump not found on host; attempting docker-based backup fallback.")
        return _create_backup_via_docker(filepath, conn, tables)


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

    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]
    toc_path: Path | None = None

    try:
        toc = subprocess.run(["pg_restore", "--list", str(filepath)], env=env, capture_output=True, text=True, check=True).stdout
        toc_path = _temporary_toc_path()
        toc_path.write_text(_without_public_schema_entries(toc), encoding="utf-8")
        cmd = [
            "pg_restore",
            f"--host={conn['host']}",
            f"--port={conn['port']}",
            f"--username={conn['user']}",
            "--dbname", conn["database"],
            "--verbose",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--use-list", str(toc_path),
            str(filepath),
        ]
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
        logger.warning("pg_restore not found on host; attempting docker-based restore fallback.")
        return _restore_backup_via_docker(filepath, conn)
    finally:
        if toc_path:
            toc_path.unlink(missing_ok=True)


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


def collect_historian_snapshot(table_names: Iterable[str] | None = None) -> dict[str, Any]:
    """Collect simple row-count snapshots for historian tables.

    The snapshot is intentionally small so backup/restore drills can compare
    pre/post restore state without depending on a full logical diff.
    """
    tables = tuple(table_names or DEFAULT_SNAPSHOT_TABLES)
    conn = _connection_params()
    query = "; ".join(
        f"SELECT '{table}' AS table_name, COUNT(*)::bigint AS row_count FROM {table}"
        for table in tables
    )
    cmd = [
        "psql",
        f"--host={conn['host']}",
        f"--port={conn['port']}",
        f"--username={conn['user']}",
        "--dbname",
        conn["database"],
        "--no-align",
        "--tuples-only",
        "--field-separator=|",
        "--command",
        query,
    ]
    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        counts: dict[str, int] = {}
        for line in result.stdout.splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 2 or not parts[0]:
                continue
            try:
                counts[parts[0]] = int(parts[1])
            except ValueError:
                counts[parts[0]] = 0
        return {
            "status": "success",
            "database": conn["database"],
            "tables": counts,
            "table_count": len(counts),
            "row_count_total": sum(counts.values()),
            "transport": "psql",
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "error": "psql not found on host; install PostgreSQL client tools to collect historian snapshots.",
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "error": e.stderr,
            "command": " ".join(cmd),
        }


def compare_historian_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_tables = before.get("tables", {}) if isinstance(before, dict) else {}
    after_tables = after.get("tables", {}) if isinstance(after, dict) else {}
    all_tables = sorted(set(before_tables) | set(after_tables))
    diffs: dict[str, dict[str, int]] = {}
    for table in all_tables:
        before_count = int(before_tables.get(table, 0))
        after_count = int(after_tables.get(table, 0))
        if before_count != after_count:
            diffs[table] = {"before": before_count, "after": after_count, "delta": after_count - before_count}
    return {
        "matched": not diffs and before.get("status") == "success" and after.get("status") == "success",
        "before": before,
        "after": after,
        "diffs": diffs,
        "table_count": len(all_tables),
    }
