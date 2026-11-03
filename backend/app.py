"""API HTTP/WebSocket do Projeto Sentinel Atlas."""

from __future__ import annotations

import json
import hmac
import os
import sys
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
from backend.source_clients import SourceUnavailable, fetch_celestrak, fetch_opensky, fetch_text, parse_tle_text  # noqa: E402
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

# Métricas leves em memória para diagnosticar a API sem persistir dados de usuários.
_metrics_started_at = time.time()
_metrics_requests_total = 0
_metrics_status_counts: dict[str, int] = {}
_metrics_route_counts: dict[str, int] = {}


def _record_request(path: str, status_code: int, duration_ms: float) -> None:
    global _metrics_requests_total
    _metrics_requests_total += 1
    status_key = str(status_code)
    _metrics_status_counts[status_key] = _metrics_status_counts.get(status_key, 0) + 1
    route_key = path or "/"
    current = _metrics_route_counts.get(route_key, 0)
    _metrics_route_counts[route_key] = current + 1

for saved_fence in store.list():
    geofences[saved_fence.name] = (saved_fence, AutomationEngine(saved_fence))


SESSION_COOKIE_NAME = "sentinel_session"
SESSION_TTL_SECONDS = 60 * 60


def _session_signature(expires_at: int) -> str:
    if not settings.api_token:
        return ""
    message = f"sentinel-browser-session:{expires_at}".encode("utf-8")
    return hmac.new(settings.api_token.encode("utf-8"), message, "sha256").hexdigest()


def _create_session_cookie() -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    return f"{expires_at}.{_session_signature(expires_at)}"


def _valid_session_cookie(value: str | None) -> bool:
    if not value or not settings.api_token:
        return False
    try:
        expires_text, supplied_signature = value.split(".", 1)
        expires_at = int(expires_text)
    except (ValueError, TypeError):
        return False
    if expires_at <= int(time.time()):
        return False
    expected_signature = _session_signature(expires_at)
    return hmac.compare_digest(supplied_signature.encode("utf-8"), expected_signature.encode("utf-8"))


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
    public_paths = {"/api/health", "/api/public-config", "/api/session", "/api/session/logout"}
    authorization = request.headers.get("authorization", "")
    bearer_valid = bool(settings.api_token) and hmac.compare_digest(
        authorization.encode("utf-8"), f"Bearer {settings.api_token}".encode("utf-8")
    )
    session_valid = _valid_session_cookie(request.cookies.get(SESSION_COOKIE_NAME))

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

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        _record_request(path, 500, (time.perf_counter() - started) * 1000)
        raise
    _record_request(path, response.status_code, (time.perf_counter() - started) * 1000)
    return response


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
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_session_cookie(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "expires_in": SESSION_TTL_SECONDS}


@app.post("/api/session/logout")
def end_browser_session(response: Response) -> dict[str, bool]:
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


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    """Retorna contadores operacionais do processo sem expor tokens ou dados de posição."""
    return {
        "service": "Sentinel Atlas API",
        "uptime_seconds": round(max(0.0, time.time() - _metrics_started_at), 3),
        "requests_total": _metrics_requests_total,
        "responses_by_status": dict(sorted(_metrics_status_counts.items())),
        "requests_by_path": dict(sorted(_metrics_route_counts.items())),
    }


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
    bearer_valid = bool(settings.api_token) and hmac.compare_digest(
        authorization.encode("utf-8"), f"Bearer {settings.api_token}".encode("utf-8")
    )
    session_valid = _valid_session_cookie(websocket.cookies.get(SESSION_COOKIE_NAME))
    if settings.api_token and not (bearer_valid or session_valid):
        await websocket.close(code=1008, reason="Autenticação necessária")
        return
    if session_valid and not bearer_valid:
        host = websocket.headers.get("host")
        origin = websocket.headers.get("origin")
        if not _is_same_origin(origin, host, websocket.url.scheme):
            await websocket.close(code=1008, reason="Origem da conexão inválida")
            return

    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            if len(message.encode("utf-8")) > 16_384:
                await websocket.close(code=1009, reason="Mensagem excede o limite de 16 KiB")
                return
            try:
                payload = PositionInput.model_validate_json(message)
            except ValidationError:
                await websocket.close(code=1008, reason="Posição inválida")
                return
            position = Position(payload.latitude, payload.longitude, payload.timestamp if payload.timestamp is not None else time.time())
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


