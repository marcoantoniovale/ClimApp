"""Pronóstico oficial de pasos fronterizos de la DMC (Dirección Meteorológica de Chile).

Fuente: https://archivos.meteochile.gob.cl/portaldmc/pasos/pronostico_pasos_fronterizos.php, que
carga un archivo JavaScript por región (catálogo en data/catalog/pasos.csv). Cada archivo trae:
  fechaemision[_Region]   "Jueves 01 de Octubre del 2026 a las 17:35 horas"
  PronoFechas[_Region]    "Viernes 02:Sábado 03:…"          (5 días, desde mañana)
  apreciacion[_Region]    situación sinóptica
  PronoIsotermas[_Region] "3200-1800:1800-2300:…"           (isoterma 0 °C por día)
  Prono<Paso>             "icono.png|texto:icono.png|texto…" (5 días)
Los archivos incluyen en su primera línea el nombre y la IP de quien los redacta: no se leen ni se
guardan.
"""

from __future__ import annotations

import csv
import html
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import http

BASE_URL = "https://archivos.meteochile.gob.cl/portaldmc/meteochile/js/"
CATALOG = Path(__file__).resolve().parents[2] / "data" / "catalog" / "pasos.csv"
CHILE = ZoneInfo("America/Santiago")


def catalogo() -> list[dict]:
    with open(CATALOG, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _var(js: str, prefix: str) -> str | None:
    """Valor de `var <prefix>[_Sufijo]="…";` (primer match)."""
    m = re.search(rf'var {prefix}(?:_\w+)?\s*=\s*"((?:[^"\\]|\\.)*)"', js)
    return html.unescape(m.group(1)).strip() if m else None


def _fechas(etiquetas: list[str], hoy: date) -> list[date | None]:
    """'Viernes 02' → la próxima fecha (desde hoy) con ese día del mes."""
    out = []
    for e in etiquetas:
        m = re.search(r"(\d{1,2})\s*$", e)
        fecha = None
        if m:
            for k in range(0, 10):
                d = hoy + timedelta(days=k)
                if d.day == int(m.group(1)):
                    fecha = d
                    break
        out.append(fecha)
    return out


def parse(js: str, variable: str, hoy: date) -> dict | None:
    """Pronóstico de un paso desde el archivo de su región, o None si la variable no está."""
    prono = _var(js, re.escape(variable) + r"(?![A-Za-z0-9])")
    if prono is None:
        return None
    etiquetas = [e.strip() for e in (_var(js, "PronoFechas") or "").split(":") if e.strip()]
    isotermas = [i.strip() for i in (_var(js, "PronoIsotermas") or "").split(":")]
    entradas = [e for e in re.split(r":(?=[\w-]+\.png\|)", prono) if e.strip()]
    fechas = _fechas(etiquetas, hoy)
    dias = []
    for i, entrada in enumerate(entradas):
        fecha = fechas[i] if i < len(fechas) else None
        icono, _, texto = entrada.partition("|")
        dias.append({
            "fecha": fecha.isoformat() if fecha else None,
            "etiqueta": etiquetas[i] if i < len(etiquetas) else None,
            "icono": icono.strip() or None,
            "texto": texto.strip().rstrip(".") + "." if texto.strip() else None,
            "isoterma": isotermas[i] if i < len(isotermas) and isotermas[i] else None,
        })
    return {
        "emision": _var(js, "fechaemision"),
        "apreciacion": _var(js, "apreciacion"),
        "dias": dias,
    }


def fetch(get_text=None, now: datetime | None = None) -> tuple[dict[str, dict], list[str]]:
    """Pronóstico DMC de todos los pasos del catálogo → ({slug: pronóstico}, errores)."""
    get_text = get_text or http.get_text
    hoy = (now or datetime.now(timezone.utc)).astimezone(CHILE).date()
    archivos: dict[str, str | None] = {}
    resultado, errores = {}, []
    for paso in catalogo():
        nombre = paso["dmc_archivo"]
        if nombre not in archivos:
            try:
                archivos[nombre] = get_text(BASE_URL + nombre)
            except Exception as exc:  # un archivo caído no detiene a los demás
                archivos[nombre] = None
                errores.append(f"{nombre}: {exc}")
        js = archivos[nombre]
        datos = parse(js, paso["dmc_variable"], hoy) if js else None
        if datos:
            resultado[paso["slug"]] = datos
        elif js:
            errores.append(f"{paso['slug']}: no se encontró {paso['dmc_variable']}")
    return resultado, errores
