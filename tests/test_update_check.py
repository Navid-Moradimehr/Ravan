import httpx

from services.common.update_check import check_for_update, current_version, version_key


def test_version_key_accepts_v_prefix():
    assert version_key("v1.2") == (1, 2, 0)


def test_update_check_is_disabled_by_default():
    result = check_for_update(enabled=False, current="0.3.0")
    assert result.available is False
    assert result.enabled is False


def test_current_version_uses_ravan_release_identity(monkeypatch):
    monkeypatch.delenv("DATASTREAM_RELEASE_VERSION", raising=False)
    assert current_version() == "1.0.0-beta.1"


def test_update_check_reports_new_release():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "version": "0.4.0",
        "release_url": "https://github.com/example/project/releases/tag/v0.4.0",
    }))
    with httpx.Client(transport=transport) as client:
        result = check_for_update(enabled=True, manifest_url="https://example.test/release.json", current="0.3.0", client=client)
    assert result.available is True
    assert result.release_url.endswith("v0.4.0")


def test_update_check_rejects_bad_manifest():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"version": "not-a-version"}))
    with httpx.Client(transport=transport) as client:
        result = check_for_update(enabled=True, manifest_url="https://example.test/release.json", client=client)
    assert result.available is False
    assert result.error
