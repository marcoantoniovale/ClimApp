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
    """GET que devuelve JSON. Reintenta con espera creciente ante errores de red, 429 y 5xx."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, safe=',')}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS or attempt == attempts:
                detail = exc.read().decode("utf-8", "replace")[:300]
                raise RuntimeError(f"HTTP {exc.code} en {url[:120]}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts:
                raise RuntimeError(f"Error de red en {url[:120]}: {exc}") from exc
        time.sleep(5 * 2 ** (attempt - 1))  # 5, 10, 20 s
