"""Publicación en Upstash Redis mediante su API REST (sin dependencias).

Variables de entorno (o ClimAppWeb/.env): UPSTASH_REDIS_REST_URL y UPSTASH_REDIS_REST_TOKEN.
Si no están, publish() no hace nada y lo informa: el JSON igual queda en location_snapshots.

Claves (prefijo climapp:v1):
  loc:<slug>   JSON de la ubicación (snapshot.build)
  avisos       avisos vigentes y su asignación a ubicaciones
  indice       lista de ubicaciones para el buscador
  meta         fecha de generación y conteos
  lluvia       lluvia medida en las estaciones DMC (cada hora; job dmc_lluvia)
"""

from __future__ import annotations

import json
import os
import urllib.request

from .db import ENV_FILE

PREFIX = "climapp:v1"
PIPELINE_SIZE = 50


def _config() -> tuple[str, str] | None:
    env = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    url, token = env.get("UPSTASH_REDIS_REST_URL"), env.get("UPSTASH_REDIS_REST_TOKEN")
    return (url.rstrip("/"), token) if url and token else None


def configured() -> bool:
    return _config() is not None


def publish(items: dict[str, object], ttl_seconds: int | None = None) -> int:
    """SET de cada clave (sin prefijo) con su valor en JSON. Devuelve cuántas claves se escribieron."""
    config = _config()
    if config is None:
        return 0
    url, token = config
    commands = []
    for key, value in items.items():
        command = ["SET", f"{PREFIX}:{key}", json.dumps(value, ensure_ascii=False, separators=(",", ":"))]
        if ttl_seconds:
            command += ["EX", str(ttl_seconds)]
        commands.append(command)
    for start in range(0, len(commands), PIPELINE_SIZE):
        body = json.dumps(commands[start:start + PIPELINE_SIZE]).encode("utf-8")
        request = urllib.request.Request(f"{url}/pipeline", data=body, method="POST", headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            for result in json.loads(response.read()):
                if "error" in result:
                    raise RuntimeError(f"Upstash: {result['error']}")
    return len(commands)
