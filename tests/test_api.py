from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import backend.app as app_module
from backend.app import app

client = TestClient(app)


def test_create_list_and_delete_geofence():
    # List initial
    resp = client.get("/api/geofences")
    assert resp.status_code == 200

    # Create geofence
    payload = {
        "name": "test_zone",
        "latitude": -23.55,
        "longitude": -46.63,
        "radius_meters": 300.0,
    }
    resp = client.post("/api/geofences", json=payload)
    assert resp.status_code == 201
    assert resp.json()["name"] == "test_zone"

    # Verify present
    resp = client.get("/api/geofences")
    assert resp.status_code == 200
    names = [g["name"] for g in resp.json()]
    assert "test_zone" in names

    # Delete geofence
    resp = client.delete("/api/geofences/test_zone")
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "name": "test_zone"}

    # Delete again -> 404
    resp = client.delete("/api/geofences/test_zone")
    assert resp.status_code == 404


def test_http_api_requires_configured_bearer_token(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, environment="test", api_token="test-token"),
    )

    assert client.get("/api/geofences").status_code == 401
    assert client.get(
        "/api/geofences", headers={"Authorization": "Bearer wrong-token"}
    ).status_code == 401
    assert client.get(
        "/api/geofences", headers={"Authorization": "Bearer test-token"}
    ).status_code == 200


def test_public_health_remains_available_without_token(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, environment="production", api_token="test-token"),
    )

    response = client.get("/api/health")
    assert response.status_code == 200


def test_http_api_fails_closed_in_production_without_token(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, environment="production", api_token=None),
    )

    response = client.get("/api/geofences")
    assert response.status_code == 503
    assert response.json() == {"detail": "Autenticação da API não configurada"}


def test_websocket_rejects_production_when_token_is_missing(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, environment="production", api_token=None),
    )

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/ws/positions"):
            pass

    assert error.value.code == 1013


def test_health_is_public():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_websocket_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, environment="production", api_token="x" * 32),
    )

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(
            "/ws/positions",
            headers={"Authorization": "Bearer invalid-token"},
        ):
            pass

    assert error.value.code == 1008


def test_websocket_rejects_oversized_message(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, environment="production", api_token="x" * 32),
    )

    with client.websocket_connect(
        "/ws/positions",
        headers={"Authorization": "Bearer " + "x" * 32},
    ) as websocket:
        websocket.send_text("x" * 16_385)
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()
        assert error.value.code == 1009
