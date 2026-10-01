"""Exporta el polígono simplificado de cada comuna a web/public/geo/<slug>.json.

Lo usa "Usar mi ubicación" en la web: el navegador descarga solo los polígonos de las comunas
cuya cabecera está más cerca y verifica en cuál cae la posición (la ubicación no sale del equipo).

Simplificación adaptativa: ~55 m de detalle; si el archivo supera MAX_BYTES (archipiélagos del sur)
se simplifica más hasta caber. Coordenadas con 4 decimales (~11 m).

Requiere los polígonos descargados por scripts/build_coast.py (data/cache/) y shapely:
  pip install -e ".[catalogo]"
Uso: python scripts/export_geo.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_seed import slugify  # noqa: E402

CACHE = ROOT / "data" / "cache"
OUT = ROOT.parent / "web" / "public" / "geo"
TOLERANCES = (0.0005, 0.001, 0.002, 0.004, 0.008)
MAX_BYTES = 60_000


def quantize(coords, digits=4):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], digits), round(coords[1], digits)]
    return [quantize(c, digits) for c in coords]


def main() -> None:
    if not list(CACHE.glob("comunas_r*.geojson")):
        sys.exit("Faltan los polígonos en data/cache/: ejecuta antes scripts/build_coast.py")
    with open(ROOT / "data" / "catalog" / "comunas.csv", encoding="utf-8") as f:
        slugs = {r["cut"]: slugify(r["nombre"]) for r in csv.DictReader(f)}

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()

    total, coarse = 0, []
    for path in sorted(CACHE.glob("comunas_r*.geojson")):
        for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
            cut = feature["properties"]["codigo_comuna"].zfill(5)
            geom = shape(feature["geometry"])
            for tol in TOLERANCES:
                simple = mapping(geom.simplify(tol, preserve_topology=True))
                body = json.dumps({"slug": slugs[cut], "type": simple["type"],
                                   "coordinates": quantize(simple["coordinates"])}, separators=(",", ":"))
                if len(body) <= MAX_BYTES:
                    break
            if tol != TOLERANCES[0]:
                coarse.append(f"{slugs[cut]} ({tol}°)")
            (OUT / f"{slugs[cut]}.json").write_text(body, encoding="utf-8")
            total += len(body)

    print(f"{len(list(OUT.glob('*.json')))} polígonos, {total / 1024 / 1024:.1f} MB en {OUT}")
    print(f"simplificados de más por tamaño: {', '.join(coarse) or 'ninguno'}")


if __name__ == "__main__":
    main()
