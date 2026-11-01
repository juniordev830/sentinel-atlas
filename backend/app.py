"""API HTTP/WebSocket do Projeto Sentinel Atlas."""

from __future__ import annotations

import json
import hmac
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python.gps_core import AutomationEngine, Geofence, Position, distance_meters  # noqa: E402
from python.settings import Settings  # noqa: E402
from backend.storage import GeofenceStore  # noqa: E402
from backend.source_clients import SourceUnavailable, fetch_celestrak, fetch_opensky, fetch_text, parse_tle_text  # noqa: E402
from backend.alerts import send_webhook  # noqa: E402
from backend.routing import bicycle_route  # noqa: E402
from backend.orbits import propagate_tle  # noqa: E402
from backend.ai import GeoINTAnalyzer  # noqa: E402
from backend.location import get_location_info  # noqa: E402


class AIAnalyzeInput(BaseModel):
    assets: list[dict[str, Any]] = Field(default_factory=list)
    geofences: list[dict[str, Any]] = Field(default_factory=list)


class AIQueryInput(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    context: dict[str, Any] = Field(default_factory=dict)


class GeofenceInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(gt=0, le=1_000_000)


class PositionInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timestamp: float | None = None


from typing import Any  # noqa: E402

app = FastAPI(title="Sentinel Atlas GPS API", version="0.1.0")
settings = Settings.from_environment()
ai_analyzer = GeoINTAnalyzer()
store = GeofenceStore(os.getenv("SENTINEL_DB_PATH", str(ROOT / ".data" / "sentinel.sqlite3")))
geofences: dict[str, tuple[Geofence, AutomationEngine]] = {}
for saved_fence in store.list():
    geofences[saved_fence.name] = (saved_fence, AutomationEngine(saved_fence))


@app.middleware("http")
async def optional_token_auth(request: Request, call_next):
    protected_path = (
        request.url.path.startswith("/api/")
        and request.url.path not in {"/api/health", "/api/public-config"}
    )
    if protected_path:
        if not settings.api_token:
            if settings.environment == "production":
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Autenticação da API não configurada"},
                )
        else:
            authorization = request.headers.get("authorization", "")
            expected = f"Bearer {settings.api_token}"
            if not hmac.compare_digest(authorization, expected):
                return JSONResponse(status_code=401, content={"detail": "Token de API inválido"})
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": "Sentinel Atlas API", "timestamp": time.time()}


@app.get("/api/sources")
def sources() -> dict[str, list[str]]:
    return {"enabled": settings.enabled_sources()}


@app.get("/api/public-config")
def public_config() -> dict[str, str | bool | None]:
    """Expõe apenas configurações destinadas ao navegador.

    A chave do Google Maps deve ter restrições de domínio configuradas no Google
    Cloud; segredos de servidores nunca são retornados por esta rota.
    """
    return {
        "google_maps_api_key": settings.google_maps_api_key,
        "google_maps_enabled": bool(settings.google_maps_api_key),
    }


@app.get("/api/sources/satellites")
def satellites() -> dict[str, object]:
    try:
        satellites = fetch_celestrak(settings.celestrak_gp_url)
        return {"source": "CelesTrak", "count": len(satellites), "items": satellites[:100]}
    except SourceUnavailable as error:
        return {"source": "CelesTrak", "count": 0, "items": [], "error": str(error)}


@app.get("/api/sources/starlink")
def starlink() -> dict[str, object]:
    try:
        tle_url = settings.celestrak_starlink_url.replace("FORMAT=json", "FORMAT=tle")
        records = parse_tle_text(fetch_text(tle_url))
        items = []
        for record in records[:200]:
            if record.get("TLE_LINE1") and record.get("TLE_LINE2"):
                try:
                    items.append(propagate_tle(str(record.get("OBJECT_NAME", "Starlink")), str(record["TLE_LINE1"]), str(record["TLE_LINE2"])))
                except RuntimeError:
                    continue
        return {"source": "CelesTrak + SGP4", "count": len(items), "items": items}
    except (SourceUnavailable, RuntimeError) as error:
        return {"source": "CelesTrak + SGP4", "count": 0, "items": [], "error": str(error)}


@app.get("/api/sources/aircraft")
def aircraft() -> dict[str, object]:
    try:
        payload = fetch_opensky()
        states = payload.get("states", []) if isinstance(payload, dict) else []
        return {"source": "OpenSky", "count": len(states), "items": states[:100]}
    except SourceUnavailable as error:
        return {"source": "OpenSky", "count": 0, "items": [], "error": str(error)}


