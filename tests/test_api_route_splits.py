from __future__ import annotations


def test_split_domain_routes_registered():
    import services.api_service.main as api_main

    routes = {route.path for route in api_main.app.routes}
    expected = {
        "/api/v1/pipelines",
        "/api/v1/pipelines/{topology_id}",
        "/api/v1/schemas",
        "/api/v1/schemas/{schema_id}/validate",
        "/api/v1/preview/topics",
        "/api/v1/preview/topics/{topic}",
        "/api/v1/preview/topics/{topic}/peek",
        "/api/v1/connectors",
        "/api/v1/connectors/{connector_id}",
        "/api/v1/digital-twin/scenes/{scene_id}",
        "/api/v1/digital-twin/scenes/{scene_id}/entities/{entity_id}/values",
        "/api/v1/oee/shifts",
        "/api/v1/oee/calculate",
        "/api/v1/assets/external",
        "/api/v1/assets/external/{asset_id}",
        "/api/v1/assets/external/{asset_id}/tags",
        "/api/v1/events/external",
        "/api/v1/historian/backup",
        "/api/v1/historian/restore",
        "/api/v1/historian/backups",
        "/api/v1/historian/backup/status",
        "/api/v1/reports/templates",
        "/api/v1/reports/generate/{template_id}",
        "/api/v1/reports",
        "/api/v1/reports/schedule/{template_id}",
    }
    missing = expected - routes
    assert not missing, f"missing routes: {sorted(missing)}"
