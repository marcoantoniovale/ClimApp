"""Precálculo: JSON por ubicación listo para la API (docs/fase1-mapeo-requisitos.md §4.6).

Temperatura y sensación térmica: mezcla de ICON y ECMWF IFS (promedio por hora; máximas y mínimas: promedio
de las de cada modelo). Probabilidad de lluvia: la media de ICON y ECMWF, calibrada con mediciones (§10). El resto de las variables vienen de ICON (humedad: ICON +
ECMWF) y GFS aporta índice UV y visibilidad (docs/precision-evaluacion.md).

Lluvia y cielo (algoritmo ClimApp, §10, evaluado el 2026-10-06 con pluviógrafos DMC y METAR): la lluvia de
cada hora es la MEDIANA de ICON, ECMWF, GFS, UKMO y JMA; la hora "llueve" si la mediana es ≥ 0,2 mm, con
suavizado de 3 h (se rellena una hora seca entre dos de lluvia y se quita la lluvia aislada de una sola
hora). El código de cielo de los modelos
solo se usa para nieve, tormenta y el tipo de lluvia (chubasco/llovizna): la intensidad sale de los mm. La
neblina (código 45) se muestra si la humedad media es ≥ 93 % y no llueve; los códigos 45/48 de los modelos
no acertaron ninguna hora con niebla observada y se descartan.

Horas de lluvia: Open-Meteo rotula la lluvia (y su probabilidad, la nieve y el código del cielo) con la hora
en que TERMINA el período (la de 15:00 a 16:00 viene como 16:00). En el JSON cada hora describe el período
que EMPIEZA a esa hora, como Yr y Meteored (a_hora_de_inicio).
Unidades de salida: °C, %, mm, hPa, viento en km/h, oleaje en m. Horas en ISO 8601 con zona de Chile.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from zoneinfo import ZoneInfo

from .units import ms_to_kmh

CHILE = ZoneInfo("America/Santiago")
SCHEMA_VERSION = 2
HOURS_AHEAD = 48          # oleaje por hora
DAYS_AHEAD = 7           # hoy + 6 días
FUENTES = [
    {"nombre": "Open-Meteo", "licencia": "CC BY 4.0", "url": "https://open-meteo.com"},
    {"nombre": "Armada de Chile — Servicio Meteorológico", "url": "https://meteoarmada.directemar.cl"},
]


def _r(value, digits=1):
    return None if value is None else round(value, digits)


def _avg(values):
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def _circular_mean(degrees):
    degrees = [d for d in degrees if d is not None]
    if not degrees:
        return None
    s = sum(math.sin(math.radians(d)) for d in degrees)
    c = sum(math.cos(math.radians(d)) for d in degrees)
    return math.degrees(math.atan2(s, c)) % 360


def _consensus_code(codes):
    """Código WMO de consenso: el que repiten al menos dos modelos; si no, la mediana."""
    codes = [int(c) for c in codes if c is not None]
    if not codes:
        return None
    code, count = Counter(codes).most_common(1)[0]
    return code if count >= 2 else sorted(codes)[len(codes) // 2]


def _kmh(value):
    return None if value is None else round(ms_to_kmh(value))


def _iso_local(t: datetime) -> str:
    return t.astimezone(CHILE).isoformat(timespec="minutes")


POR_HORA_PREVIA = ("precipitacion", "precip_prob", "nieve", "estado_cielo")


def a_hora_de_inicio(rows) -> list:
    """Mueve las variables de "hora anterior" (POR_HORA_PREVIA) una hora antes: el valor de las 16:00
    (lluvia de 15 a 16) pasa a las 15:00. A la última hora de cada modelo le quedan sin dato."""
    siguiente = {(m, t): v for m, t, v in rows}
    out = []
    for m, t, v in rows:
        sig = siguiente.get((m, t + timedelta(hours=1)), {})
        out.append((m, t, {**v, **{c: sig.get(c) for c in POR_HORA_PREVIA if c in v}}))
    return out


# Probabilidad de lluvia calibrada (§10): logística sobre la probabilidad media de ICON + ECMWF (logit) y la
# fracción de modelos con ≥ 0,1 mm. Ajustada con 10.433 horas (pluviógrafos DMC y METAR); validación cruzada
# entre conjuntos: BSS +0,23 → +0,37/+0,43. Coeficientes (a, b, c) según los modelos con lluvia en la hora.
PROB_CALIBRACION = {5: (-2.463, 0.427, 2.04), 3: (-1.935, 0.536, 1.145)}
PROB_DIA_EXPONENTE = 0.5   # día: 1 − (Π(1 − p_hora))^0,5 (las horas de un mismo día no son independientes)


def probabilidad_calibrada(prob_media: float | None, mm_modelos: list[float]) -> float | None:
    """Probabilidad (%) de lluvia en la hora a partir de la media de ICON + ECMWF (%) y la lluvia de cada modelo."""
    if prob_media is None or not mm_modelos:
        return prob_media
    a, b, c = PROB_CALIBRACION[5 if len(mm_modelos) >= 5 else 3]
    raw = min(max(prob_media / 100, 0.01), 0.99)
    fraccion = sum(v >= 0.1 for v in mm_modelos) / len(mm_modelos)
    return 100 / (1 + math.exp(-(a + b * math.log(raw / (1 - raw)) + c * fraccion)))


def probabilidad_del_dia(probs: list[float]) -> float | None:
    """Probabilidad (%) de que llueva en algún momento del día, desde las probabilidades calibradas por hora."""
    probs = [p for p in probs if p is not None]
    if not probs:
        return None
    return 100 * (1 - math.prod(1 - p / 100 for p in probs) ** PROB_DIA_EXPONENTE)


LLUVIA_MM = 0.2          # mediana de modelos para que una hora "llueva" (§10)
NEBLINA_HR = 93          # humedad media (%) para neblina, sin lluvia (§10)
_NIEVE_TORMENTA = {71, 73, 75, 77, 85, 86, 95, 96, 99}
_HELADA = {56, 57, 66, 67}
_LLUVIA_MODELO = set(range(51, 68)) | {80, 81, 82}


def _lluvia_horaria(values):
    """Lluvia de la hora: mediana de los modelos con dato (con menos de 3, el promedio)."""
    values = [v for v in values if v is not None]
    if not values:
        return None
    return median(values) if len(values) >= 3 else mean(values)


def _nubes(nubosidad) -> int:
    if nubosidad is None or nubosidad >= 70:
        return 3
    return 2 if nubosidad >= 30 else 1


def cielo_por_hora(hours: dict[datetime, dict]) -> None:
    """Ajusta en el lugar `estado_cielo` de cada hora según la lluvia mediana suavizada y la humedad (§10)."""
    hora = timedelta(hours=1)
    cruda = {t for t, h in hours.items() if (h["precipitacion"] or 0) >= LLUVIA_MM}
    # Suavizado en dos pasos: se rellena una hora seca entre dos de lluvia y luego se quita la lluvia de
    # una hora aislada (rinde como la mayoría de 3 h, pero "lluvia, seca, lluvia" queda como 3 h de lluvia).
    rellena = cruda | {t for t in hours if t - hora in cruda and t + hora in cruda}
    lluvia = {t for t in rellena if t - hora in rellena or t + hora in rellena}
    for t, h in hours.items():
        llueve = t in lluvia
        code, mm = h["estado_cielo"], h["precipitacion"] or 0
        if code in _NIEVE_TORMENTA:
            continue
        if llueve:
            if code in _HELADA:
                continue
            if code in (80, 81, 82):
                h["estado_cielo"] = 80 if mm < 0.5 else 81 if mm < 4 else 82
            elif code in (51, 53, 55) and mm < 1:
                h["estado_cielo"] = 51 if mm < 0.5 else 53
            else:
                h["estado_cielo"] = 61 if mm < 0.5 else 63 if mm < 4 else 65
        elif h["humedad"] is not None and h["humedad"] >= NEBLINA_HR and mm < 0.1:
            h["estado_cielo"] = 45
        elif code is None or code in _LLUVIA_MODELO or code in (45, 48):
            h["estado_cielo"] = None if code is None and h["nubosidad"] is None else _nubes(h["nubosidad"])


PROXIMA_HORAS = 48       # horizonte de "próxima lluvia"
_ES_LLUVIA = set(range(51, 68)) | {80, 81, 82, 95, 96, 99}


def proxima_lluvia(rows, hours: dict[datetime, dict], desde: datetime) -> dict | None:
    """Próxima lluvia en PROXIMA_HORAS (vista de fiabilidad, RF05.3).
    - inicio/fin: primer tramo continuo de horas con lluvia de consenso (cielo de cielo_por_hora).
    - desde/hasta: rango de la hora en que la empieza cada modelo (primera hora ≥ LLUVIA_MM), con cuántos
      modelos la traen. rows ya en hora de inicio (a_hora_de_inicio). None si ningún modelo da lluvia."""
    hasta = desde + timedelta(hours=PROXIMA_HORAS)
    hora = timedelta(hours=1)
    lluvia = sorted(t for t, h in hours.items() if desde <= t < hasta and h["estado_cielo"] in _ES_LLUVIA)
    por_modelo: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for m, t, v in rows:
        if desde <= t < hasta and v.get("precipitacion") is not None:
            por_modelo[m].append((t, v["precipitacion"]))
    inicios = [t0 for serie in por_modelo.values()
               if (t0 := next((t for t, mm in sorted(serie) if mm >= LLUVIA_MM), None)) is not None]
    if not lluvia and not inicios:
        return None
    out = {"modelos": len(por_modelo), "modelos_con_lluvia": len(inicios)}
    if inicios:
        out |= {"desde": _iso_local(min(inicios)), "hasta": _iso_local(max(inicios))}
    if lluvia:
        fin, tramo = lluvia[0], set(lluvia)
        while fin + hora in tramo:
            fin += hora
        out |= {"inicio": _iso_local(lluvia[0]), "fin": _iso_local(fin + hora)}
    return out


NEBLINA_HORAS_DIA = 8    # horas de neblina para que el resumen del día diga "Neblina"


def cielo_del_dia(codes: list[int]) -> int | None:
    """Cielo del resumen diario: el más severo, salvo la neblina, que solo manda si dura NEBLINA_HORAS_DIA
    (una hora de neblina de madrugada no convierte el día en "Neblina")."""
    if not codes:
        return None
    resto = [c for c in codes if c not in (45, 48)]
    if not resto or (sum(c in (45, 48) for c in codes) >= NEBLINA_HORAS_DIA and max(resto) < 51):
        return 45
    return max(resto)


def consensus_hours(rows) -> dict[datetime, dict]:
    """rows: (modelo, valid_time, valores) → por hora: promedio de modelos y rango de temperatura;
    lluvia: mediana de modelos; cielo ajustado con cielo_por_hora."""
    by_time: dict[datetime, list[dict]] = defaultdict(list)
    for _, t, values in rows:
        by_time[t].append(values)
    hours = {}
    for t, models in sorted(by_time.items()):
        temps = [m["temperatura"] for m in models if m.get("temperatura") is not None]
        hours[t] = {
            "temperatura": _avg(temps),
            "temperatura_min": min(temps) if temps else None,
            "temperatura_max": max(temps) if temps else None,
            "sensacion_termica": _avg(m.get("sensacion_termica") for m in models),
            "estado_cielo": _consensus_code(m.get("estado_cielo") for m in models),
            "indice_uv": _avg(m.get("indice_uv") for m in models),
            "humedad": _avg(m.get("humedad") for m in models),
            "precip_prob": probabilidad_calibrada(_avg(m.get("precip_prob") for m in models),
                                                  [m["precipitacion"] for m in models if m.get("precipitacion") is not None]),
            "precipitacion": _lluvia_horaria(m.get("precipitacion") for m in models),
            "viento_vel": _avg(m.get("viento_vel") for m in models),
            "viento_dir": _circular_mean(m.get("viento_dir") for m in models),
            "viento_rafaga": _avg(m.get("viento_rafaga") for m in models),
            "presion": _avg(m.get("presion") for m in models),
            "punto_rocio": _avg(m.get("punto_rocio") for m in models),
            "nubosidad": _avg(m.get("nubosidad") for m in models),
            "visibilidad": _avg(m.get("visibilidad") for m in models),
            "isoterma_0": _avg(m.get("isoterma_0") for m in models),
            "nieve": _avg(m.get("nieve") for m in models),
            "modelos": len(models),
        }
    cielo_por_hora(hours)
    return hours


def daily(rows, start_day, days: int) -> list[dict]:
    """Resumen diario (día de Chile). Máx./mín. por modelo y luego promedio y rango entre modelos."""
    per_model_day: dict[tuple[str, object], list[dict]] = defaultdict(list)
    for model, t, values in rows:
        per_model_day[(model, t.astimezone(CHILE).date())].append(values)
    hours = consensus_hours(rows)
    hours_by_day: dict[object, list[dict]] = defaultdict(list)
    for t, h in hours.items():
        hours_by_day[t.astimezone(CHILE).date()].append(h)

    result = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        tmax, tmin, rain = [], [], []
        for (model, d), values in per_model_day.items():
            if d != day:
                continue
            temps = [v["temperatura"] for v in values if v.get("temperatura") is not None]
            if len(temps) >= 18:          # día casi completo para ese modelo
                tmax.append(max(temps))
                tmin.append(min(temps))
            lluvias = [v["precipitacion"] for v in values if v.get("precipitacion") is not None]
            if lluvias:   # solo modelos que pronostican lluvia (los que no la traen no cuentan como 0)
                rain.append(sum(lluvias))
        hs = hours_by_day.get(day, [])
        if not hs:
            continue
        codes = [h["estado_cielo"] for h in hs if h["estado_cielo"] is not None]
        result.append({
            "fecha": day.isoformat(),
            "temperatura_max": _r(_avg(tmax)),
            "temperatura_min": _r(_avg(tmin)),
            "rango_max": [_r(min(tmax)), _r(max(tmax))] if tmax else None,
            "rango_min": [_r(min(tmin)), _r(max(tmin))] if tmin else None,
            "estado_cielo": cielo_del_dia(codes),
            "precip_prob": _r(probabilidad_del_dia([h["precip_prob"] for h in hs]), 0),
            "precipitacion": _r(_lluvia_horaria(rain)),   # mediana de los totales de cada modelo
            "viento_max": _kmh(max((h["viento_vel"] for h in hs if h["viento_vel"] is not None), default=None)),
            "rafaga_max": _kmh(max((h["viento_rafaga"] for h in hs if h["viento_rafaga"] is not None), default=None)),
            "indice_uv_max": _r(max((h["indice_uv"] for h in hs if h["indice_uv"] is not None), default=None)),
            "viento_dir": _r(_circular_mean(h["viento_dir"] for h in hs), 0),
            "nieve": _r(sum(h["nieve"] or 0 for h in hs)),
            "isoterma_0_min": _r(min((h["isoterma_0"] for h in hs if h["isoterma_0"] is not None), default=None), 0),
            "horas": len(hs),
        })
    return result


def marine_summary(marine, now: datetime) -> dict | None:
    if not marine:
        return None
    future = [(t, v) for t, v in sorted(marine) if t >= now.replace(minute=0, second=0, microsecond=0)]
    by_day: dict[object, list[dict]] = defaultdict(list)
    for t, v in future:
        by_day[t.astimezone(CHILE).date()].append(v)
    return {
        "horas": [{"hora": _iso_local(t), "altura": _r(v["oleaje_altura"]), "periodo": _r(v["oleaje_periodo"], 0),
                   "direccion": _r(v["oleaje_dir"], 0), "marejada": _r(v["marejada_altura"])}
                  for t, v in future[:HOURS_AHEAD:3]],
        "dias": [{"fecha": d.isoformat(),
                  "altura_max": _r(max((v["oleaje_altura"] for v in vs if v["oleaje_altura"] is not None), default=None)),
                  "periodo_max": _r(max((v["oleaje_periodo"] for v in vs if v["oleaje_periodo"] is not None), default=None), 0),
                  "direccion": _r(_circular_mean(v["oleaje_dir"] for v in vs), 0)}
                 for d, vs in list(by_day.items())[:DAYS_AHEAD]],
    }


def build(location: dict, rows, marine, observation: dict | None, fetched_at: datetime | None,
          now: datetime | None = None, corridas: dict[str, str] | None = None,
          cercanas: list[dict] | None = None, correccion: dict | None = None) -> dict:
    """Arma el JSON de una ubicación. rows: (modelo, valid_time, valores) de forecast_current."""
    now = now or datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    rows = a_hora_de_inicio(rows)
    hours = consensus_hours(rows)
    last_day = now.astimezone(CHILE).date() + timedelta(days=DAYS_AHEAD - 1)
    upcoming = [(t, h) for t, h in hours.items()
                if t >= current_hour and t.astimezone(CHILE).date() <= last_day]
    models = sorted({m for m, _, _ in rows})
    dias = daily(rows, now.astimezone(CHILE).date(), DAYS_AHEAD)

    return {
        "version": SCHEMA_VERSION,
        "ubicacion": {**{k: location[k] for k in ("slug", "nombre", "region", "tipo", "lat", "lon", "es_costera")},
                      "altura_m": location.get("altura_m")},
        "generado": _iso_local(now),
        "actualizado": _iso_local(fetched_at) if fetched_at else None,
        "provisional": not (correccion and correccion["franjas"]),
        "fuente": {"modelo": "ICON (DWD) + ECMWF IFS",
                   "complementario": "GFS (índice UV y visibilidad); lluvia: mediana de ICON, ECMWF, GFS, UKMO y JMA"},
        "modelos": models,
        "corridas": {m: corridas[m] for m in models if corridas and m in corridas},  # inicio de cada corrida
        "unidades": {"temperatura": "°C", "precipitacion": "mm", "viento": "km/h", "presion": "hPa",
                     "humedad": "%", "oleaje": "m"},
        "horas": [{
            "hora": _iso_local(t),
            "temperatura": _r(h["temperatura"]),
            "rango": [_r(h["temperatura_min"]), _r(h["temperatura_max"])],
            "sensacion_termica": _r(h["sensacion_termica"]),
            "estado_cielo": h["estado_cielo"],
            "indice_uv": _r(h["indice_uv"]),
            "humedad": _r(h["humedad"], 0),
            "precip_prob": _r(h["precip_prob"], 0),
            "precipitacion": _r(h["precipitacion"]),
            "viento": _kmh(h["viento_vel"]),
            "viento_dir": _r(h["viento_dir"], 0),
            "rafaga": _kmh(h["viento_rafaga"]),
            "presion": _r(h["presion"], 0),
            "punto_rocio": _r(h["punto_rocio"]),
            "nubosidad": _r(h["nubosidad"], 0),
            "visibilidad": _r(h["visibilidad"], -2),
            "isoterma_0": _r(h["isoterma_0"], -1),
            "nieve": _r(h["nieve"]),
        } for t, h in upcoming],
        "dias": dias,
        "proxima_lluvia": proxima_lluvia(rows, hours, current_hour),
        "alertas": alertas_paso(dias, location.get("altura_m")) if location.get("tipo") == "paso" else [],
        "marino": marine_summary(marine, now) if location.get("es_costera") else None,
        "observacion": observation,
        "cercanas": cercanas or [],
        "correccion": {  # algoritmo ClimApp: temperatura de ICON corregida con estaciones DMC cercanas
            "aplicada": bool(correccion and correccion["franjas"]),
            "estaciones": (correccion or {}).get("estaciones", []),
            "franjas": {str(k): round(v, 2) for k, v in (correccion or {}).get("franjas", {}).items()},
        },
        "fuentes": FUENTES,
    }


# Alertas propias para pasos fronterizos (umbrales iniciales; a calibrar con la experiencia).
NIEVE_AVISO_CM, NIEVE_ALERTA_CM = 1.0, 10.0
VENTISCA_RAFAGA_KMH = 50
RAFAGA_AVISO_KMH, RAFAGA_ALERTA_KMH = 60, 80
# En el altiplano (≥ 3.500 m) el viento fuerte es habitual: umbrales más altos para no saturar.
ALTIPLANO_M = 3500
RAFAGA_AVISO_ALTIPLANO_KMH, RAFAGA_ALERTA_ALTIPLANO_KMH = 75, 95
FRIO_EXTREMO_C = -10.0


def alertas_paso(dias: list[dict], altura_m: float | None) -> list[dict]:
    """Alertas por día para un paso a partir del resumen diario (ICON ajustado a la altura del paso).
    nivel: 'alerta' (riesgo alto) o 'aviso'."""
    out = []
    altiplano = (altura_m or 0) >= ALTIPLANO_M
    aviso_kmh = RAFAGA_AVISO_ALTIPLANO_KMH if altiplano else RAFAGA_AVISO_KMH
    alerta_kmh = RAFAGA_ALERTA_ALTIPLANO_KMH if altiplano else RAFAGA_ALERTA_KMH
    for d in dias:
        nieve = d.get("nieve") or 0
        rafaga = d.get("rafaga_max") or 0
        tmin = d.get("temperatura_min")
        iso = d.get("isoterma_0_min")
        lluvia = d.get("precipitacion") or 0

        def add(nivel, tipo, texto):
            out.append({"fecha": d["fecha"], "nivel": nivel, "tipo": tipo, "texto": texto})

        if nieve >= NIEVE_ALERTA_CM:
            add("alerta", "nieve", f"Nieve intensa: {nieve:.0f} cm")
        elif nieve >= NIEVE_AVISO_CM:
            add("aviso", "nieve", f"Nieve: {nieve:.0f} cm")
        if nieve > 0 and rafaga >= VENTISCA_RAFAGA_KMH:
            add("alerta", "ventisca", f"Ventisca: nieve con ráfagas de {rafaga} km/h")
        elif rafaga >= alerta_kmh:
            add("alerta", "viento", f"Viento muy fuerte: ráfagas de {rafaga} km/h")
        elif rafaga >= aviso_kmh:
            add("aviso", "viento", f"Viento fuerte: ráfagas de {rafaga} km/h")
        if tmin is not None and tmin <= FRIO_EXTREMO_C:
            add("aviso", "frio", f"Frío extremo: mínima de {tmin:.0f} °C")
        if (altura_m and iso is not None and iso < altura_m and lluvia >= 1 and nieve < NIEVE_AVISO_CM):
            add("aviso", "hielo", f"Precipitación con isoterma 0 °C bajo el paso ({iso:.0f} m): posible nieve o hielo")
    return out
