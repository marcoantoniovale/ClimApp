"""Conector de observaciones de la Armada de Chile (API JSON del mapa de estaciones).

Hallazgos que explican las reglas de este módulo (docs/spikes-semana1.md §2):
- Capitanías (/observaciones/directemar): `fecha` en hora de Chile; viento en nudos
  (sin unidad declarada; deducido comparando con Open-Meteo: razón 1,87 ≈ 1,94).
  Algunas traen "Fecha inválida" o lecturas de hace meses.
- EMA (/observaciones): `timeLocal` es la hora de Chile; `time` viene mal convertido
  (UTC + 2 h), así que no se usa. La unidad del viento está en el parámetro 6.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import http
from .units import ARMADA_WIND_UNITS, plausible, to_float, to_ms

API = "https://serviciosonline.directemar.cl/meteomapa/api/meteo"
CHILE = ZoneInfo("America/Santiago")
MAX_AGE = timedelta(days=2)   # lecturas más antiguas se consideran estación detenida

# Parámetros de las EMA (cdparam) → columna canónica.
EMA_PARAMS = {
    7: "viento_dir",
    11: "temperatura",
    13: "punto_rocio",
    14: "humedad",
    16: "presion",
    67: "precipitacion_1h",
}
EMA_WIND_SPEED, EMA_WIND_UNIT = 8, 6


def parse_local(text: str | None) -> datetime | None:
    """Fecha en hora de Chile ('2026-10-01T17:08:07' o '2026-10-01T16:50') → UTC; inválida → None."""
    try:
        local = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return local.replace(tzinfo=CHILE).astimezone(timezone.utc)


def _clean(values: dict) -> dict:
    return {col: plausible(col, value) for col, value in values.items()}


def parse_capitanias(records: list[dict]) -> list[dict]:
    rows = []
    for r in records:
        observed_at = parse_local(r.get("fecha"))
        if observed_at is None:
            continue
        rows.append({
            "station_id": r["codigo"],
            "observed_at": observed_at,
            **_clean({
                "temperatura": to_float(r.get("temperatura")),
                "punto_rocio": to_float(r.get("puntoDeRocio")),
                "humedad": to_float(r.get("humedad")),
                "presion": to_float(r.get("presion")),
                "viento_vel": to_ms(to_float(r.get("velocidadDelViento")), "kn"),
                "viento_dir": to_float(r.get("viento")),
                "viento_rafaga": to_ms(to_float(r.get("rafaga10Minutos")), "kn"),
                "precipitacion_1h": to_float(r.get("lluviaUltimaHora")),
            }),
            "raw": r,
        })
    return rows


def parse_ema(records: list[dict]) -> list[dict]:
    rows = []
    for r in records:
        observed_at = parse_local(r.get("timeLocal"))
        if observed_at is None:
            continue
        params = {p["cdparam"]: to_float(p.get("value")) for p in r.get("parametros") or []}
        unit = ARMADA_WIND_UNITS.get(int(params.get(EMA_WIND_UNIT) or 1), "kn")
        values = {col: params.get(code) for code, col in EMA_PARAMS.items()}
        values["viento_vel"] = to_ms(params.get(EMA_WIND_SPEED), unit)
        values["viento_rafaga"] = None
        rows.append({
            "station_id": str(r["codigoEstacion"]),
            "observed_at": observed_at,
            **_clean(values),
            "raw": r,
        })
    return rows


def fetch_observations(get_json=http.get_json) -> list[dict]:
    """Observaciones actuales de capitanías y EMA, ya normalizadas."""
    return (parse_capitanias(get_json(f"{API}/observaciones/directemar"))
            + parse_ema(get_json(f"{API}/observaciones")))


def is_recent(row: dict, now: datetime) -> bool:
    return now - MAX_AGE <= row["observed_at"] <= now + timedelta(hours=1)
