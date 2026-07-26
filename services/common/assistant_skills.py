"""Read-only declarative assistant skill loading for self-hosted deployments."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _skill_path() -> Path:
    return Path(os.getenv("RAVAN_ASSISTANT_SKILLS_PATH", "config/assistant-skills"))


def _parse(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return {"name": path.stem, "label": path.stem, "version": "1", "mode": "read-only", "approval_required": False, "content": text}
    parts = text.split("---", 2)
    if len(parts) != 3:
        return None
    metadata: dict[str, Any] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    metadata["approval_required"] = str(metadata.get("approval_required", "false")).lower() == "true"
    metadata["content"] = parts[2].strip()
    metadata["path"] = str(path)
    return metadata


def list_skills() -> list[dict[str, Any]]:
    directory = _skill_path()
    if not directory.exists():
        return []
    skills = [_parse(path) for path in sorted(directory.glob("*.md"))]
    return [skill for skill in skills if skill is not None]


def get_skill(name: str) -> dict[str, Any] | None:
    return next((skill for skill in list_skills() if skill.get("name") == name), None)


def select_skills(content: str) -> list[dict[str, Any]]:
    lowered = content.lower()
    selected = []
    for skill in list_skills():
        name = str(skill.get("name", ""))
        if "source" in name and any(term in lowered for term in ("source", "sensor", "plc", "opc", "mqtt", "modbus")):
            selected.append(skill)
        elif "operator" in name:
            selected.append(skill)
    return selected
