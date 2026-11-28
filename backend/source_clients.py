"""Clientes HTTP pequenos para fontes públicas de dados geoespaciais."""

from __future__ import annotations

import json
from threading import BoundedSemaphore
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SourceUnavailable(RuntimeError):
    pass


MAX_SOURCE_BYTES = 16 * 1024 * 1024
_source_slots = BoundedSemaphore(16)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


source_opener = build_opener(NoRedirect())


def _fetch_bytes(url: str, timeout: float, *, max_bytes: int, params=None, data=None, headers=None) -> bytes:
    if not _source_slots.acquire(blocking=False):
        raise SourceUnavailable("Limite de consultas externas simultâneas atingido")
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
            raise ValueError("URL de fonte inválida")
        if params:
            url = parsed._replace(query=urlencode(params)).geturl()
        request = Request(url, data=urlencode(data).encode("utf-8") if data is not None else None,
                          headers={"User-Agent": "Sentinel-Atlas/0.1", **(headers or {}),
                                   "Accept-Encoding": "identity"})
        with source_opener.open(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > max_bytes:
                raise ValueError("Tamanho anunciado acima do limite")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("Resposta acima do limite")
            return data
    except (OSError, ValueError) as error:
        raise SourceUnavailable("Fonte externa indisponível ou resposta inválida") from error
    finally:
        _source_slots.release()


def fetch_json(url: str, timeout: float = 10, *, max_bytes: int | None = None,
               params=None, data=None, headers=None) -> object:
    body = _fetch_bytes(url, timeout, max_bytes=MAX_SOURCE_BYTES if max_bytes is None else max_bytes,
                        params=params, data=data, headers=headers)
    try:
        return json.loads(body)
    except (ValueError, RecursionError) as error:
        raise SourceUnavailable("Resposta JSON inválida") from error


def fetch_text(url: str, timeout: float = 10) -> str:
    try:
        return _fetch_bytes(url, timeout, max_bytes=MAX_SOURCE_BYTES).decode("utf-8")
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
