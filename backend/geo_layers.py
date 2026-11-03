"""Catálogo transparente de 16 camadas geoespaciais: dados, previsão e integrações opcionais.

Nenhum dado demo é anunciado como fonte real. Consultas apenas quando solicitadas,
com endpoints fixos ou URLs configuradas pelo operador e cache de memória limitado.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx

from backend.source_clients import SourceUnavailable, fetch_opensky, parse_tle_text, fetch_text
from backend.orbits import propagate_tle

# id, nome, provedor, classe, requisito, explicação, documentação
LAYERS = (
    ("imagery", "Imagens de satélite", "NASA Worldview/GIBS", "image_view", None, "Imagens de observações por data, não vídeo ao vivo.", "https://worldview.earthdata.nasa.gov/"),
    ("aircraft", "Aeronaves", "OpenSky Network", "observation", None, "Cobertura variável e limites do provedor.", "https://openskynetwork.github.io/opensky-api/"),
    ("vessels", "Navios e atividade marítima", "Global Fishing Watch", "historical_event", "GFW_API_TOKEN", "Eventos históricos, não rastreamento AIS global ao vivo; uso não comercial.", "https://globalfishingwatch.org/our-apis/documentation/"),
    ("wildfires", "Focos de calor", "NASA FIRMS", "satellite_detection", "FIRMS_MAP_KEY", "Detecções por passagem orbital, não incêndios confirmados.", "https://firms.modaps.eosdis.nasa.gov/api/"),
    ("earthquakes", "Terremotos", "USGS", "observation", None, "Feed recente; medições podem ser revisadas.", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php"),
    ("weather", "Tempo e previsão", "Open-Meteo", "model", None, "Dados meteorológicos estimados/modelados para coordenadas.", "https://open-meteo.com/en/docs"),
    ("extreme_events", "Eventos naturais", "NASA EONET", "event", None, "Eventos catalogados com atualizações não instantâneas.", "https://eonet.gsfc.nasa.gov/docs/v3"),
    ("orbital", "Satélites em órbita", "CelesTrak/SGP4", "prediction", None, "Posição orbital calculada a partir de elementos TLE.", "https://celestrak.org/NORAD/documentation/"),
    ("urban", "Prédios, vias e locais", "OpenStreetMap/Overpass", "mapped", None, "Objetos cadastrados pela comunidade, cobertura desigual.", "https://wiki.openstreetmap.org/wiki/Overpass_API"),
    ("traffic", "Trânsito", "Google Maps", "map_view", "GOOGLE_MAPS_API_KEY", "Somente camada visual licenciada no mapa oficial Google.", "https://developers.google.com/maps/documentation/javascript/trafficlayer"),
    ("transit", "Transporte público", "Feed GeoJSON do operador", "observation", "SENTINEL_TRANSIT_GEOJSON_URL", "Depende de feed regional autorizado; não é GTFS-RT genérico.", "https://gtfs.org/documentation/realtime/"),
    ("hydrology", "Rios e reservatórios", "Feed GeoJSON/ANA regional", "observation", "SENTINEL_HYDRO_GEOJSON_URL", "Depende de serviço regional com coordenadas e licença de acesso.", "https://www.snirh.gov.br/hidroweb/"),
    ("air_quality", "Qualidade do ar", "Open-Meteo", "model", None, "Modelo de qualidade do ar, não sensor medindo no local.", "https://open-meteo.com/en/docs/air-quality-api"),
    ("municipalities", "Municípios brasileiros", "IBGE", "registry", None, "Cadastro oficial por UF; seleção do estado obrigatória.", "https://servicodados.ibge.gov.br/api/docs/localidades"),
    ("terrain", "Elevação do terreno", "Copernicus DEM/Open-Meteo", "terrain_model", None, "Estimativa de elevação em modelo digital de terreno.", "https://open-meteo.com/en/docs/elevation-api"),
    ("alerts", "Alertas públicos", "Feed GeoJSON oficial regional", "observation", "SENTINEL_ALERTS_GEOJSON_URL", "Depende de feed público regional cadastrado pelo operador.", "https://www.gov.br/defesacivil/pt-br"),
)
LAYER_INDEX = {row[0]: row for row in LAYERS}
REGIONAL_KEYS = {"SENTINEL_TRANSIT_GEOJSON_URL", "SENTINEL_HYDRO_GEOJSON_URL", "SENTINEL_ALERTS_GEOJSON_URL"}
_cache: dict[tuple, tuple[float, dict]] = {}
_lock = threading.Lock()


def catalog() -> list[dict]:
    """Retorna catálogo sem consultar serviços externos nem expor segredos."""
    result = []
    for key, name, provider, nature, env_key, detail, docs in LAYERS:
        configured = not env_key or bool(os.getenv(env_key, "").strip())
        if nature in ("image_view", "map_view"):
            status = "external_view" if configured else "requires_configuration"
        elif key == "municipalities":
            status = "needs_region"
        else:
            status = "ready" if configured else "requires_configuration"
        result.append({
            "id": key, "name": name, "provider": provider, "data_kind": nature,
            "status": status, "requirement": env_key if not configured else None,
            "description": detail, "documentation": docs,
        })
    return result


def _coord(lat: float, lng: float) -> tuple[float, float]:
    if (not math.isfinite(lat) or not math.isfinite(lng)
            or not -90 <= lat <= 90 or not -180 <= lng <= 180):
        raise ValueError("Coordenadas inválidas")
    return round(lat, 5), round(lng, 5)


def _request(url: str, *, params=None, headers=None, text=False):
    # Endereços fornecidos pelos operadores devem ser HTTPS e possuir domínio.
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SourceUnavailable("URL do provedor inválida: HTTPS é obrigatório.")
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            # Transfere no máximo 1,5 MB descomprimidos: não baixar todo o corpo
            # antes de aplicar o limite (feeds externos podem ser gigantes).
            with client.stream("GET", url, params=params, headers={
                "User-Agent": "SentinelAtlas/0.4 (geospatial public data)",
                **(headers or {}),
            }) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_bytes(chunk_size=65_536):
                    if len(payload) + len(chunk) > 1_500_000:
                        raise SourceUnavailable("Resposta maior que o limite permitido.")
                    payload.extend(chunk)
                body = bytes(payload)
                return body.decode(response.encoding or "utf-8") if text else json.loads(body)
    except (httpx.HTTPError, ValueError) as error:
        raise SourceUnavailable("Serviço externo indisponível ou sem autorização.") from error


def _point(key, name, lat, lng, description="", timestamp=None, data_kind=None):
    try:
        lat, lng = _coord(float(lat), float(lng))
    except (TypeError, ValueError, OverflowError):
        return None
    return {
        "id": str(key)[:120], "title": str(name)[:180],
        "lat": lat, "lng": lng, "detail": str(description)[:350],
        "timestamp": timestamp, "data_kind": data_kind,
    }


def _number(value, minimum=None, maximum=None):
    """Somente medições numéricas finitas para painéis, nunca valores inventados."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if minimum is not None and number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _geojson(payload, layer):
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise SourceUnavailable("GeoJSON incompatível com o contrato de FeatureCollection.")
    points = []
    for index, feature in enumerate(payload.get("features", [])[:100]):
        if not isinstance(feature, dict):
            continue
        geom = feature.get("geometry") or {}
        coord = geom.get("coordinates") or []
        if geom.get("type") == "Point" and len(coord) >= 2:
            props = feature.get("properties") or {}
            if not isinstance(props, dict):
                props = {}
            point = _point(
                f"{layer}-{index}", props.get("title") or props.get("name") or layer,
                coord[1], coord[0], props.get("description") or props.get("category") or "",
                props.get("date") or props.get("time")
            )
            if point:
                points.append(point)
    return points


