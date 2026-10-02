"""Unidades canónicas y conversiones (docs/fase1-mapeo-requisitos.md §4.3).

Canónicas: temperatura °C, presión hPa, precipitación mm, viento m/s, oleaje m / s / grados.
"""

from __future__ import annotations

KNOT_IN_MS = 1852 / 3600     # 1 nudo = 1852 m/h
KMH_IN_MS = 1000 / 3600

# Código de unidad de viento de las EMA de la Armada (parámetro 6).
ARMADA_WIND_UNITS = {1: "kn", 2: "km/h", 3: "m/s"}

# Rangos plausibles por variable canónica; fuera de rango se descarta el valor.
PLAUSIBLE = {
    "temperatura": (-60.0, 50.0),
    "sensacion_termica": (-70.0, 60.0),
    "punto_rocio": (-70.0, 40.0),
    "humedad": (0.0, 100.0),
    "precip_prob": (0.0, 100.0),
    "precipitacion": (0.0, 500.0),
    "presion": (850.0, 1090.0),
    "viento_vel": (0.0, 100.0),
    "viento_rafaga": (0.0, 120.0),
    "viento_dir": (0.0, 360.0),
    "indice_uv": (0.0, 20.0),
    "nubosidad": (0.0, 100.0),
    "visibilidad": (0.0, 100_000.0),
    "isoterma_0": (-1000.0, 7000.0),
    "nieve": (0.0, 50.0),
}


def to_ms(value: float | None, unit: str) -> float | None:
    """Velocidad de viento a m/s desde 'kn', 'km/h' o 'm/s'."""
    if value is None:
        return None
    factor = {"kn": KNOT_IN_MS, "km/h": KMH_IN_MS, "m/s": 1.0}[unit]
    return value * factor


def ms_to_kmh(value: float) -> float:
    return value / KMH_IN_MS


def ms_to_knots(value: float) -> float:
    return value / KNOT_IN_MS


def to_float(value) -> float | None:
    """Convierte textos y números de las fuentes a float; '', None y no numéricos → None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def plausible(variable: str, value: float | None) -> float | None:
    """Devuelve el valor si está en el rango plausible de la variable; si no, None."""
    if value is None or variable not in PLAUSIBLE:
        return value
    low, high = PLAUSIBLE[variable]
    return value if low <= value <= high else None
