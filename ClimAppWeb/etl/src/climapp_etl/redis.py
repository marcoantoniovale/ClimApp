"""Publicación en Upstash Redis mediante su API REST (sin dependencias).

Variables de entorno (o ClimAppWeb/.env): UPSTASH_REDIS_REST_URL y UPSTASH_REDIS_REST_TOKEN.
Si no están, publish() no hace nada y lo informa: el JSON igual queda en location_snapshots.

Claves (prefijo climapp:v1):
  loc:<slug>   JSON de la ubicación (snapshot.build)
  avisos       avisos vigentes y su asignación a ubicaciones
  indice       lista de ubicaciones para el buscador
  meta         fecha de generación y conteos
  lluvia       lluvia medida en las estaciones DMC (cada hora; job dmc_lluvia)

Uso del plan gratuito de Upstash (límites mensuales de comandos y de transferencia; el 2026-10-29 se
agotaron con ~10 GB/mes de JSON y un SET por clave): los valores de más de COMPRIMIR_DESDE bytes se
guardan comprimidos ("gz:" + gzip en base64; la web los descomprime en lib/redis.ts) y las claves se
escriben con MSET en lotes de hasta LOTE_BYTES (un comando por lote).

Respaldo (si Upstash no responde, la web lee lo mismo desde GitHub): con la variable CLIMAPP_RESPALDO_DIR,
publish() escribe además cada clave como JSON en ese directorio (antes de intentar Redis, para que quede
aunque Upstash falle). Ruta: la clave con ":" → "/" (loc:quintero → loc/quintero.json). El flujo de GitHub
Actions sube el directorio a la etiqueta `datos` del repositorio (scripts/publicar_respaldo.sh) y la web la
lee desde raw.githubusercontent.com (web/src/lib/redis.ts).

Cuota agotada: si Upstash responde que la base llegó al límite del plan, publish() no falla (el dato ya
quedó en el respaldo y la web lo lee de ahí); lo registra, deja de intentar Redis en el resto del proceso y
sin_cuota() pasa a True. USO acumula comandos y bytes enviados (se informan al final de `auto`).
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import logging
import urllib.error
import urllib.request
from pathlib import Path

from .db import ENV_FILE

PREFIX = "climapp:v1"
COMPRIMIR_DESDE = 2048          # bytes de JSON
LOTE_BYTES = 700_000            # por MSET (Upstash limita el tamaño de cada petición)

log = logging.getLogger(__name__)
USO = {"comandos": 0, "bytes": 0}
_sin_cuota = False


def sin_cuota() -> bool:
    """True si en este proceso Upstash respondió que se agotó la cuota del plan."""
    return _sin_cuota


def es_cuota_agotada(codigo: int, cuerpo: str) -> bool:
    return codigo in (400, 403, 429) and ("limit" in cuerpo.lower() or "quota" in cuerpo.lower())


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


def codificar(value: object) -> str:
    """JSON compacto; si es grande, comprimido con gzip en base64 y el prefijo "gz:"."""
    texto = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(texto) < COMPRIMIR_DESDE:
        return texto
    return "gz:" + base64.b64encode(gzip.compress(texto.encode("utf-8"), compresslevel=9, mtime=0)).decode("ascii")


def comandos(items: dict[str, object], ttl_seconds: int | None = None) -> list[list[str]]:
    """Comandos para escribir las claves: SET … EX con plazo; si no, MSET por lotes de ≤ LOTE_BYTES."""
    valores = [(f"{PREFIX}:{key}", codificar(value)) for key, value in items.items()]
    if ttl_seconds:
        return [["SET", k, v, "EX", str(ttl_seconds)] for k, v in valores]
    lotes: list[list[str]] = []
    tamano = LOTE_BYTES
    for k, v in valores:
        if tamano + len(v) > LOTE_BYTES:
            lotes.append(["MSET"])
            tamano = 0
        lotes[-1] += [k, v]
        tamano += len(k) + len(v)
    return lotes


def ruta_respaldo(key: str) -> str:
    """Clave sin prefijo → ruta del archivo de respaldo (loc:quintero → loc/quintero.json)."""
    return key.replace(":", "/") + ".json"


def respaldar(items: dict[str, object]) -> int:
    """Escribe cada clave en CLIMAPP_RESPALDO_DIR (si está definida). Devuelve cuántas escribió."""
    base = os.environ.get("CLIMAPP_RESPALDO_DIR")
    if not base:
        return 0
    for key, value in items.items():
        destino = Path(base) / ruta_respaldo(key)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(items)


def publish(items: dict[str, object], ttl_seconds: int | None = None) -> int:
    """Escribe cada clave (sin prefijo) con su valor. Devuelve cuántas claves se escribieron.

    Las claves sin plazo también van al respaldo (las de un solo uso, como revalidar, no).
    """
    global _sin_cuota
    respaldadas = 0 if ttl_seconds else respaldar(items)
    config = _config()
    if config is None or _sin_cuota:
        return respaldadas
    url, token = config
    for command in comandos(items, ttl_seconds):   # una petición por comando: cada lote cabe en el límite
        body = json.dumps([command]).encode("utf-8")
        request = urllib.request.Request(f"{url}/pipeline", data=body, method="POST", headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                resultados = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            cuerpo = exc.read().decode("utf-8", "replace")
            if es_cuota_agotada(exc.code, cuerpo):
                _sin_cuota = True
                log.warning("Upstash sin cuota (%s): solo respaldo en GitHub. %s", exc.code, cuerpo[:200])
                return respaldadas
            raise RuntimeError(f"Upstash {exc.code}: {cuerpo[:200]}") from exc
        USO["comandos"] += 1
        USO["bytes"] += len(body)
        for result in resultados:
            if "error" in result:
                raise RuntimeError(f"Upstash: {result['error']}")
    return len(items)
