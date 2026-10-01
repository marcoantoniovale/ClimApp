"""Cliente HTTP mínimo con reintentos (sin dependencias externas)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "ClimApp-ETL/0.1 (+https://github.com/marcoantoniovale/ClimApp)"
RETRY_STATUS = {429, 500, 502, 503, 504}


def get_json(url: str, params: dict | None = None, *, attempts: int = 4, timeout: int = 60):
    """GET que devuelve JSON. Reintenta con espera creciente ante errores de red, 429, 5xx
    y respuestas vacías o que no son JSON (Open-Meteo devolvió un 200 vacío el 2026-10-01)."""
    for attempt in range(1, attempts + 1):
        body = _get(url, params, "application/json", attempts, timeout)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            if attempt == attempts:
                raise RuntimeError(f"Respuesta no JSON ({len(body)} bytes) de {url[:120]}") from exc
            time.sleep(5 * 2 ** (attempt - 1))


def get_text(url: str, params: dict | None = None, *, attempts: int = 4, timeout: int = 60) -> str:
    """GET que devuelve texto (HTML), con los mismos reintentos."""
    return _get(url, params, "text/html", attempts, timeout).decode("utf-8", "replace")


def _get(url: str, params: dict | None, accept: str, attempts: int, timeout: int) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, safe=',')}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS or attempt == attempts:
                detail = exc.read().decode("utf-8", "replace")[:300]
                raise RuntimeError(f"HTTP {exc.code} en {url[:120]}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts:
                raise RuntimeError(f"Error de red en {url[:120]}: {exc}") from exc
        time.sleep(5 * 2 ** (attempt - 1))  # 5, 10, 20 s
