"""Clientes HTTP pequenos para fontes públicas de dados geoespaciais."""

from __future__ import annotations

import json
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SourceUnavailable(RuntimeError):
    pass


MAX_SOURCE_BYTES = 16 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


source_opener = build_opener(NoRedirect())


def _fetch_bytes(url: str, timeout: float) -> bytes:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
            raise ValueError("URL de fonte inválida")
        request = Request(url, headers={"User-Agent": "Sentinel-Atlas/0.1", "Accept-Encoding": "identity"})
        with source_opener.open(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > MAX_SOURCE_BYTES:
                raise ValueError("Tamanho anunciado acima do limite")
            data = response.read(MAX_SOURCE_BYTES + 1)
            if len(data) > MAX_SOURCE_BYTES:
                raise ValueError("Resposta acima do limite")
            return data
    except (OSError, ValueError) as error:
        raise SourceUnavailable("Fonte externa indisponível ou resposta inválida") from error


def fetch_json(url: str, timeout: float = 10) -> object:
    data = _fetch_bytes(url, timeout)
    try:
        return json.loads(data)
    except (ValueError, RecursionError) as error:
        raise SourceUnavailable("Resposta JSON inválida") from error


def fetch_text(url: str, timeout: float = 10) -> str:
    try:
        return _fetch_bytes(url, timeout).decode("utf-8")
    except UnicodeDecodeError as error:
        raise SourceUnavailable("Resposta de texto inválida") from error


def parse_tle_text(payload: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    records = []
    for index in range(0, len(lines) - 2, 3):
        name, line1, line2 = lines[index:index + 3]
        if line1.startswith("1 ") and line2.startswith("2 "):
            records.append({"OBJECT_NAME": name, "TLE_LINE1": line1, "TLE_LINE2": line2})
    return records


def fetch_celestrak(url: str) -> list[dict[str, object]]:
    payload = fetch_json(url)
    if not isinstance(payload, list):
        raise SourceUnavailable("Resposta inválida do CelesTrak")
    return [item for item in payload if isinstance(item, dict)]


def fetch_opensky(url: str = "https://opensky-network.org/api/states/all") -> dict[str, object]:
    payload = fetch_json(url)
    if not isinstance(payload, dict):
        raise SourceUnavailable("Resposta inválida do OpenSky")
    return payload
