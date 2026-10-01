"""Marca las comunas costeras: las que tienen costa en el océano (o mares interiores, fiordos).

Método: distancia entre el polígono oficial de cada comuna y la línea de costa de Natural Earth
(1:10 millones). Es costera si la distancia es <= UMBRAL_KM. Los lagos no cuentan como costa.

Fuentes (se descargan a data/cache/, que no se versiona):
- Polígonos de comunas: paquete chilemapas (Apache-2.0), data_geojson/comunas/rXX.geojson.
- Línea de costa: Natural Earth ne_10m_coastline (dominio público).

Salida: data/catalog/comunas_costa.csv (cut, es_costera, dist_costa_km).

Requiere shapely:  pip install -e ".[catalogo]"
Uso:               python scripts/build_coast.py
"""

from __future__ import annotations

import csv
import json
import math
import urllib.request
from pathlib import Path

from shapely.geometry import box, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
CATALOG = ROOT / "data" / "catalog"

COMUNAS_URL = "https://raw.githubusercontent.com/pachadotdev/chilemapas/HEAD/data_geojson/comunas/r{:02d}.geojson"
COAST_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson"
CHILE_BBOX = box(-110.0, -60.0, -66.0, -17.0)   # sin la Antártica (no está en chilemapas)
UMBRAL_KM = 1.5   # Alto Hospicio (2,0 km, sin costa) queda fuera; Chanco (1,0 km) dentro


def cached(url: str, name: str) -> dict:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "ClimApp-catalog/0.1"})
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return json.loads(path.read_text(encoding="utf-8"))


def to_km(geom, lat0: float):
    """Proyección equirectangular local (km) centrada en lat0; suficiente para distancias cortas."""
    kx = 111.32 * math.cos(math.radians(lat0))
    return transform(lambda x, y, z=None: (x * kx, y * 110.57), geom)


def main() -> None:
    coast = cached(COAST_URL, "ne_10m_coastline.geojson")
    coastline = unary_union([shape(f["geometry"]) for f in coast["features"]]).intersection(CHILE_BBOX)

    polygons: dict[str, object] = {}
    for region in range(1, 17):
        data = cached(COMUNAS_URL.format(region), f"comunas_r{region:02d}.geojson")
        for f in data["features"]:
            polygons[f["properties"]["codigo_comuna"].zfill(5)] = shape(f["geometry"])

    with open(CATALOG / "comunas.csv", encoding="utf-8") as fh:
        comunas = list(csv.DictReader(fh))

    rows = []
    for c in comunas:
        poly = polygons.get(c["cut"])
        if poly is None:   # Antártica: sin polígono; su cabecera (Villa Las Estrellas) está en la costa
            rows.append({"cut": c["cut"], "es_costera": True, "dist_costa_km": 0.0})
            continue
        lat0 = poly.centroid.y
        near = coastline.intersection(poly.envelope.buffer(0.5))
        dist = to_km(poly, lat0).distance(to_km(near, lat0)) if not near.is_empty else math.inf
        rows.append({"cut": c["cut"], "es_costera": dist <= UMBRAL_KM,
                     "dist_costa_km": round(dist, 1) if dist != math.inf else ""})

    with open(CATALOG / "comunas_costa.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["cut", "es_costera", "dist_costa_km"])
        writer.writeheader()
        writer.writerows(rows)

    costeras = sum(r["es_costera"] for r in rows)
    print(f"comunas: {len(rows)}  costeras: {costeras}  sin polígono: "
          f"{[c['cut'] for c in comunas if c['cut'] not in polygons]}")


if __name__ == "__main__":
    main()
