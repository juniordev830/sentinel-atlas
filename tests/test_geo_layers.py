"""Testes sem rede: 16 categorias, origem explícita, validação e fontes opcionais."""
from unittest.mock import Mock

from fastapi.testclient import TestClient

import backend.geo_layers as layers
from backend.app import app


def test_catalog_has_sixteen_distinct_real_or_optional_sources(monkeypatch):
    for key in ("GOOGLE_MAPS_API_KEY", "FIRMS_MAP_KEY", "GFW_API_TOKEN",
                "SENTINEL_TRANSIT_GEOJSON_URL", "SENTINEL_HYDRO_GEOJSON_URL",
                "SENTINEL_ALERTS_GEOJSON_URL"):
        monkeypatch.delenv(key, raising=False)
    catalog = layers.catalog()
    assert len(catalog) == 16
    assert len({row["id"] for row in catalog}) == 16
    assert next(row for row in catalog if row["id"] == "traffic")["status"] == "requires_configuration"
    assert next(row for row in catalog if row["id"] == "weather")["data_kind"] == "model"
    assert next(row for row in catalog if row["id"] == "municipalities")["status"] == "needs_region"
    assert next(row for row in catalog if row["id"] == "vessels")["status"] == "requires_configuration"
    assert all(row["documentation"].startswith("https://") for row in catalog)


def test_catalog_does_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("GFW_API_TOKEN", "really-secret-token")
    monkeypatch.setenv("FIRMS_MAP_KEY", "really-secret-firms")
    monkeypatch.setenv("SENTINEL_ALERTS_GEOJSON_URL", "https://official.example.org/feed")
    response = layers.catalog()
    assert "really-secret" not in str(response)
    assert "https://official.example.org/feed" not in str(response)
    assert next(row for row in response if row["id"] == "vessels")["status"] == "ready"


def test_missing_credentials_short_circuit_without_external_network(monkeypatch):
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    monkeypatch.setattr(layers, "_run_layer", lambda *args: (_ for _ in ()).throw(AssertionError("network call")))
    answer = layers.fetch_layer("wildfires", -5.8, -35.2)
    assert answer["status"] == "requires_configuration"
    assert answer["items"] == []
    assert answer["fetched_at"] is None


def test_invalid_coordinates_uf_and_unknown_layers():
    import pytest
    with pytest.raises(ValueError):
        layers.fetch_layer("weather", float("nan"), 0)
    with pytest.raises(ValueError):
        layers.fetch_layer("weather", 0, -181)
    with pytest.raises(ValueError):
        layers.fetch_layer("municipalities", 0, 0, region="../")
    with pytest.raises(KeyError):
        layers.fetch_layer("not-a-layer", 0, 0)
    assert layers.fetch_layer("municipalities", 0, 0)["status"] == "needs_region"


def test_weather_returns_model_not_measured_station(monkeypatch):
    def fake_request(url, **kwargs):
        assert url == "https://api.open-meteo.com/v1/forecast"
        return {"current": {"temperature_2m": 29, "relative_humidity_2m": 66,
                            "wind_speed_10m": 12, "time": "2026-11-02T12:00"}}
    monkeypatch.setattr(layers, "_request", fake_request)
    points, _ = layers._run_layer("weather", -5.8, -35.2, "")
    assert len(points) == 1
    assert points[0]["data_kind"] == "model"
    assert "29" in points[0]["detail"]


def test_eonet_only_maps_valid_point_geometry(monkeypatch):
    monkeypatch.setattr(layers, "_request", lambda *_args, **_kwargs: {
        "events": [
            {"id": "EONET_1", "title": "Tempestade",
             "categories": [{"title": "Severe Storms"}],
             "geometry": [{"type": "Point", "coordinates": [-36, -7], "date": "2026-11-02"}]},
            {"id": "EONET_2", "title": "Área",
             "geometry": [{"type": "Polygon", "coordinates": [[[-30, -5]]]}]},
        ]
    })
    points, _ = layers._run_layer("extreme_events", -7, -36, "")
    assert len(points) == 1
    assert points[0]["lat"] == -7 and points[0]["lng"] == -36


def test_geojson_rejects_arbitrary_geometry_and_html_is_not_used():
    data = {"type": "FeatureCollection", "features": [
        {"geometry": {"type": "Point", "coordinates": [-35, -5]},
         "properties": {"title": "<script>alert('bad')</script>"}},
        {"geometry": {"type": "Polygon", "coordinates": [[]]},
         "properties": {"title": "Polygon"}},
    ]}
    points = layers._geojson(data, "hydrology")
    assert len(points) == 1
    assert points[0]["title"] == "<script>alert('bad')</script>"


def test_municipalities_requires_uf_and_uses_official_ibge(monkeypatch):
    monkeypatch.setattr(layers, "_request", lambda url, **kwargs: [
        {"id": 2408003, "nome": "Mossoró"}, {"id": 2408102, "nome": "Natal"}])
    pts, _ = layers._run_layer("municipalities", -5.8, -35.2, "RN")
    assert len(pts) == 2
    assert pts[0]["lat"] is None  # não fingir que a lista IBGE fornece coordenadas
    assert "Mossoró" in pts[0]["title"]


