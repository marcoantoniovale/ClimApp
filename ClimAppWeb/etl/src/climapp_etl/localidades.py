"""Localidades y barrios con pronóstico propio (docs/localidades-propuesta.md, etapas L1 y L2).

Una localidad usa la curva de temperatura de su comuna (mezcla ICON + ECMWF, ya corregida con el
algoritmo ClimApp en la cabecera) y le suma su diferencia propia, hora a hora:

    T_localidad(h) = T_comuna(h) + franjas[franja(h)] + perfil[hora_local(h)]

- franjas: sesgo de la comuna menos el sesgo interpolado en la localidad (el sesgo se resta al
  pronóstico, así que corregir con el de la localidad equivale a sumar esta diferencia).
- perfil (24 valores, uno por hora local) o, si no hay, una constante por altura:
  · localidad cercana a la cabecera (≤ LEJOS_KM): misma celda del modelo; solo la altura, a
    GRADIENTE °C/m (el mismo ajuste que hace Open-Meteo dentro de una celda).
  · localidad lejana: su celda del modelo puede ser otra. Una vez al día se descarga la mezcla en el
    centro de cada celda de 0,1° con localidades lejanas y se guarda la diferencia típica con la
    comuna por hora local (mediana de los 7 días), más el ajuste por altura dentro de la celda.
    Se usa la mediana por hora (y no la diferencia hora a hora) porque el perfil se renueva una vez al
    día y debe valer para las corridas siguientes.
- anomalía del momento interpolada en la localidad (reemplaza a la de la comuna).
- medición de la estación más cercana de su zona, para mostrar.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

from .correccion import CHILE

CATALOGO = Path(__file__).resolve().parents[2] / "data" / "catalog" / "localidades.csv"
LEJOS_KM = 8.0
GRADIENTE = 0.0065   # °C por metro (gradiente térmico estándar)
CELDA = 0.1          # grados


def cargar(path: Path = CATALOGO) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [r | {"lat": float(r["lat"]), "lon": float(r["lon"]),
                     "altura": float(r["altura"]) if r["altura"] else None,
                     "km_cabecera": float(r["km_cabecera"])} for r in csv.DictReader(f)]


def clave(lugar: dict) -> str:
    return f"{lugar['comuna']}/{lugar['slug']}"


def celda(lat: float, lon: float) -> tuple[int, int]:
    return round(lat / CELDA), round(lon / CELDA)


def por_altura(altura_referencia: float | None, altura: float | None) -> float:
    """°C a sumar por estar a otra altura que la referencia (más alto, más frío)."""
    if altura_referencia is None or altura is None:
        return 0.0
    return GRADIENTE * (altura_referencia - altura)


def perfil_horario(diferencias: dict[datetime, float]) -> list[float] | None:
    """Mediana de las diferencias por hora local (0–23). None si falta alguna hora."""
    por_hora: dict[int, list[float]] = defaultdict(list)
    for t, d in diferencias.items():
        por_hora[t.astimezone(CHILE).hour].append(d)
    if len(por_hora) < 24:
        return None
    return [round(median(por_hora[h]), 2) for h in range(24)]


def ajuste(lugar: dict, franjas_comuna: dict[int, float], franjas_lugar: dict[int, float],
           perfil: list[float] | None, altura_cabecera: float | None) -> dict:
    """Parte fija del ajuste de una localidad: diferencia de sesgo por franja y perfil (o altura)."""
    out = {"nombre": lugar["nombre"], "tipo": lugar["tipo"], "lat": round(lugar["lat"], 4),
           "lon": round(lugar["lon"], 4), "altura": lugar["altura"],
           "franjas": {str(f): round(franjas_comuna.get(f, 0.0) - franjas_lugar.get(f, 0.0), 2) for f in range(4)}}
    if perfil:
        out["perfil"] = perfil
    else:
        out["por_altura"] = round(por_altura(altura_cabecera, lugar["altura"]), 2)
    return out
