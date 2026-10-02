"""Algoritmo ClimApp v1: corrección de la temperatura de ICON con mediciones de estaciones DMC.

1. Sesgo por estación y franja del día (hora de Chile; 4 franjas de 6 h): promedio de
   (ICON − medición) en las horas comparadas. Se atenúa con pocos datos, sesgo = bruto · n / (n + K),
   y se limita a ±MAX_SESGO. Así arranca prudente y se vuelve más firme a medida que llegan datos.
2. Corrección de una ubicación: promedio ponderado de los sesgos de las estaciones a ≤ RADIO_KM y de la
   misma zona (costa con costa, interior con interior), con peso exp(−d / ESCALA_KM) y un término que
   atenúa cuando las estaciones están lejos. Sin estaciones cercanas no se corrige.
3. Se resta la corrección a la temperatura y a la sensación térmica de ICON, hora a hora.
4. Medición de anclaje: la lectura más reciente de la estación más cercana de la misma zona (≤ RADIO_MEDICION_KM).
   La web parte de ella y la acerca a la curva del pronóstico de a poco (ver web/src/lib/ahora.ts).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from statistics import mean
from zoneinfo import ZoneInfo

CHILE = ZoneInfo("America/Santiago")
K = 12              # horas para que el sesgo pese la mitad
MAX_SESGO = 5.0     # °C
MAX_DIFERENCIA = 15.0   # °C: diferencias mayores se consideran error de medición
RADIO_KM = 25.0
ESCALA_KM = 10.0
ATENUACION = 0.25   # peso "a favor de cero" cuando las estaciones están lejos
RADIO_MEDICION_KM = 15.0


def franja(t: datetime) -> int:
    return t.astimezone(CHILE).hour // 6


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def sesgos(icon: dict[datetime, float], obs: dict[datetime, float]) -> dict[int, dict]:
    """Sesgo de ICON en una estación por franja: {franja: {sesgo, sesgo_bruto, n, error_antes}}."""
    por_franja: dict[int, list[float]] = defaultdict(list)
    for t, medido in obs.items():
        pronostico = icon.get(t)
        if pronostico is None or medido is None:
            continue
        diferencia = pronostico - medido
        if abs(diferencia) <= MAX_DIFERENCIA:
            por_franja[franja(t)].append(diferencia)
    out = {}
    for f, difs in por_franja.items():
        n = len(difs)
        bruto = mean(difs)
        out[f] = {
            "sesgo": max(-MAX_SESGO, min(MAX_SESGO, bruto * n / (n + K))),
            "sesgo_bruto": bruto,
            "n": n,
            "error_antes": mean(abs(d) for d in difs),
        }
    return out


def correccion(lat: float, lon: float, costera: bool, estaciones: list[dict]) -> dict:
    """Corrección para una ubicación. estaciones: [{id, nombre, lat, lon, costera, sesgos: {franja: sesgo}}].
    Devuelve {"franjas": {franja: °C a restar}, "estaciones": [{nombre, km}]}."""
    cercanas = []
    for e in estaciones:
        if e["costera"] != costera:
            continue
        d = km(lat, lon, e["lat"], e["lon"])
        if d <= RADIO_KM:
            cercanas.append((d, e))
    if not cercanas:
        return {"franjas": {}, "estaciones": []}
    franjas = {}
    for f in range(4):
        pares = [(math.exp(-d / ESCALA_KM), e["sesgos"][f]) for d, e in cercanas if f in e["sesgos"]]
        if pares:
            peso = sum(w for w, _ in pares)
            franjas[f] = sum(w * s for w, s in pares) / (peso + ATENUACION)
    cercanas.sort(key=lambda x: x[0])
    return {"franjas": franjas, "estaciones": [{"nombre": e["nombre"], "km": round(d, 1)} for d, e in cercanas[:3]]}


def medicion_cercana(lat: float, lon: float, costera: bool, mediciones: list[dict],
                     radio: float = RADIO_MEDICION_KM) -> dict | None:
    """Última medición de la estación más cercana de la misma zona, con su distancia (km), o None.
    mediciones: [{lat, lon, costera, ...campos de la medición}]."""
    mejor = None
    for m in mediciones:
        if m["costera"] != costera:
            continue
        d = km(lat, lon, m["lat"], m["lon"])
        if d <= radio and (mejor is None or d < mejor[0]):
            mejor = (d, m)
    if mejor is None:
        return None
    d, m = mejor
    return {k: v for k, v in m.items() if k not in ("lat", "lon", "costera")} | {"km": round(d, 1)}


def aplicar(rows: list[tuple], corr: dict) -> list[tuple]:
    """Resta la corrección a temperatura y sensación térmica de ICON en filas (modelo, hora, valores)."""
    if not corr["franjas"]:
        return rows
    out = []
    for modelo, t, valores in rows:
        delta = corr["franjas"].get(franja(t))
        if modelo == "icon" and delta:
            valores = dict(valores)
            for col in ("temperatura", "sensacion_termica"):
                if valores.get(col) is not None:
                    valores[col] = valores[col] - delta
        out.append((modelo, t, valores))
    return out


def validacion_cruzada(estaciones: list[dict], icon: dict[str, dict], obs: dict[str, dict]) -> dict:
    """Error medio de ICON en cada estación, sin corregir y corregido SOLO con sus vecinas (sin usar
    la propia estación). Mide si la corrección mejora donde no se midió."""
    antes, despues = [], []
    for e in estaciones:
        vecinas = [v for v in estaciones if v["id"] != e["id"]]
        corr = correccion(e["lat"], e["lon"], e["costera"], vecinas)
        if not corr["franjas"]:
            continue
        for t, medido in obs.get(e["id"], {}).items():
            p = icon.get(e["id"], {}).get(t)
            if p is None or abs(p - medido) > MAX_DIFERENCIA:
                continue
            antes.append(abs(p - medido))
            despues.append(abs(p - corr["franjas"].get(franja(t), 0) - medido))
    return {"n": len(antes), "error_antes": mean(antes) if antes else None,
            "error_despues": mean(despues) if despues else None}