def test_geoint_api_catalog_does_not_access_external_sources(monkeypatch):
    monkeypatch.setattr(layers, "_run_layer", lambda *args: (_ for _ in ()).throw(AssertionError("network")))
    client = TestClient(app)
    result = client.get("/api/geoint/layers")
    assert result.status_code == 200
    assert result.json()["count"] == 16
    assert client.get("/api/geoint/layers/invalid?lat=0&lng=0").status_code == 404
    assert client.get("/api/geoint/layers/weather?lat=91&lng=0").status_code == 422
    assert client.get("/api/geoint/layers/weather?lat=0&lng=-190").status_code == 422


def test_geoint_api_layer_sample_and_cache(monkeypatch):
    layers._cache.clear()
    calls = []
    def stub(layer, lat, lng, region):
        calls.append(layer)
        return ([layers._point("one", "Condições modeladas", lat, lng, "25 °C")], None)
    monkeypatch.setattr(layers, "_run_layer", stub)
    client = TestClient(app)
    first = client.get("/api/geoint/layers/weather?lat=-6.238&lng=-35.456")
    second = client.get("/api/geoint/layers/weather?lat=-6.238&lng=-35.456")
    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert calls == ["weather"]
    layers._cache.clear()

def test_geoint_cache_keeps_nearby_coordinates_separate(monkeypatch):
    """Coordenadas distintas não podem compartilhar resultado por arredondamento amplo."""
    layers._cache.clear()
    calls = []

    def fake_layer(layer, lat, lng, region):
        calls.append((lat, lng))
        return [layers._point("local", "Consulta geográfica", lat, lng)], None

    monkeypatch.setattr(layers, "_run_layer", fake_layer)
    try:
        first = layers.fetch_layer("weather", -5.80111, -35.20111)
        second = layers.fetch_layer("weather", -5.80444, -35.20444)
        again = layers.fetch_layer("weather", -5.80111, -35.20111)
        assert len(calls) == 2
        assert first["items"][0]["lat"] != second["items"][0]["lat"]
        assert first["cached"] is False
        assert second["cached"] is False
        assert again["cached"] is True
    finally:
        layers._cache.clear()


def test_geoint_download_stops_when_response_exceeds_limit(monkeypatch):
    """O limite de 1,5 MB precisa interromper o streaming, não só validar no fim."""
    import httpx
    import pytest
    from backend.source_clients import SourceUnavailable

    class CountingStream(httpx.SyncByteStream):
        read_chunks = 0

        def __iter__(self):
            for _ in range(5):
                self.read_chunks += 1
                yield b"x" * 600_000

    source = CountingStream()
    original_client = httpx.Client

    def mock_client(**kwargs):
        return original_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, stream=source)
            ), **kwargs
        )

    monkeypatch.setattr(layers.httpx, "Client", mock_client)
    with pytest.raises(SourceUnavailable, match="maior que o limite"):
        layers._request("https://example.org/oversized", text=True)
    assert source.read_chunks < 5, "o corpo inteiro foi descarregado antes do limite"


def test_geoint_streamed_json_response(monkeypatch):
    import httpx

    original_client = httpx.Client
    monkeypatch.setattr(
        layers.httpx, "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"entries": [1, 2]})
            ), **kwargs
        )
    )
    assert layers._request("https://example.org/feed") == {"entries": [1, 2]}


def test_weather_structured_measurements_for_visuals(monkeypatch):
    """Valores numéricos verdadeiros com direção meteorológica, sem números inventados."""
    def fake_request(url, **kwargs):
        assert "wind_direction_10m" in kwargs["params"]["current"]
        return {"current": {
            "temperature_2m": 27, "relative_humidity_2m": 81,
            "wind_speed_10m": 18.5, "wind_direction_10m": 135,
            "precipitation": 0.4, "cloud_cover": 92, "time": "2026-11-02T22:00"
        }}
    monkeypatch.setattr(layers, "_request", fake_request)
    items, _ = layers._run_layer("weather", -5.8, -35.2, "")
    assert len(items) == 1
    assert items[0]["data_kind"] == "model"
    assert items[0]["measurements"] == {
        "temperature_c": 27.0, "humidity_pct": 81.0,
        "wind_speed_kmh": 18.5, "wind_direction_deg": 135.0,
        "precipitation_mm": 0.4, "cloud_cover_pct": 92.0
    }


def test_weather_measurements_reject_invalid_and_boolean_values(monkeypatch):
    monkeypatch.setattr(layers, "_request", lambda *_args, **_kwargs: {
        "current": {
            "temperature_2m": float("nan"), "relative_humidity_2m": 105,
            "wind_speed_10m": True, "wind_direction_10m": 720,
            "precipitation": -1, "cloud_cover": 30, "time": "2026-11-02T12:00"
        }
    })
    items, _ = layers._run_layer("weather", 1, 2, "")
    measurements = items[0]["measurements"]
    assert measurements == {
        "temperature_c": None, "humidity_pct": None,
        "wind_speed_kmh": None, "wind_direction_deg": None,
        "precipitation_mm": None, "cloud_cover_pct": 30.0
    }


def test_air_quality_measurements_for_visuals(monkeypatch):
    monkeypatch.setattr(layers, "_request", lambda *_args, **_kwargs: {
        "current": {"pm2_5": 12.5, "pm10": 32.3, "us_aqi": 48, "time": "2026-11-02T21:00"}
    })
    items, _ = layers._run_layer("air_quality", -5, -35, "")
    assert items[0]["measurements"] == {
        "pm25_ugm3": 12.5, "pm10_ugm3": 32.3, "us_aqi": 48.0
    }
