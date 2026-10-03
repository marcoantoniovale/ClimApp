"""Algoritmo ClimApp v2: corrección de la temperatura de ICON con mediciones oficiales (DMC y SINCA).

Detalle y resultados en docs/precision-evaluacion.md §7.

Pronóstico base: mezcla de ICON y ECMWF IFS 9 km (promedio). En lo que sigue, "ICON" es esa mezcla.

1. Registro del error. Cada hora, por estación: r = ICON − medido, con ICON interpolado al instante de
   la lectura en el punto de la estación. Control de calidad (qc): rango, error absurdo, salto brusco,
   sensor pegado y discrepancia con las estaciones vecinas. Solo las horas "ok" se usan.
2. Sesgo sistemático (lo que ICON suele equivocarse ahí y a esa hora), por estación y franja de 6 h:
   promedio del error con olvido exponencial (vida media VIDA_MEDIA_DIAS; equivale a un filtro de
   Kalman de nivel local en régimen), atenuado con pocos datos: sesgo = media · n / (n + K).
   Se rectifica solo con cada hora nueva.
3. Anomalía del momento (lo que hoy se aparta de lo habitual): a = medido − (ICON − sesgo) en la última
   lectura de cada estación. La web la suma a la curva y la desvanece con τ (ajustado con los datos).
4. Comunas: sesgo y anomalía se interpolan desde las estaciones (se interpola el ERROR, no la
   temperatura: cada comuna conserva su propia curva de ICON). Búsqueda por cuadrantes: la estación más
   cercana al N-E, N-O, S-E y S-O, de la misma zona (costa/interior) y a ≤ RADIO_KM. Peso
   1/(d + D0)² · exp(−|Δaltura| / ALTURA_ESCALA_M). Un peso fijo "a favor de cero" hace que, lejos de
   las estaciones, la corrección vuelva a ICON puro.
5. Validación: cada estación se predice sin ella (como una comuna sin medición) y con ella.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

CHILE = ZoneInfo("America/Santiago")

# Modelos de la mezcla de temperatura (pronóstico base): el sesgo se aprende sobre su promedio y se
# resta a cada uno, así el promedio queda corregido.
MODELOS_BASE = ("icon", "ecmwf")

# Sesgo sistemático
K = 12.0                 # horas (ponderadas) para que el sesgo pese la mitad
MAX_SESGO = 5.0          # °C
VIDA_MEDIA_DIAS = 7.0
VENTANA_DIAS = 30

# Interpolación espacial
RADIO_KM = 50.0
D0_KM = 2.0
RETORNO_KM = 25.0        # una sola estación a esta distancia aporta la mitad de su valor
ALTURA_ESCALA_M = 500.0
PESO_CERO = 1 / (RETORNO_KM + D0_KM) ** 2

# Anomalía del momento
ANOMALIA_MAX_EDAD = timedelta(hours=3)
TAU_H = 20.0             # inicial; se ajusta con ajustar_tau
TAU_MIN_H, TAU_MAX_H = 3.0, 48.0

# Medición que se muestra ("Medido en …")
RADIO_MEDICION_KM = 15.0

# Control de calidad
RANGO = (-40.0, 50.0)
MAX_RESIDUO = 12.0       # °C entre ICON y lo medido
MAX_SALTO = 8.0          # °C por hora entre lecturas consecutivas
PEGADO_HORAS = 6         # lecturas idénticas seguidas
VECINAS_RADIO_KM = 50.0
VECINAS_MIN = 3
VECINAS_MAX_DIF = 5.0    # °C de diferencia de error con la mediana de las vecinas


def franja(t: datetime) -> int:
    return t.astimezone(CHILE).hour // 6


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# 1. Control de calidad

def qc_lectura(medido: float, icon: float, serie_previa: list[tuple[datetime, float]], t: datetime) -> str:
    """Control de una lectura con su propia serie (lecturas anteriores de la estación, ordenadas)."""
    if not RANGO[0] <= medido <= RANGO[1]:
        return "rango"
    if abs(icon - medido) > MAX_RESIDUO:
        return "residuo"
    if serie_previa:
        t0, v0 = serie_previa[-1]
        horas = (t - t0).total_seconds() / 3600
        if 0 < horas <= 3 and abs(medido - v0) > MAX_SALTO * max(horas, 1):
            return "salto"
    ultimas = [v for _, v in serie_previa[-(PEGADO_HORAS - 1):]]
    if len(ultimas) == PEGADO_HORAS - 1 and all(v == medido for v in ultimas):
        return "pegado"
    return "ok"


def qc_vecinas(filas: list[dict]) -> None:
    """Marca 'vecinas' en las filas de una misma hora cuyo error discrepa de sus vecinas.
    filas: [{lat, lon, costera, residuo, qc}] (se modifica qc)."""
    for f in filas:
        if f["qc"] != "ok":
            continue
        vecinas = [v["residuo"] for v in filas if v is not f and v["qc"] == "ok" and v["costera"] == f["costera"]
                   and km(f["lat"], f["lon"], v["lat"], v["lon"]) <= VECINAS_RADIO_KM]
        if len(vecinas) >= VECINAS_MIN and abs(f["residuo"] - median(vecinas)) > VECINAS_MAX_DIF:
            f["qc"] = "vecinas"


# ---------------------------------------------------------------------------
# 2. Sesgo sistemático

def sesgos(residuos: list[tuple[datetime, float]], ahora: datetime) -> dict[int, dict]:
    """Sesgo de ICON en una estación por franja, con olvido exponencial.
    residuos: [(instante, ICON − medido)] ya filtrados por qc. Devuelve {franja: {sesgo, sesgo_bruto, n, error_antes}}."""
    acum: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0])   # Σw, Σw·r, Σw·|r|, n
    for t, r in residuos:
        edad_dias = (ahora - t).total_seconds() / 86400
        if edad_dias < 0 or edad_dias > VENTANA_DIAS:
            continue
        w = 0.5 ** (edad_dias / VIDA_MEDIA_DIAS)
        a = acum[franja(t)]
        a[0] += w
        a[1] += w * r
        a[2] += w * abs(r)
        a[3] += 1
    out = {}
    for f, (sw, swr, swa, n) in acum.items():
        bruto = swr / sw
        out[f] = {"sesgo": max(-MAX_SESGO, min(MAX_SESGO, bruto * sw / (sw + K))),
                  "sesgo_bruto": bruto, "n": n, "error_antes": swa / sw}
    return out


# ---------------------------------------------------------------------------
# 4. Interpolación por cuadrantes

def _peso(d: float, e: dict, altura: float | None) -> float:
    w = 1 / (d + D0_KM) ** 2
    if altura is not None and e.get("altura") is not None:
        w *= math.exp(-abs(e["altura"] - altura) / ALTURA_ESCALA_M)
    return w


def interpolar(lat: float, lon: float, altura: float | None, costera: bool, estaciones: list[dict],
               excluir: str | None = None) -> dict | None:
    """Valor en un punto desde las estaciones [{id, nombre, lat, lon, altura, costera, valor}], solo de la misma
    zona (costa/interior). En cada cuadrante gana la de mayor peso (distancia y altura).
    (Ponderar por distancia al mar con Natural Earth 1:10M no mejoró la validación: 1,040 vs 1,026 °C.)
    Devuelve {valor, estaciones: [{nombre, km, peso}]} o None si no hay estaciones útiles."""
    cuadrantes: dict[int, tuple[float, float, dict]] = {}
    cos = math.cos(math.radians(lat))
    for e in estaciones:
        if e.get("valor") is None or e["id"] == excluir:
            continue
        if e["costera"] != costera:
            continue
        d = km(lat, lon, e["lat"], e["lon"])
        if d > RADIO_KM:
            continue
        w = _peso(d, e, altura)
        q = (e["lat"] >= lat) * 2 + ((e["lon"] - lon) * cos >= 0)
        if q not in cuadrantes or w > cuadrantes[q][0]:
            cuadrantes[q] = (w, d, e)
    if not cuadrantes:
        return None
    pesos = list(cuadrantes.values())
    total = sum(w for w, _, _ in pesos)
    valor = sum(w * e["valor"] for w, _, e in pesos) / (total + PESO_CERO)
    pesos.sort(key=lambda x: -x[0])
    return {"valor": valor,
            "estaciones": [{"nombre": e["nombre"], "km": round(d, 1), "peso": round(w / total, 2)}
                           for w, d, e in pesos]}


def correccion(lat: float, lon: float, altura: float | None, costera: bool, estaciones: list[dict],
               excluir: str | None = None) -> dict:
    """Sesgo de ICON interpolado en una ubicación, por franja. estaciones: [{id, nombre, lat, lon, altura,
    costera, sesgos: {franja: sesgo}}]. Devuelve {"franjas": {franja: °C a restar}, "estaciones": [...]}."""
    franjas, usadas = {}, []
    for f in range(4):
        r = interpolar(lat, lon, altura, costera,
                       [e | {"valor": e["sesgos"].get(f)} for e in estaciones], excluir)
        if r:
            franjas[f] = r["valor"]
            if len(r["estaciones"]) > len(usadas):
                usadas = r["estaciones"]
    return {"franjas": franjas, "estaciones": usadas}


def aplicar(rows: list[tuple], corr: dict) -> list[tuple]:
    """Resta la corrección a temperatura y sensación térmica de los modelos base en filas (modelo, hora, valores)."""
    if not corr["franjas"]:
        return rows
    out = []
    for modelo, t, valores in rows:
        delta = corr["franjas"].get(franja(t))
        if modelo in MODELOS_BASE and delta:
            valores = dict(valores)
            for col in ("temperatura", "sensacion_termica"):
                if valores.get(col) is not None:
                    valores[col] = valores[col] - delta
        out.append((modelo, t, valores))
    return out


def medicion_cercana(lat: float, lon: float, costera: bool, mediciones: list[dict],
                     radio: float = RADIO_MEDICION_KM) -> dict | None:
    """Última medición de la estación más cercana de la misma zona, con su distancia (km), o None.
    Es la que se muestra ("Medido en …"); el ajuste usa la anomalía interpolada."""
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


# ---------------------------------------------------------------------------
# 3. Persistencia de la anomalía (τ)

def ajustar_tau(anomalias: dict[str, dict[datetime, float]], max_lag: int = 6) -> tuple[float, dict[int, float]]:
    """τ (horas) de la persistencia de la anomalía: factor(L) = Σ a(t)·a(t+L) / Σ a(t)², ajustado a
    exp(−L/τ). anomalias: {estación: {hora: a}}. Con pocos datos devuelve TAU_H."""
    factores = {}
    for lag in range(1, max_lag + 1):
        num = den = 0.0
        pares = 0
        for serie in anomalias.values():
            for t, a in serie.items():
                b = serie.get(t + timedelta(hours=lag))
                if b is not None:
                    num += a * b
                    den += a * a
                    pares += 1
        if pares >= 100 and den > 0:
            factores[lag] = num / den
    if len(factores) < 3:
        return TAU_H, factores
    candidatos = [TAU_MIN_H + 0.5 * i for i in range(int((TAU_MAX_H - TAU_MIN_H) / 0.5) + 1)]
    tau = min(candidatos, key=lambda tau: sum((f - math.exp(-lag / tau)) ** 2 for lag, f in factores.items()))
    return tau, factores


# ---------------------------------------------------------------------------
# 5. Validación

def _mae(errores: list[float]) -> float | None:
    return round(sum(map(abs, errores)) / len(errores), 3) if errores else None


def validar(estaciones: list[dict], residuos: dict[str, dict[datetime, float]], tau: float) -> dict:
    """Error medio (°C) prediciendo cada estación: con ICON solo, sin la estación (como una comuna sin
    medición, solo con sus vecinas) y con la estación. "1 h" = ajuste del momento una hora después.
    estaciones: [{id, nombre, lat, lon, altura, costera, sesgos: {franja: sesgo}}];
    residuos: {estación: {hora: ICON − medido}} (solo qc ok)."""
    por_id = {e["id"]: e for e in estaciones}
    decae = math.exp(-1 / tau)
    anomalia = {sid: {t: por_id[sid]["sesgos"].get(franja(t), 0.0) - r for t, r in serie.items()}
                for sid, serie in residuos.items() if sid in por_id}
    por_hora: dict[datetime, list[dict]] = defaultdict(list)
    for sid, serie in anomalia.items():
        for t, a in serie.items():
            por_hora[t].append(por_id[sid] | {"valor": a})

    icon, sin_sesgo, sin_1h, con_sesgo, con_1h = [], [], [], [], []
    for e in estaciones:
        serie = residuos.get(e["id"])
        if not serie:
            continue
        vecinas = correccion(e["lat"], e["lon"], e.get("altura"), e["costera"], estaciones, excluir=e["id"])
        for t, r in serie.items():
            f = franja(t)
            icon.append(r)
            sv = vecinas["franjas"].get(f, 0.0)
            sin_sesgo.append(r - sv)
            con_sesgo.append(r - e["sesgos"].get(f, 0.0))
            previa = t - timedelta(hours=1)
            if previa in serie:
                a_propia = anomalia[e["id"]][previa]
                con_1h.append(r - (e["sesgos"].get(f, 0.0) - a_propia * decae))
                av = interpolar(e["lat"], e["lon"], e.get("altura"), e["costera"], por_hora.get(previa, []),
                                excluir=e["id"])
                if av:
                    sin_1h.append(r - (sv - av["valor"] * decae))
    return {"horas": len(icon), "tau_h": tau, "icon": _mae(icon),
            "sin_estacion": {"sesgo": _mae(sin_sesgo), "ahora_1h": _mae(sin_1h), "horas_1h": len(sin_1h)},
            "con_estacion": {"sesgo": _mae(con_sesgo), "ahora_1h": _mae(con_1h), "horas_1h": len(con_1h)}}
