from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import backend.app as app_module
from backend.app import PositionInput, app

client = TestClient(app)



def test_google_maps_public_config_never_exposes_admin_token(monkeypatch):
    """A chave do navegador pode ser pública, mas o token administrativo nunca."""
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(
            app_module.settings,
            environment="test",
            api_token="private-sentinel-token",
            google_maps_api_key="browser-referrer-restricted-key",
        ),
    )
    response = client.get("/api/public-config")
    assert response.status_code == 200
    assert response.json() == {
        "google_maps_api_key": "browser-referrer-restricted-key",
        "google_maps_enabled": True,
    }
    assert "private-sentinel-token" not in response.text

    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, google_maps_api_key=None),
    )
    response = client.get("/api/public-config")
    assert response.json() == {
        "google_maps_api_key": None,
        "google_maps_enabled": False,
    }


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



@pytest.mark.parametrize("timestamp", [-1, float("nan"), float("inf"), float("-inf")])
def test_position_input_rejects_invalid_timestamps(timestamp):
    with pytest.raises(ValueError):
        PositionInput(latitude=0, longitude=0, timestamp=timestamp)


def test_position_input_preserves_zero_timestamp():
    position = PositionInput(latitude=0, longitude=0, timestamp=0)
    assert position.timestamp == 0



def _configure_browser_auth(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        replace(app_module.settings, environment="test", api_token="test-browser-token"),
    )
    client.cookies.clear()


def test_browser_login_creates_httponly_session_cookie(monkeypatch):
    _configure_browser_auth(monkeypatch)

    response = client.post(
        "/api/session",
        json={"token": "test-browser-token"},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "expires_in": 3600}
    cookie = response.headers["set-cookie"].lower()
    assert "sentinel_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert client.get("/api/geofences").status_code == 200


def test_browser_login_rejects_invalid_token_and_cross_origin(monkeypatch):
    _configure_browser_auth(monkeypatch)

    invalid_token = client.post(
        "/api/session",
        json={"token": "wrong-token"},
        headers={"Origin": "http://testserver"},
    )
    assert invalid_token.status_code == 401

    invalid_origin = client.post(
        "/api/session",
        json={"token": "test-browser-token"},
        headers={"Origin": "https://attacker.example"},
    )
    assert invalid_origin.status_code == 403


def test_browser_session_blocks_cross_origin_mutations(monkeypatch):
    _configure_browser_auth(monkeypatch)
    login = client.post(
        "/api/session",
        json={"token": "test-browser-token"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/geofences",
        json={
            "name": "csrf_attempt",
            "latitude": -23.55,
            "longitude": -46.63,
            "radius_meters": 100,
        },
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403


def test_browser_session_authenticates_websocket_with_same_origin(monkeypatch):
    _configure_browser_auth(monkeypatch)
    login = client.post(
        "/api/session",
        json={"token": "test-browser-token"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200

    with client.websocket_connect(
        "/ws/positions",
        headers={"Origin": "http://testserver"},
    ) as websocket:
        websocket.send_json({"latitude": -23.55, "longitude": -46.63, "timestamp": 1})
        message = websocket.receive_json()
        assert message["position"]["timestamp"] == 1

    client.cookies.clear()


def test_browser_session_logout_clears_cookie(monkeypatch):
    _configure_browser_auth(monkeypatch)
    login = client.post(
        "/api/session",
        json={"token": "test-browser-token"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200
    assert client.get("/api/geofences").status_code == 200

    logout = client.post("/api/session/logout")
    assert logout.status_code == 200
    assert client.get("/api/geofences").status_code == 401
    client.cookies.clear()



@pytest.mark.parametrize("cookie_value", ["0.invalid", "not-a-session", "9999999999.invalid"])
def test_browser_session_rejects_expired_or_forged_cookie(monkeypatch, cookie_value):
    _configure_browser_auth(monkeypatch)
    client.cookies.set("sentinel_session", cookie_value)

    response = client.get("/api/geofences")
    assert response.status_code == 401
    client.cookies.clear()


def test_browser_login_rejects_unicode_token_without_server_error(monkeypatch):
    _configure_browser_auth(monkeypatch)
    response = client.post(
        "/api/session", json={"token": "inválido"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 401


def test_session_signature_rejects_unicode_without_server_error(monkeypatch):
    _configure_browser_auth(monkeypatch)
    expiry = int(app_module.time.time()) + 3600
    assert app_module._valid_session_cookie(f"{expiry}.assinátura") is False