def _run_layer(layer, lat, lng, region):
    if layer == "imagery":
        return [], "https://worldview.earthdata.nasa.gov/"
    if layer == "traffic":
        return [], None  # Google Maps é exibido pelo JavaScript oficial.
    if layer == "earthquakes":
        data = _request("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson")
        if not isinstance(data, dict):
            raise SourceUnavailable("Formato USGS inválido")
        points = []
        for feature in data.get("features", [])[:75]:
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coord = geometry.get("coordinates") or []
            if len(coord) >= 2:
                item = _point("usgs-" + str(feature.get("id", "")),
                              properties.get("title", "Terremoto"),
                              coord[1], coord[0],
                              "Magnitude: " + str(properties.get("mag", "?")),
                              properties.get("time"))
                if item:
                    points.append(item)
        return points, None
    if layer == "weather":
        data = _request("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lng,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,cloud_cover",
            "timezone": "UTC",
        })
        current = data.get("current", {})
        p = _point("weather", "Condições meteorológicas (modelo)", lat, lng,
                   "Temperatura " + str(current.get("temperature_2m", "?")) +
                   " °C · Umidade " + str(current.get("relative_humidity_2m", "?")) +
                   "% · Vento " + str(current.get("wind_speed_10m", "?")) + " km/h",
                   current.get("time"), "model")
        if p:
            p["measurements"] = {
                "temperature_c": _number(current.get("temperature_2m"), -100, 70),
                "humidity_pct": _number(current.get("relative_humidity_2m"), 0, 100),
                "wind_speed_kmh": _number(current.get("wind_speed_10m"), 0, 500),
                "wind_direction_deg": _number(current.get("wind_direction_10m"), 0, 360),
                "precipitation_mm": _number(current.get("precipitation"), 0, 5000),
                "cloud_cover_pct": _number(current.get("cloud_cover"), 0, 100),
            }
        return ([p] if p else []), None
    if layer == "air_quality":
        data = _request("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude": lat, "longitude": lng, "current": "pm2_5,pm10,us_aqi", "timezone": "UTC"
        })
        current = data.get("current", {})
        p = _point("air", "Qualidade do ar (modelo)", lat, lng,
                   "PM2.5: " + str(current.get("pm2_5", "?")) +
                   " µg/m³ · PM10: " + str(current.get("pm10", "?")) +
                   " µg/m³ · AQI EUA: " + str(current.get("us_aqi", "?")),
                   current.get("time"), "model")
        if p:
            p["measurements"] = {
                "pm25_ugm3": _number(current.get("pm2_5"), 0, 5000),
                "pm10_ugm3": _number(current.get("pm10"), 0, 5000),
                "us_aqi": _number(current.get("us_aqi"), 0, 500),
            }
        return ([p] if p else []), None
    if layer == "terrain":
        data = _request("https://api.open-meteo.com/v1/elevation", params={"latitude": lat, "longitude": lng})
        heights = data.get("elevation") or []
        if not heights:
            raise SourceUnavailable("Modelo de elevação sem cobertura neste ponto")
        p = _point("terrain", "Elevação estimada do terreno", lat, lng,
                   str(heights[0]) + " m acima do nível do mar (Copernicus DEM)", None, "terrain_model")
        return ([p] if p else []), None
    if layer == "extreme_events":
        data = _request("https://eonet.gsfc.nasa.gov/api/v3/events", params={"status": "open", "limit": 50})
        points = []
        for event in data.get("events", [])[:50]:
            coords = (event.get("geometry") or [])[-1:]  # coordenada mais recente
            if not coords:
                continue
            item = coords[0]
            ll = item.get("coordinates") or []
            if item.get("type") == "Point" and len(ll) >= 2:
                category = ", ".join(c.get("title", "") for c in event.get("categories", []))
                p = _point(event.get("id", "eonet"), event.get("title", "Evento"), ll[1], ll[0],
                           category, item.get("date"))
                if p:
                    points.append(p)
        return points, None
    if layer == "aircraft":
        # Recorte reduz o volume de dados e limita custo/uso.
        params = {"lamin": max(-90, lat - 1), "lamax": min(90, lat + 1),
                  "lomin": max(-180, lng - 1), "lomax": min(180, lng + 1)}
        data = _request("https://opensky-network.org/api/states/all", params=params)
        points = []
        for state in (data.get("states") or [])[:70]:
            if not isinstance(state, list) or len(state) < 8:
                continue
            p = _point("air-" + str(state[0]), state[1] or state[0], state[6], state[5],
                       "Altitude barométrica: " + str(state[7]) + " m",
                       data.get("time"))
            if p:
                points.append(p)
        return points, None
    if layer == "orbital":
        text = fetch_text("https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=tle", timeout=8)
        records = parse_tle_text(text)
        points = []
        for record in records[:1]:
            try:
                orbit = propagate_tle(record["OBJECT_NAME"], record["TLE_LINE1"], record["TLE_LINE2"])
                p = _point("iss", "ISS (posição orbital estimada)",
                           orbit.get("latitude", orbit.get("lat")),
                           orbit.get("longitude", orbit.get("lng")),
                           "Efeméride SGP4, não rastreamento observacional instantâneo",
                           None, "prediction")
                if p:
                    points.append(p)
            except (RuntimeError, ValueError):
                continue
        return points, None
    if layer == "urban":
        query = (
            '[out:json][timeout:10];(nwr(around:700,' + str(lat) + ',' + str(lng) +
            ')["building"];nwr(around:700,' + str(lat) + ',' + str(lng) +
            ')["amenity"];nwr(around:700,' + str(lat) + ',' + str(lng) +
            ')["public_transport"];);out center tags 60;'
        )
        raw = _request("https://overpass-api.de/api/interpreter", params={"data": query})
        points = []
        for item in raw.get("elements", [])[:60]:
            tags = item.get("tags") or {}
            center = item.get("center") or {}
            p = _point("osm-" + str(item.get("id", "")),
                       tags.get("name") or tags.get("amenity") or tags.get("building") or "Lugar mapeado",
                       item.get("lat", center.get("lat")),
                       item.get("lon", center.get("lon")),
                       tags.get("amenity") or tags.get("building") or "OSM")
            if p:
                points.append(p)
        return points, None
    if layer == "municipalities":
        if not region or not re.fullmatch(r"[A-Z]{2}", region):
            return [], None
        data = _request("https://servicodados.ibge.gov.br/api/v1/localidades/estados/" + region + "/municipios")
        return [{
            "id": "ibge-" + str(city["id"]), "title": str(city["nome"]), "lat": None, "lng": None,
            "detail": "Código IBGE: " + str(city["id"]), "timestamp": None, "data_kind": "registry",
        } for city in data[:60] if isinstance(city, dict) and "id" in city and "nome" in city], None
    if layer == "wildfires":
        # Formato CSV oficial FIRMS. O MAP_KEY não é enviado ao navegador.
        key = os.getenv("FIRMS_MAP_KEY", "").strip()
        west, east = max(-180, lng - 1), min(180, lng + 1)
        south, north = max(-90, lat - 1), min(90, lat + 1)
        url = ("https://firms.modaps.eosdis.nasa.gov/api/area/csv/" +
               key + "/VIIRS_SNPP_NRT/" +
               ",".join(str(x) for x in [west, south, east, north]) + "/1")
        raw = _request(url, text=True)
        points = []
        for idx, row in enumerate(csv.DictReader(io.StringIO(raw))):
            if idx >= 60:
                break
            p = _point("firms-" + str(idx), "Anomalia térmica / foco de calor",
                       row.get("latitude"), row.get("longitude"),
                       "Confiança: " + str(row.get("confidence", "não informada")),
                       row.get("acq_date"), "satellite_detection")
            if p:
                points.append(p)
        return points, None
    if layer == "vessels":
        token = os.getenv("GFW_API_TOKEN", "").strip()
        today = datetime.now(timezone.utc).date()
        data = _request("https://gateway.api.globalfishingwatch.org/v3/events",
                        params={
                            "datasets[0]": "public-global-port-visits-events:latest",
                            "start-date": (today - timedelta(days=14)).isoformat(),
                            "end-date": today.isoformat(), "limit": 30, "offset": 0,
                        }, headers={"Authorization": "Bearer " + token})
        points = []
        for i, event in enumerate(data.get("entries", data.get("events", []))[:30]):
            pos = event.get("position") or {}
            p = _point("gfw-" + str(event.get("id", i)),
                       "Evento portuário " + str(event.get("vessel", {}).get("name", "")),
                       pos.get("lat"), pos.get("lon"), "Registro histórico GFW",
                       event.get("start"), "historical_event")
            if p:
                points.append(p)
        return points, None
    if layer in ("transit", "hydrology", "alerts"):
        setting = dict(transit="SENTINEL_TRANSIT_GEOJSON_URL", hydrology="SENTINEL_HYDRO_GEOJSON_URL",
                       alerts="SENTINEL_ALERTS_GEOJSON_URL")[layer]
        return _geojson(_request(os.environ[setting]), layer), None
    raise KeyError(layer)


