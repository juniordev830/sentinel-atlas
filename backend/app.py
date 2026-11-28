"""API HTTP/WebSocket do Projeto Sentinel Atlas."""

from __future__ import annotations

import asyncio
import json
import math
import hmac
import os
import sys
from secrets import token_urlsafe
import time
from urllib.parse import urlsplit
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Query, Response
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from python.gps_core import AutomationEngine, Geofence, Position, distance_meters  # noqa: E402
from python.settings import Settings  # noqa: E402
from backend.storage import GeofenceStore  # noqa: E402
from backend.source_clients import SourceUnavailable, fetch_celestrak, fetch_json, fetch_opensky, fetch_text, parse_tle_text  # noqa: E402
from backend.alerts import send_webhook  # noqa: E402
from backend.routing import bicycle_route  # noqa: E402
from backend.orbits import propagate_tle  # noqa: E402
from backend.ai import GeoINTAnalyzer  # noqa: E402
from backend.location import get_location_info  # noqa: E402
from backend.geo_layers import catalog as geoint_catalog, fetch_layer as geoint_fetch_layer  # noqa: E402



def validate_analysis_items(items, *, fences=False):
    import math
    if not isinstance(items, list) or len(items) > (500 if fences else 1000):
        raise ValueError("Lista de análise inválida ou excessiva")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Cada item deve ser um objeto")
        lat = item.get("latitude", item.get("lat"))
        lon = item.get("longitude", item.get("lon"))
        for value, bound in ((lat, 90), (lon, 180)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > bound:
                raise ValueError("Coordenadas inválidas")
        if fences:
            radius = item.get("radius_meters", 1000)
            if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(radius) or not 0 < radius <= 1000000:
                raise ValueError("Raio inválido")
        for key in ("name", "callsign", "id", "type"):
            if key in item and (not isinstance(item[key], str) or len(item[key]) > 160):
                raise ValueError("Identificador inválido")
        for key in ("speed", "velocity"):
            if key in item:
                value = item[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError("Velocidade inválida")
    return items

class AIAnalyzeInput(BaseModel):
    assets: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)
    geofences: list[dict[str, Any]] = Field(default_factory=list, max_length=500)

    @field_validator("assets")
    @classmethod
    def validate_assets(cls, values):
        return validate_analysis_items(values)

    @field_validator("geofences")
    @classmethod
    def validate_fences(cls, values):
        return validate_analysis_items(values, fences=True)


class AIQueryInput(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def validate_context(cls, value):
        validate_analysis_items(value.get("assets", []))
        validate_analysis_items(value.get("geofences", []), fences=True)
        return value


class GeofenceInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(gt=0, le=1_000_000)


class PositionInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timestamp: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class SessionLoginInput(BaseModel):
    token: str = Field(min_length=1, max_length=512)



app = FastAPI(title="Sentinel Atlas GPS API", version="0.1.0")
settings = Settings.from_environment()
ai_analyzer = GeoINTAnalyzer()
store = GeofenceStore(os.getenv("SENTINEL_DB_PATH", str(ROOT / ".data" / "sentinel.sqlite3")))
geofences: dict[str, tuple[Geofence, AutomationEngine]] = {}
for saved_fence in store.list():
    geofences[saved_fence.name] = (saved_fence, AutomationEngine(saved_fence))


SESSION_COOKIE_NAME = "sentinel_session"
SESSION_TTL_SECONDS = 60 * 60


LOGIN_WINDOW_SECONDS = 60
LOGIN_ATTEMPTS_PER_WINDOW = 10
MAX_LOGIN_CLIENTS = 4096
MAX_LOGIN_ATTEMPTS = 120
MAX_POSITION_SOCKETS = 64
WS_SESSION_CHECK_SECONDS = 5
WS_POSITION_WINDOW_SECONDS = 1
MAX_WS_POSITIONS_PER_WINDOW = 5

_login_buckets: dict[str, tuple[int, int]] = {}
_login_window = -1
_login_total = 0
_socket_slots = asyncio.BoundedSemaphore(MAX_POSITION_SOCKETS)


def _allow_login(address: str) -> bool:
    # Called on the event loop before request body parsing.
    global _login_window, _login_total
    window = int(time.monotonic() / LOGIN_WINDOW_SECONDS)
    if window != _login_window:
        _login_buckets.clear()
        _login_window = window
        _login_total = 0
    if _login_total >= MAX_LOGIN_ATTEMPTS:
        return False
    if address not in _login_buckets and len(_login_buckets) >= MAX_LOGIN_CLIENTS:
        return False
    _, count = _login_buckets.get(address, (window, 0))
    if count >= LOGIN_ATTEMPTS_PER_WINDOW:
        return False
    _login_total += 1
    _login_buckets[address] = (window, count + 1)
    return True


def _session_digest(value: str | None) -> str | None:
    if not value or len(value) != 43 or not value.isascii() or not settings.api_token:
        return None
    return hmac.new(settings.api_token.encode("utf-8"), value.encode("ascii"), "sha256").hexdigest()


def _valid_session_cookie(value: str | None) -> bool:
    digest = _session_digest(value)
    return digest is not None and store.session_valid(digest, int(time.time()))


def _is_same_origin(origin: str | None, host: str | None, scheme: str) -> bool:
    if not origin or not host:
        return False
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    expected_scheme = "https" if scheme in {"https", "wss"} else "http"
    return parsed.scheme == expected_scheme and parsed.netloc.lower() == host.lower()


@app.middleware("http")
async def optional_token_auth(request: Request, call_next):
    path = request.url.path
    if path == "/api/session" and request.method == "POST":
        address = request.client.host if request.client else "unknown"
        if not _allow_login(address):
            return JSONResponse(
                status_code=429, content={"detail": "Muitas tentativas de autenticação"},
                headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)},
            )
    public_paths = {"/api/health", "/api/public-config", "/api/session", "/api/session/logout"}
    authorization = request.headers.get("authorization", "")
    bearer_valid = bool(settings.api_token) and hmac.compare_digest(
        authorization.encode("utf-8"), f"Bearer {settings.api_token}".encode("utf-8")
    )
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session_valid = bool(session_cookie) and not bearer_valid and await asyncio.to_thread(
        _valid_session_cookie, session_cookie,
    )

    if path == "/" and settings.api_token and not (bearer_valid or session_valid):
        return RedirectResponse(url="/login", status_code=303)

    protected_path = path.startswith("/api/") and path not in public_paths
    if protected_path:
        if not settings.api_token:
            if settings.environment == "production":
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Autenticação da API não configurada"},
                )
        elif not (bearer_valid or session_valid):
            return JSONResponse(status_code=401, content={"detail": "Autenticação necessária"})
        elif session_valid and not bearer_valid and request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not _is_same_origin(
                request.headers.get("origin"),
                request.headers.get("host"),
                request.url.scheme,
            ):
                return JSONResponse(status_code=403, content={"detail": "Origem da requisição inválida"})

    return await call_next(request)


