from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_linux_installer_has_safe_lifecycle_contract() -> None:
    script = (ROOT / "scripts" / "install-linux-site-server.sh").read_text(encoding="utf-8")
    assert "source-build" in script
    assert "registry" in script
    assert "systemctl enable" in script
    assert "docker compose" in script
    assert "--profile ui --profile edge" in script
    assert "--env-file" in script
    assert "docker compose" in script
    assert "down --volumes" not in script
    assert "SCRIPT_DIR}/../.." in script
    assert "DOCTOR_SOURCE" in script
    assert "UNINSTALL_SOURCE" in script
    assert "upgrade.sh" in script


def test_linux_doctor_and_uninstaller_preserve_data_by_default() -> None:
    doctor = (ROOT / "scripts" / "ravan-site-doctor.sh").read_text(encoding="utf-8")
    uninstall = (ROOT / "scripts" / "uninstall-linux-site-server.sh").read_text(encoding="utf-8")
    upgrade = (ROOT / "scripts" / "upgrade-linux-site-server.sh").read_text(encoding="utf-8")
    assert "docker compose" in doctor
    assert "/health" in doctor
    assert "--purge" in uninstall
    assert "Named Docker volumes were not removed" in uninstall
    assert "docker compose" in uninstall
    assert "down --volumes" not in uninstall
    assert "previous-runtime" in upgrade
    assert "Rollback started" in upgrade
    assert "runtime.next" in upgrade
