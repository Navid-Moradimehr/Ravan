from __future__ import annotations

import importlib


def test_asset_store_persists_and_recovers_state(tmp_path, monkeypatch):
    state_path = tmp_path / "asset-store.json"
    monkeypatch.setenv("ASSET_STORE_PATH", str(state_path))

    import services.assets.model as asset_model

    reloaded_module = importlib.reload(asset_model)
    reloaded_module.add_asset(
        reloaded_module.AssetNode(
            id="asset-1",
            name="Pump 01",
            type="pump",
            parent_id="cell-1",
            metadata={"site_id": "demo-site"},
        )
    )
    reloaded_module.add_tag_to_asset(
        asset_id="asset-1",
        tag_id="temp-1",
        name="Temperature",
        unit="C",
        min_val=0.0,
        max_val=100.0,
        warning_low=10.0,
        warning_high=90.0,
        critical_low=5.0,
        critical_high=95.0,
        sampling_rate_hz=1.0,
    )

    reloaded_again = importlib.reload(asset_model)
    asset = reloaded_again.get_asset("asset-1")

    assert asset is not None
    assert asset.name == "Pump 01"
    assert asset.metadata["site_id"] == "demo-site"
    assert asset.tags[0]["id"] == "temp-1"


def test_external_router_uses_asset_crud(tmp_path, monkeypatch):
    state_path = tmp_path / "asset-store-router.json"
    monkeypatch.setenv("ASSET_STORE_PATH", str(state_path))

    import services.assets.model as asset_model
    import services.api_service.routers.external as external_router

    importlib.reload(asset_model)
    importlib.reload(external_router)

    asset = asset_model.AssetNode(id="asset-2", name="Motor 01", type="motor")
    asset_model.add_asset(asset)

    fetched = asset_model.get_asset("asset-2")
    assert fetched is not None
    assert fetched.to_dict()["type"] == "motor"
