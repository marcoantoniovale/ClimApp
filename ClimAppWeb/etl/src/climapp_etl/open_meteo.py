"""Conector Open-Meteo: pronóstico horario de GFS, ECMWF e ICON en varias ubicaciones.

Detalles de la API y de la cuota en docs/spikes-semana1.md §1.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from . import http
from .units import plausible

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Código interno → nombre del modelo en Open-Meteo.
MODELS = {"gfs": "gfs_seamless", "ecmwf": "ecmwf_ifs025", "icon": "icon_seamless"}

# Variable de Open-Meteo → columna canónica. Open-Meteo entrega ya en °C, %, mm, hPa y
# (con wind_speed_unit=ms) m/s. uv_index solo viene en GFS; ECMWF e ICON lo dejan nulo.
VARIABLES = {
    "temperature_2m": "temperatura",
    "apparent_temperature": "sensacion_termica",
    "weather_code": "estado_cielo",
    "uv_index": "indice_uv",
    "relative_humidity_2m": "humedad",
    "precipitation_probability": "precip_prob",
    "precipitation": "precipitacion",
    "wind_speed_10m": "viento_vel",
    "wind_direction_10m": "viento_dir",
    "wind_gusts_10m": "viento_rafaga",
    "pressure_msl": "presion",
}

# Subconjunto que se archiva para la verificación de la Fase 2.
ARCHIVE_VARIABLES = {
    k: v for k, v in VARIABLES.items()
    if v in ("temperatura", "humedad", "precipitacion", "viento_vel", "viento_dir", "viento_rafaga", "presion")
}

BATCH_SIZE = 50            # ubicaciones por petición
CALLS_PER_MINUTE = 500     # límite propio, bajo el de Open-Meteo (600/min)


@dataclass(frozen=True)
class Point:
    key: object            # location_id o station_id
    lat: float
    lon: float


def call_weight(n_points: int, n_variables: int, n_models: int, days: int) -> float:
    """Llamadas que Open-Meteo descuenta: >10 variables o >14 días cuentan como fracción extra.
    Supuesto conservador: cada ubicación cuenta por separado y cada modelo multiplica las variables."""
    return n_points * max(1.0, n_variables * n_models / 10) * max(1.0, days / 14)


class MinuteBudget:
    """Espera lo necesario para no superar CALLS_PER_MINUTE en una ventana de 60 s."""

    def __init__(self, per_minute: float = CALLS_PER_MINUTE, clock=time.monotonic, sleep=time.sleep):
        self.per_minute = per_minute
        self.clock, self.sleep = clock, sleep
        self.spent: list[tuple[float, float]] = []  # (instante, peso)

    def acquire(self, weight: float) -> None:
        while True:
            now = self.clock()
            self.spent = [(t, w) for t, w in self.spent if now - t < 60]
            if sum(w for _, w in self.spent) + weight <= self.per_minute or not self.spent:
                self.spent.append((now, weight))
                return
            self.sleep(60 - (now - self.spent[0][0]) + 0.5)


def fetch(points: list[Point], variables: dict[str, str], days: int,
          budget: MinuteBudget | None = None, get_json=http.get_json) -> list[tuple[Point, dict]]:
    """Descarga el pronóstico horario de todos los puntos, en lotes. Devuelve (punto, respuesta)."""
    budget = budget or MinuteBudget()
    results = []
    for start in range(0, len(points), BATCH_SIZE):
        batch = points[start:start + BATCH_SIZE]
        budget.acquire(call_weight(len(batch), len(variables), len(MODELS), days))
        data = get_json(FORECAST_URL, {
            "latitude": ",".join(f"{p.lat:.4f}" for p in batch),
            "longitude": ",".join(f"{p.lon:.4f}" for p in batch),
            "hourly": ",".join(variables),
            "models": ",".join(MODELS.values()),
            "forecast_days": days,
            "wind_speed_unit": "ms",
            "timezone": "GMT",
        })
        if isinstance(data, dict):  # con una sola coordenada la API no devuelve lista
            data = [data]
        if len(data) != len(batch):
            raise RuntimeError(f"Open-Meteo devolvió {len(data)} ubicaciones para un lote de {len(batch)}")
        results.extend(zip(batch, data))
    return results


def rows(response: dict, variables: dict[str, str]) -> Iterator[tuple[str, datetime, dict]]:
    """Convierte la respuesta de una ubicación en (modelo, hora_valida_utc, {columna: valor}).
    Omite las horas en que el modelo no trae ningún dato."""
    hourly = response["hourly"]
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in hourly["time"]]
    for model, api_model in MODELS.items():
        series = {col: hourly.get(f"{var}_{api_model}") for var, col in variables.items()}
        for i, valid_time in enumerate(times):
            values = {}
            for col, serie in series.items():
                value = serie[i] if serie is not None else None
                if isinstance(value, float) and math.isnan(value):
                    value = None
                values[col] = plausible(col, value)
            if any(v is not None for v in values.values()):
                yield model, valid_time, values