def fetch_layer(layer: str, lat: float, lng: float, *, region: str = "") -> dict:
    if layer not in LAYER_INDEX:
        raise KeyError("Camada desconhecida")
    lat, lng = _coord(lat, lng)
    region = region.upper().strip()
    if region and not re.fullmatch("[A-Z]{2}", region):
        raise ValueError("UF inválida")
    definition = next(row for row in catalog() if row["id"] == layer)
    state = definition["status"]
    if state == "requires_configuration":
        return {**definition, "items": [], "count": 0, "fetched_at": None}
    if state == "needs_region" and not region:
        return {**definition, "items": [], "count": 0, "fetched_at": None}
    if state == "external_view" and layer in ("imagery", "traffic"):
        return {**definition, "items": [], "count": 0, "fetched_at": None,
                "external_url": "https://worldview.earthdata.nasa.gov/" if layer == "imagery" else None}
    # Coordenadas já foram arredondadas a 5 casas em _coord. Um cache de
    # apenas 2 casas misturava pontos a centenas de metros de distância.
    key = (layer, lat, lng, region)
    with _lock:
        stored = _cache.get(key)
        if stored and stored[0] > time.monotonic():
            return {**stored[1], "cached": True}
    try:
        items, url = _run_layer(layer, lat, lng, region)
        result = {**definition, "status": "ok" if items else "empty",
                  "items": items[:75], "count": min(len(items), 75),
                  "fetched_at": datetime.now(timezone.utc).isoformat(),
                  "cached": False}
        if url:
            result["external_url"] = url
    except (SourceUnavailable, httpx.HTTPError, ValueError, TypeError, KeyError, RuntimeError, OSError):
        return {**definition, "status": "unavailable", "items": [],
                "count": 0, "fetched_at": None,
                "error": "Fonte não respondeu ou impôs restrição. Confira logs e documentação."}
    with _lock:
        if len(_cache) >= 128:
            _cache.clear()
        _cache[key] = (time.monotonic() + 300, result)
    return result
