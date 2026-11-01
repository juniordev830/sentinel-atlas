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
