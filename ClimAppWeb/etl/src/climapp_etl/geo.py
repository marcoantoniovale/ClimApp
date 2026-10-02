"""Comuna de un punto con los polígonos comunales de la web (ClimAppWeb/web/public/geo/<slug>.json).

Las estaciones se ubican por polígono y no por la cabecera más cercana: con la cabecera, Quinta Normal
caía en Estación Central y Pudahuel en Quilicura.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GEO_DIR = Path(__file__).resolve().parents[3] / "web" / "public" / "geo"


def _en_anillo(x: float, y: float, anillo: list) -> bool:
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i]
        xj, yj = anillo[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


@lru_cache(maxsize=1)
def _poligonos() -> list[tuple]:
    out = []
    for archivo in sorted(GEO_DIR.glob("*.json")):
        g = json.loads(archivo.read_text(encoding="utf-8"))
        for p in g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]:
            xs = [x for x, _ in p[0]]
            ys = [y for _, y in p[0]]
            out.append((g["slug"], p, min(xs), max(xs), min(ys), max(ys)))
    return out


def comuna_de(lat: float, lon: float) -> str | None:
    """Slug de la comuna que contiene el punto, o None (mar, fuera de Chile o sin polígonos)."""
    for slug, p, x0, x1, y0, y1 in _poligonos():
        if x0 <= lon <= x1 and y0 <= lat <= y1 and _en_anillo(lon, lat, p[0]) \
                and not any(_en_anillo(lon, lat, hueco) for hueco in p[1:]):
            return slug
    return None