@app.get("/api/routes/bicycle")
def bicycle(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict[str, object]:
    try:
        return bicycle_route(start_lat, start_lon, end_lat, end_lon)
    except SourceUnavailable as error:
        return {"code": "Unavailable", "routes": [], "error": str(error)}


@app.post("/api/geofences", status_code=201)
def create_geofence(payload: GeofenceInput) -> dict[str, object]:
    fence = Geofence(**payload.model_dump())
    store.save(fence)
    geofences[fence.name] = (fence, AutomationEngine(fence))
    return asdict(fence)


@app.get("/api/geofences")
def list_geofences() -> list[dict[str, object]]:
    return [asdict(fence) for fence, _ in geofences.values()]


@app.delete("/api/geofences/{name}")
def delete_geofence(name: str) -> dict[str, object]:
    deleted_from_store = store.delete(name)
    deleted_from_memory = geofences.pop(name, None) is not None
    if not (deleted_from_store or deleted_from_memory):
        raise HTTPException(status_code=404, detail="Geofence não encontrada")
    return {"status": "deleted", "name": name}


@app.get("/api/positions/history")
def position_history(limit: int = 100) -> list[dict[str, float]]:
    return [asdict(position) for position in store.list_positions(limit)]


@app.get("/api/map/features")
def map_features(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius: int = Query(default=500, ge=100, le=1500),
) -> dict[str, Any]:
    """Busca elementos cartográficos públicos do OpenStreetMap próximos a um ponto."""
    import httpx

    query = f"""
    [out:json][timeout:12];
    (
      nwr(around:{radius},{lat},{lng})["building"];
      nwr(around:{radius},{lat},{lng})["highway"];
      nwr(around:{radius},{lat},{lng})["public_transport"];
      nwr(around:{radius},{lat},{lng})["railway"];
      nwr(around:{radius},{lat},{lng})["amenity"];
      nwr(around:{radius},{lat},{lng})["shop"];
      nwr(around:{radius},{lat},{lng})["office"];
      nwr(around:{radius},{lat},{lng})["leisure"];
      nwr(around:{radius},{lat},{lng})["tourism"];
    );
    out center tags 100;
    """
    try:
        response = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=15.0,
            headers={"User-Agent": "SentinelAtlas/0.1 (public map features)"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Dados cartográficos temporariamente indisponíveis; tente novamente mais tarde.",
        ) from error

    items: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        center = element.get("center") or {}
        item_lat = element.get("lat", center.get("lat"))
        item_lng = element.get("lon", center.get("lon"))
        if item_lat is None or item_lng is None:
            continue
        if "building" in tags:
            kind = "building"
            name = tags.get("name") or tags.get("building", "Edificação sem nome")
        elif "highway" in tags:
            kind = "road"
            name = tags.get("name") or tags.get("highway", "Via sem nome")
        elif "public_transport" in tags or "railway" in tags:
            kind = "transport"
            name = tags.get("name") or tags.get("public_transport") or tags.get("railway", "Ponto de transporte")
        else:
            kind = "place"
            name = tags.get("name") or next(
                (tags[key] for key in ("amenity", "shop", "office", "leisure", "tourism") if key in tags),
                "Local mapeado",
            )
        items.append({
            "id": f"osm-{element.get('type', 'item')}-{element.get('id', '')}",
            "kind": kind,
            "name": str(name)[:160],
            "lat": float(item_lat),
            "lng": float(item_lng),
            "category": str(tags.get("building") or tags.get("highway") or tags.get("amenity") or tags.get("public_transport") or tags.get("railway") or tags.get("shop") or tags.get("tourism") or tags.get("leisure") or tags.get("office") or "mapa")[:80],
            "source": "OpenStreetMap",
        })
    return {
        "source": "OpenStreetMap / Overpass API",
        "updated_at": time.time(),
        "center": {"lat": lat, "lng": lng},
        "radius_meters": radius,
        "count": len(items),
        "counts": {
            "buildings": sum(item["kind"] == "building" for item in items),
            "roads": sum(item["kind"] == "road" for item in items),
            "transport": sum(item["kind"] == "transport" for item in items),
            "places": sum(item["kind"] == "place" for item in items),
        },
        "items": items,
    }


@app.get("/api/location/info")
def location_info(lat: float, lng: float) -> dict[str, Any]:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="Coordenadas geográficas inválidas")
    return get_location_info(lat, lng)


@app.post("/api/ai/analyze")
def ai_analyze(payload: AIAnalyzeInput) -> dict[str, Any]:
    # Se nenhuma geofence for fornecida na requisição, usa as cadastradas no backend
    fences = payload.geofences or [asdict(fence) for fence, _ in geofences.values()]
    return ai_analyzer.analyze_situation(payload.assets, fences)


@app.post("/api/ai/query")
def ai_query(payload: AIQueryInput) -> dict[str, Any]:
    ctx = payload.context
    if "geofences" not in ctx:
        ctx["geofences"] = [asdict(fence) for fence, _ in geofences.values()]
    return ai_analyzer.query_copilot(payload.question, ctx)


@app.websocket("/ws/positions")
async def positions(websocket: WebSocket) -> None:
    if settings.environment == "production" and not settings.api_token:
        await websocket.close(code=1013, reason="Autenticação da API não configurada")
        return

    authorization = websocket.headers.get("authorization", "")
    expected = f"Bearer {settings.api_token}"
    if settings.api_token and not hmac.compare_digest(authorization, expected):
        await websocket.close(code=1008, reason="Token de API inválido")
        return

    await websocket.accept()
    try:
        while True:
            payload = PositionInput.model_validate_json(await websocket.receive_text())
            position = Position(payload.latitude, payload.longitude, payload.timestamp or time.time())
            store.save_position(position)
            events = []
            for fence, engine in geofences.values():
                event = engine.process(position)
                events.append({
                    "geofence": fence.name,
                    "event": event,
                    "distance_meters": round(distance_meters(position, fence), 1),
                })
                if event:
                    send_webhook(settings.alert_webhook_url, {
                        "type": "geofence",
                        "name": fence.name,
                        "event": event,
                        "latitude": position.latitude,
                        "longitude": position.longitude,
                        "timestamp": position.timestamp,
                    })
            await websocket.send_text(json.dumps({"position": asdict(position), "events": events}))
    except WebSocketDisconnect:
        return


# Mantido por último para não interceptar as rotas da API e do WebSocket.
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")


