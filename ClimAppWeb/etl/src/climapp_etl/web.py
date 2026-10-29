"""Aviso a la web (Vercel) para que muestre los datos nuevos al instante.

El ETL deja una clave aleatoria de un solo uso en Redis (climapp:v1:revalidar, vence en 5 min) y la
envía a POST /api/revalidate; la web la compara con la de Redis y expira su caché. Así no hace falta
otra variable secreta compartida.

Variable opcional: WEB_URL (por defecto la URL de producción).
"""

from __future__ import annotations

import json
import os
import secrets
import urllib.request
from datetime import datetime, timezone

from . import redis

WEB_URL = os.environ.get("WEB_URL", "https://climapp-chile.vercel.app")


def respaldo_publicado() -> bool:
    """Tras subir el respaldo a GitHub: guarda en Redis la versión (commit) que debe leer la web
    (clave `respaldo`; CLIMAPP_RESPALDO_SHA) y la renueva. Lo llama el flujo de la ingesta."""
    sha = os.environ.get("CLIMAPP_RESPALDO_SHA", "").strip()
    if len(sha) != 40:
        raise ValueError("CLIMAPP_RESPALDO_SHA debe ser un commit (40 caracteres)")
    redis.publish({"respaldo": {"sha": sha, "generado": datetime.now(timezone.utc).isoformat(timespec="seconds")}})
    return revalidar()


def revalidar(timeout: int = 30) -> bool:
    """Pide a la web renovar sus páginas. Devuelve True si respondió OK; nunca lanza excepción."""
    if not redis.configured() or redis.sin_cuota():
        return False
    try:
        token = secrets.token_urlsafe(32)
        redis.publish({"revalidar": {"token": token}}, ttl_seconds=300)
        req = urllib.request.Request(f"{WEB_URL.rstrip('/')}/api/revalidate", method="POST",
                                     data=json.dumps({"token": token}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "ClimApp-ETL/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False
