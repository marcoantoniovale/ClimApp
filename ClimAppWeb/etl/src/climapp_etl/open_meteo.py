"""Conector Open-Meteo: pronóstico horario en varias ubicaciones.

Modelo único ICON (decisión del 2026-10-01, docs/precision-evaluacion.md): menor error contra las
estaciones DMC y publicación más rápida. GFS aporta solo índice UV y visibilidad, que ICON no
entrega. Detalles de la API y de la cuota en docs/spikes-semana1.md §1.
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
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

# API marina (un solo modelo): variable → columna de forecast_marine.
MARINE_VARIABLES = {
    "wave_height": "oleaje_altura",
    "wave_period": "oleaje_periodo",
    "wave_direction": "oleaje_dir",
    "swell_wave_height": "marejada_altura",
}

# Código interno → nombre del modelo en Open-Meteo.
MODELS = {"icon": "icon_seamless", "ecmwf": "ecmwf_ifs", "gfs": "gfs_seamless"}

# Variables que se piden a cada modelo: variable de Open-Meteo → columna canónica. Open-Meteo entrega
# ya en °C, %, mm, hPa, m y (con wind_speed_unit=ms) m/s; snowfall en cm.
MODEL_VARIABLES = {
    "icon": {
        "temperature_2m": "temperatura",
        "apparent_temperature": "sensacion_termica",
        "dew_point_2m": "punto_rocio",
        "weather_code": "estado_cielo",
        "relative_humidity_2m": "humedad",
        "cloud_cover": "nubosidad",
        "precipitation_probability": "precip_prob",
        "precipitation": "precipitacion",
        "snowfall": "nieve",
        "wind_speed_10m": "viento_vel",
        "wind_direction_10m": "viento_dir",
        "wind_gusts_10m": "viento_rafaga",
        "pressure_msl": "presion",
        "freezing_level_height": "isoterma_0",
    },
    # Mezcla (algoritmo ClimApp): ICON + ECMWF IFS 9 km por partes iguales; el precálculo promedia por hora
    # los modelos presentes. Temperatura medida en 197 estaciones (docs/precision-evaluacion.md §8); lluvia
    # en consenso desde el 2026-10-05 (ICON sola atrasaba el inicio respecto de los demás modelos).
    "ecmwf": {
        "temperature_2m": "temperatura",
        "apparent_temperature": "sensacion_termica",
        "precipitation": "precipitacion",
        "precipitation_probability": "precip_prob",
        "weather_code": "estado_cielo",
    },
    "gfs": {  # complementarias: ICON no las calcula
        "uv_index": "indice_uv",
        "visibility": "visibilidad",
    },
}

# Todas las columnas de forecast_current, en orden estable.
COLUMNS = list(dict.fromkeys(c for vs in MODEL_VARIABLES.values() for c in vs.values()))

# Compatibilidad: todas las variables (p. ej. para pruebas) y subconjunto que se archiva (ICON).
VARIABLES = {k: v for vs in MODEL_VARIABLES.values() for k, v in vs.items()}
ARCHIVE_VARIABLES = {
    k: v for k, v in MODEL_VARIABLES["icon"].items()
    if v in ("temperatura", "humedad", "precipitacion", "viento_vel", "viento_dir", "viento_rafaga", "presion")
}

# Metadatos de corridas: https://api.open-meteo.com/data/<modelo>/static/meta.json
# gfs_seamless combina GFS 0.13° y 0.25°; se toma la corrida más nueva de ambos.
META_URL = "https://api.open-meteo.com/data/{}/static/meta.json"
META_SOURCES = {"icon": ("dwd_icon",), "ecmwf": ("ecmwf_ifs",), "gfs": ("ncep_gfs013", "ncep_gfs025")}

BATCH_SIZE = 50            # ubicaciones por petición
CALLS_PER_MINUTE = 500     # límite propio, bajo el de Open-Meteo (600/min)


@dataclass(frozen=True)
class Point:
    key: object            # location_id o station_id
    lat: float
    lon: float
    elevation: float | None = None   # m; si se indica, Open-Meteo ajusta la temperatura a esa altura


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


@dataclass(frozen=True)
class Run:
    init: datetime          # hora de inicio de la corrida
    available: datetime     # cuándo quedó disponible en Open-Meteo


def latest_runs(get_json=http.get_json) -> dict[str, Run]:
    """Última corrida disponible de cada modelo según los metadatos de Open-Meteo."""
    runs = {}
    for model, sources in META_SOURCES.items():
        candidates = []
        for source in sources:
            meta = get_json(META_URL.format(source), attempts=2, timeout=20)
            candidates.append(Run(
                init=datetime.fromtimestamp(meta["last_run_initialisation_time"], timezone.utc),
                available=datetime.fromtimestamp(meta["last_run_availability_time"], timezone.utc),
            ))
        runs[model] = max(candidates, key=lambda r: (r.init, r.available))
    return runs


def fetch(points: list[Point], variables: dict[str, str], days: int, past_days: int = 0,
          budget: MinuteBudget | None = None, get_json=http.get_json,
          models: list[str] | None = None) -> list[tuple[Point, dict]]:
    """Descarga el pronóstico horario de todos los puntos, en lotes. Devuelve (punto, respuesta).
    past_days agrega días anteriores (para que el resumen de "hoy" en hora de Chile esté completo).
    models: subconjunto de MODELS a pedir (por defecto, todos)."""
    budget = budget or MinuteBudget()
    models = models or list(MODELS)
    results = []
    for start in range(0, len(points), BATCH_SIZE):
        batch = points[start:start + BATCH_SIZE]
        budget.acquire(call_weight(len(batch), len(variables), len(models), days + past_days))
        data = get_json(FORECAST_URL, {
            "latitude": ",".join(f"{p.lat:.4f}" for p in batch),
            "longitude": ",".join(f"{p.lon:.4f}" for p in batch),
            "hourly": ",".join(variables),
            "models": ",".join(MODELS[m] for m in models),
            "forecast_days": days,
            "past_days": past_days,
            "wind_speed_unit": "ms",
            "timezone": "GMT",
            **_elevation_param(batch),
        })
        if isinstance(data, dict):  # con una sola coordenada la API no devuelve lista
            data = [data]
        if len(data) != len(batch):
            raise RuntimeError(f"Open-Meteo devolvió {len(data)} ubicaciones para un lote de {len(batch)}")
        results.extend(zip(batch, data))
    return results


def _elevation_param(batch: list[Point]) -> dict:
    """Parámetro elevation solo si todos los puntos del lote la traen (no mezclar con la del DEM)."""
    if batch and all(p.elevation is not None for p in batch):
        return {"elevation": ",".join(f"{p.elevation:.0f}" for p in batch)}
    return {}


def fetch_marine(points: list[Point], days: int, budget: MinuteBudget | None = None,
                 get_json=http.get_json) -> list[tuple[Point, dict]]:
    """Oleaje horario en la celda de mar más cercana a cada punto."""
    budget = budget or MinuteBudget()
    results = []
    for start in range(0, len(points), BATCH_SIZE):
        batch = points[start:start + BATCH_SIZE]
        budget.acquire(call_weight(len(batch), len(MARINE_VARIABLES), 1, days))
        data = get_json(MARINE_URL, {
            "latitude": ",".join(f"{p.lat:.4f}" for p in batch),
            "longitude": ",".join(f"{p.lon:.4f}" for p in batch),
            "hourly": ",".join(MARINE_VARIABLES),
            "forecast_days": days,
            "cell_selection": "sea",
            "timezone": "GMT",
        })
        if isinstance(data, dict):
            data = [data]
        if len(data) != len(batch):
            raise RuntimeError(f"Open-Meteo marino devolvió {len(data)} ubicaciones para {len(batch)}")
        results.extend(zip(batch, data))
    return results


def marine_rows(response: dict) -> Iterator[tuple[datetime, dict]]:
    """(hora_valida_utc, {columna: valor}) de una respuesta marina; omite horas vacías."""
    hourly = response["hourly"]
    for i, t in enumerate(hourly["time"]):
        values = {col: hourly.get(var, [None] * (i + 1))[i] for var, col in MARINE_VARIABLES.items()}
        if any(v is not None for v in values.values()):
            yield datetime.fromisoformat(t).replace(tzinfo=timezone.utc), values


def rows(response: dict, variables: dict[str, str],
         models: list[str] | None = None) -> Iterator[tuple[str, datetime, dict]]:
    """Convierte la respuesta de una ubicación en (modelo, hora_valida_utc, {columna: valor}).
    Omite las horas en que el modelo no trae ningún dato."""
    hourly = response["hourly"]
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in hourly["time"]]
    models = models or list(MODELS)
    for model in models:
        api_model = MODELS[model]
        # Con un solo modelo en la petición, Open-Meteo no agrega el sufijo del modelo a la variable.
        series = {col: hourly.get(f"{var}_{api_model}", hourly.get(var) if len(models) == 1 else None)
                  for var, col in variables.items()}
        for i, valid_time in enumerate(times):
            values = {}
            for col, serie in series.items():
                value = serie[i] if serie is not None else None
                if isinstance(value, float) and math.isnan(value):
                    value = None
                values[col] = plausible(col, value)
            if any(v is not None for v in values.values()):
                yield model, valid_time, values


ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"


def elevations(points: list[Point], budget: MinuteBudget | None = None,
               get_json=http.get_json) -> dict[object, float]:
    """Altura del terreno (m, modelo digital de Open-Meteo, ~90 m) de cada punto: {clave: m}.
    Cada coordenada cuenta como una llamada en la cuota por minuto."""
    budget = budget or MinuteBudget()
    out = {}
    for start in range(0, len(points), 100):
        batch = points[start:start + 100]
        budget.acquire(len(batch))
        data = get_json(ELEVATION_URL, {"latitude": ",".join(f"{p.lat:.4f}" for p in batch),
                                        "longitude": ",".join(f"{p.lon:.4f}" for p in batch)})
        for p, h in zip(batch, data.get("elevation", [])):
            if h is not None:
                out[p.key] = float(h)
    return out
