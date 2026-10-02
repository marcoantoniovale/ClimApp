"""Mediciones de las estaciones automáticas (EMA) de la DMC (Dirección Meteorológica de Chile).

Fuentes (datos de "acceso y uso público" según el portal; responden desde GitHub Actions):
- Mapa nacional: https://climatologia.meteochile.gob.cl/application/index/menuTematicoEmas
  Una página con todas las EMA (~148): coordenadas y nombre (marcador del mapa) y la última medición
  (hora local, temperatura, humedad, viento en grados/nudos, presión). Se lee cada hora.
- Visor por estación: …/application/diariob/visorDeDatosEma/<código>
  Temperatura minuto a minuto de hoy y ayer. Se usa para cargar historia al empezar.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import http
from .units import plausible, to_ms

MAPA_URL = "https://climatologia.meteochile.gob.cl/application/index/menuTematicoEmas"
VISOR_URL = "https://climatologia.meteochile.gob.cl/application/diariob/visorDeDatosEma/{}"
CHILE = ZoneInfo("America/Santiago")


def _num(texto: str | None) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", texto or "")
    return float(m.group(0)) if m else None


def _hora_local(texto: str) -> datetime | None:
    try:
        return datetime.strptime(texto.strip(), "%d-%m-%Y %H:%M").replace(tzinfo=CHILE).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_mapa(page: str) -> list[dict]:
    """Última medición de cada estación del mapa nacional (una entrada por código)."""
    estaciones: dict[str, dict] = {}
    for m in re.finditer(r"bindPopup\(\"<div class='card'>(.*?)\"\);", page, re.S):
        popup = m.group(1)
        codigo = re.search(r"\((\d{6})\)</small>", popup)
        if not codigo or codigo.group(1) in estaciones:
            continue
        marcador = page.rfind("L.marker([", 0, m.start())
        coords = re.match(r"L\.marker\(\[(-?\d+\.\d+),\s*(-?\d+\.\d+)\][^)]*?title:\s*'([^']*)'", page[marcador:marcador + 300])
        fecha = re.search(r"text-blanco'>([^<]+)<", popup)
        h3 = re.findall(r"<h3>\s*(.*?)\s*</h3>", popup)
        h6 = re.findall(r"<h6>\s*(.*?)\s*</h6>", popup)
        if not coords:
            continue
        viento_txt = h6[1] if len(h6) > 1 else ""
        dir_vel = re.match(r"(\d+)°/(\d+)\(kt\)", viento_txt)
        if dir_vel:
            viento_dir, viento_vel = float(dir_vel.group(1)), to_ms(float(dir_vel.group(2)), "kn")
        elif viento_txt.lower().startswith("calma"):
            viento_dir, viento_vel = None, 0.0
        else:
            viento_dir = viento_vel = None
        estaciones[codigo.group(1)] = {
            "codigo": codigo.group(1),
            "nombre": html.unescape(coords.group(3)).strip(),
            "lat": float(coords.group(1)),
            "lon": float(coords.group(2)),
            "observed_at": _hora_local(fecha.group(1)) if fecha else None,
            "temperatura": plausible("temperatura", _num(h3[0] if h3 else None)),
            "humedad": plausible("humedad", _num(h6[0] if h6 else None)),
            "viento_vel": plausible("viento_vel", viento_vel),
            "viento_dir": plausible("viento_dir", viento_dir),
            "presion": plausible("presion", _num(h6[2] if len(h6) > 2 else None)),
        }
    return list(estaciones.values())


def parse_historial(page: str, hoy: date) -> dict[datetime, float]:
    """Temperatura horaria (en punto) de hoy y ayer desde el visor de una estación.

    Los minutos de cada serie son hora de Chile, pero el rótulo de la serie usa la fecha UTC: entre
    las 21:00 y las 24:00 (hora de verano) "hoy" aparece rotulado como mañana. Por eso las fechas se
    asignan por orden (la serie más reciente = hoy en Chile, la otra = ayer), no por el rótulo."""
    i = page.find('["00:00","00:01"')
    if i < 0:
        return {}
    horas = re.findall(r'"(\d\d:\d\d)"', re.match(r"\[[^\]]*\]", page[i:]).group(0))
    series = [(datetime.strptime(m.group(1), "%d-%m-%Y").date(), m.group(2))
              for m in re.finditer(r"name:\s*'(\d\d-\d\d-\d{4})',\s*data:\s*\[([^\]]*)\]", page[i:i + 80_000])]
    series = sorted(series[:2], key=lambda x: x[0], reverse=True)   # 2 primeras series = gráfico de temperatura
    obs = {}
    for k, (_, datos) in enumerate(series):
        dia = hoy - timedelta(days=k)
        for hhmm, valor in zip(horas, datos.split(",")):
            t = _num(valor)
            if t is None or not hhmm.endswith(":00"):
                continue
            instante = datetime(dia.year, dia.month, dia.day, int(hhmm[:2]), tzinfo=CHILE).astimezone(timezone.utc)
            obs[instante] = plausible("temperatura", t)
    return {k: v for k, v in obs.items() if v is not None}


def fetch_mapa(get_text=None) -> list[dict]:
    return parse_mapa((get_text or http.get_text)(MAPA_URL))


def fetch_historial(codigo: str, get_text=None, now: datetime | None = None) -> dict[datetime, float]:
    now = now or datetime.now(timezone.utc)
    serie = parse_historial((get_text or http.get_text)(VISOR_URL.format(codigo)), now.astimezone(CHILE).date())
    return {t: v for t, v in serie.items() if t <= now}
