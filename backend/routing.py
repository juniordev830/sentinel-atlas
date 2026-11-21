"""Rotas de bicicleta usando o serviço público OSRM."""

from __future__ import annotations

import math

from backend.source_clients import SourceUnavailable, fetch_json


def _validate_coordinate(value: float, limit: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not -limit <= value <= limit
    ):
        raise ValueError("Coordenadas inválidas: latitude deve estar entre -90 e 90 e longitude entre -180 e 180.")


def bicycle_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict[str, object]:
    """Obtém uma rota de bicicleta após validar as quatro coordenadas."""
    for latitude in (start_lat, end_lat):
        _validate_coordinate(latitude, 90)
    for longitude in (start_lon, end_lon):
        _validate_coordinate(longitude, 180)

    url = (
        "https://router.project-osrm.org/route/v1/bicycle/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    )
    payload = fetch_json(url)
    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        raise SourceUnavailable("Rota de bicicleta indisponível")
    return payload
