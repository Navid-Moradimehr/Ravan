from pathlib import Path


def test_ai_warning_soak_script_has_three_protocol_shaped_sources():
    source = Path("scripts/ai-warning-soak.py").read_text(encoding="utf-8")
    assert '"opcua", "mqtt", "modbus"' in source
    assert '"warning" if warning else "normal"' in source
    assert '"warning_seconds"' in source