@app.get("/login", response_class=HTMLResponse)
def browser_login_page() -> str:
    """Página mínima para trocar o token administrativo por um cookie de sessão."""
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#070b16">
  <title>Entrar · Sentinel Atlas</title>
  <style>
    *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#050811;color:#e2e8f0;font:16px system-ui,sans-serif}
    main{width:min(92vw,420px);padding:32px;border:1px solid #164e63;border-radius:18px;background:#0b1221;box-shadow:0 20px 70px #0008}
    h1{margin:0 0 8px;color:#67e8f9;font-size:1.45rem}p{color:#94a3b8;line-height:1.5}
    label{display:block;margin:22px 0 8px}input{width:100%;padding:13px;border:1px solid #334155;border-radius:9px;background:#020617;color:#fff;font:inherit}
    button{width:100%;margin-top:14px;padding:13px;border:0;border-radius:9px;background:#0891b2;color:white;font-weight:700;font:inherit;cursor:pointer}
    #status{min-height:24px;margin-top:14px;color:#fca5a5;font-size:.9rem}small{color:#64748b}
  </style>
</head>
<body>
  <main>
    <h1>Sentinel Atlas</h1>
    <p>Entre com o token administrativo configurado no servidor. Ele será trocado por uma sessão temporária protegida por cookie HttpOnly.</p>
    <form id="login-form">
      <label for="token">Token de acesso</label>
      <input id="token" name="token" type="password" autocomplete="current-password" required maxlength="512">
      <button type="submit">Entrar no painel</button>
    </form>
    <button id="logout" type="button" style="background:#334155">Encerrar sessão neste navegador</button>
    <div id="status" role="status" aria-live="polite"></div>
    <small>A sessão expira automaticamente após 1 hora. Não compartilhe seu token.</small>
  </main>
  <script>
    const status = document.getElementById('status');
    document.getElementById('login-form').addEventListener('submit', async event => {
      event.preventDefault();
      const tokenInput = document.getElementById('token');
      status.textContent = 'Validando acesso…';
      try {
        const response = await fetch('/api/session', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({token: tokenInput.value})
        });
        if (!response.ok) throw new Error(response.status === 401 ? 'Token inválido.' : 'Não foi possível iniciar a sessão.');
        tokenInput.value = '';
        location.replace('/');
      } catch (error) {
        status.textContent = error.message;
      }
    });
    document.getElementById('logout').addEventListener('click', async () => {
      try {
        await fetch('/api/session/logout', {method:'POST', credentials:'same-origin'});
        status.textContent = 'Sessão encerrada.';
      } catch {
        status.textContent = 'Não foi possível encerrar a sessão.';
      }
    });
  </script>
</body>
</html>"""


@app.post("/api/session")
def create_browser_session(payload: SessionLoginInput, request: Request, response: Response) -> dict[str, object]:
    if not settings.api_token:
        raise HTTPException(status_code=503, detail="Autenticação da API não configurada")
    if not _is_same_origin(request.headers.get("origin"), request.headers.get("host"), request.url.scheme):
        raise HTTPException(status_code=403, detail="Origem da requisição inválida")
    if not hmac.compare_digest(payload.token.encode("utf-8"), settings.api_token.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Token inválido")
    now = int(time.time())
    session_id = token_urlsafe(32)
    digest = _session_digest(session_id)
    if digest is None or not store.create_session(digest, now, now + SESSION_TTL_SECONDS):
        raise HTTPException(status_code=503, detail="Limite de sessões ativas atingido")
    old_digest = _session_digest(request.cookies.get(SESSION_COOKIE_NAME))
    if old_digest:
        store.revoke_session(old_digest)
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "expires_in": SESSION_TTL_SECONDS}


@app.post("/api/session/logout")
def end_browser_session(request: Request, response: Response) -> dict[str, bool]:
    origin = request.headers.get("origin")
    if origin and not _is_same_origin(origin, request.headers.get("host"), request.url.scheme):
        raise HTTPException(status_code=403, detail="Origem da requisição inválida")
    digest = _session_digest(request.cookies.get(SESSION_COOKIE_NAME))
    if digest:
        store.revoke_session(digest)
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
    )
    return {"authenticated": False}


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


@app.get("/api/geoint/layers")
def geoint_layers() -> dict[str, Any]:
    """Catálogo das 16 fontes, sem efetuar consultas pagas nem vazar chaves."""
    return {"count": 16, "layers": geoint_catalog()}


@app.get("/api/geoint/layers/{layer_id}")
def geoint_layer_data(
    layer_id: str,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    uf: str = Query(default="", max_length=2),
) -> dict[str, Any]:
    """Consulta explícita e limitada por fonte; o globo nunca inicia varreduras em massa."""
    try:
        return geoint_fetch_layer(layer_id, lat, lng, region=uf)
    except KeyError:
        raise HTTPException(status_code=404, detail="Camada inexistente") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="Parâmetros geográficos inválidos") from None


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
        if not isinstance(payload, dict) or ("states" in payload and payload["states"] is not None and not isinstance(payload["states"], list)):
            raise SourceUnavailable("Resposta inválida do OpenSky")
        states = payload.get("states") or []
        return {"source": "OpenSky", "count": len(states), "items": states[:100]}
    except SourceUnavailable as error:
        return {"source": "OpenSky", "count": 0, "items": [], "error": str(error)}


@app.get("/api/routes/bicycle")
def bicycle(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict[str, object]:
    try:
        return bicycle_route(start_lat, start_lon, end_lat, end_lon)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SourceUnavailable as error:
        return JSONResponse(
            status_code=503,
            content={"code": "Unavailable", "routes": [], "error": str(error)},
        )


@app.post("/api/geofences", status_code=201)
def create_geofence(payload: GeofenceInput) -> dict[str, object]:
    fence = Geofence(**payload.model_dump())
    store.save(fence)
    geofences[fence.name] = (fence, AutomationEngine(fence))
    return asdict(fence)


@app.get("/api/geofences")
def list_geofences() -> list[dict[str, object]]:
    return [asdict(fence) for fence, _ in geofences.copy().values()]


@app.delete("/api/geofences/{name}")
def delete_geofence(name: str) -> dict[str, object]:
    deleted_from_store = store.delete(name)
    deleted_from_memory = geofences.pop(name, None) is not None
    if not (deleted_from_store or deleted_from_memory):
        raise HTTPException(status_code=404, detail="Geofence não encontrada")
    return {"status": "deleted", "name": name}


@app.get("/api/positions/history")
def position_history(
    limit: int = 100,
    start: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    end: float | None = Query(default=None, ge=0, allow_inf_nan=False),
) -> list[dict[str, float]]:
    """Histórico local autorizado, com intervalo temporal inclusivo opcional."""
    try:
        positions = store.list_positions(limit, start=start, end=end)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return [asdict(position) for position in positions]


def valid_map_coordinate(value: Any, bound: int) -> bool:
    return (type(value) in (int, float) and -bound <= value <= bound
            and math.isfinite(value))


@app.get("/api/map/features")
def map_features(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius: int = Query(default=500, ge=100, le=1500),
) -> dict[str, Any]:
    """Busca elementos cartográficos públicos do OpenStreetMap próximos a um ponto."""
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
        payload = fetch_json(
            "https://overpass-api.de/api/interpreter", timeout=15, max_bytes=1_500_000,
            data={"data": query},
            headers={"User-Agent": "SentinelAtlas/0.1 (public map features)"},
        )
    except SourceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Dados cartográficos temporariamente indisponíveis; tente novamente mais tarde.",
        ) from error

    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise HTTPException(status_code=503, detail="Resposta cartográfica inválida.")
    items: list[dict[str, Any]] = []
    for element in payload["elements"][:100]:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags") or {}
        center = element.get("center") or {}
        if not isinstance(tags, dict) or not isinstance(center, dict):
            continue
        item_lat = element.get("lat", center.get("lat"))
        item_lng = element.get("lon", center.get("lon"))
        if not valid_map_coordinate(item_lat, 90) or not valid_map_coordinate(item_lng, 180):
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
    fences = payload.geofences or [asdict(fence) for fence, _ in geofences.copy().values()]
    return ai_analyzer.analyze_situation(payload.assets, fences)


@app.post("/api/ai/query")
def ai_query(payload: AIQueryInput) -> dict[str, Any]:
    ctx = payload.context
    if "geofences" not in ctx:
        ctx["geofences"] = [asdict(fence) for fence, _ in geofences.copy().values()]
    return ai_analyzer.query_copilot(payload.question, ctx)


async def accept_position_socket(websocket: WebSocket) -> bool:
    if settings.environment == "production" and not settings.api_token:
        await websocket.close(code=1013, reason="Autenticação da API não configurada")
        return False

    authorization = websocket.headers.get("authorization", "")
    bearer_valid = bool(settings.api_token) and hmac.compare_digest(
        authorization.encode("utf-8"), f"Bearer {settings.api_token}".encode("utf-8")
    )
    session_cookie = websocket.cookies.get(SESSION_COOKIE_NAME)
    session_valid = bool(session_cookie) and not bearer_valid and await asyncio.to_thread(_valid_session_cookie, session_cookie)
    if settings.api_token and not (bearer_valid or session_valid):
        await websocket.close(code=1008, reason="Autenticação necessária")
        return False
    if session_valid and not bearer_valid:
        host = websocket.headers.get("host")
        origin = websocket.headers.get("origin")
        if not _is_same_origin(origin, host, websocket.url.scheme):
            await websocket.close(code=1008, reason="Origem da conexão inválida")
            return False

    if _socket_slots.locked():
        await websocket.close(code=1013, reason="Limite de conexões atingido")
        return False
    await _socket_slots.acquire()
    websocket.state.session_cookie = session_cookie if session_valid else None
    try:
        await websocket.accept()
    except BaseException:
        _socket_slots.release()
        raise
    return True


async def _socket_session_valid(websocket: WebSocket) -> bool:
    browser_session = websocket.state.session_cookie
    if browser_session is None or await asyncio.to_thread(_valid_session_cookie, browser_session):
        return True
    await websocket.close(code=1008, reason="Sessão expirada ou revogada")
    return False


@app.websocket("/ws/demo/geofence")
async def demo_geofence(websocket: WebSocket) -> None:
    if not await accept_position_socket(websocket):
        return
    fence = Geofence("Área demonstrativa", -5.79, -35.20, 45_000)
    engine = AutomationEngine(fence)
    try:
        for index, longitude in enumerate((-36.00, -35.42, -35.20, -34.40)):
            if index:
                await asyncio.sleep(0.85)
            if not await _socket_session_valid(websocket):
                return
            position = Position(fence.latitude, longitude, time.time())
            await websocket.send_json({
                "position": asdict(position), "fence": asdict(fence),
                "event": engine.process(position), "distance_meters": round(distance_meters(position, fence)),
            })
        await websocket.close()
    except (WebSocketDisconnect, OSError):
        return
    finally:
        _socket_slots.release()


@app.websocket("/ws/positions")
async def positions(websocket: WebSocket) -> None:
    if not await accept_position_socket(websocket):
        return
    window_start = time.monotonic()
    count = 0
    try:
        while await _socket_session_valid(websocket):
            try:
                incoming = await asyncio.wait_for(websocket.receive(), timeout=WS_SESSION_CHECK_SECONDS)
            except TimeoutError:
                continue
            if incoming["type"] == "websocket.disconnect":
                break
            message = incoming.get("text")
            if message is None:
                await websocket.close(code=1003, reason="Apenas mensagens de texto são aceitas")
                return
            if len(message.encode("utf-8")) > 16_384:
                await websocket.close(code=1009, reason="Mensagem excede o limite de 16 KiB")
                return
            now = time.monotonic()
            if now - window_start >= WS_POSITION_WINDOW_SECONDS:
                window_start, count = now, 0
            count += 1
            if count > MAX_WS_POSITIONS_PER_WINDOW:
                await websocket.close(code=1008, reason="Limite de frequência excedido")
                return
            if not await _socket_session_valid(websocket):
                return
            try:
                payload = PositionInput.model_validate_json(message)
            except ValidationError:
                await websocket.close(code=1008, reason="Posição inválida")
                return
            position = Position(payload.latitude, payload.longitude, payload.timestamp if payload.timestamp is not None else time.time())
            await asyncio.to_thread(store.save_position, position)
            events = []
            notifications = []
            for fence, engine in geofences.copy().values():
                event = engine.process(position)
                events.append({
                    "geofence": fence.name,
                    "event": event,
                    "distance_meters": round(distance_meters(position, fence), 1),
                })
                if event:
                    notifications.append({
                        "type": "geofence",
                        "name": fence.name,
                        "event": event,
                        "latitude": position.latitude,
                        "longitude": position.longitude,
                        "timestamp": position.timestamp,
                    })
            if settings.alert_webhook_url:
                for notification in notifications:
                    await asyncio.to_thread(send_webhook, settings.alert_webhook_url, notification)
            await websocket.send_text(json.dumps({"position": asdict(position), "events": events}))
    except (WebSocketDisconnect, OSError):
        return
    finally:
        _socket_slots.release()


# Mantido por último para não interceptar as rotas da API e do WebSocket.
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")


