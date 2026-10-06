"""Catálogo de puertos → data/catalog/puertos.csv (con su comuna) y web/public/puertos.json (buscador).

Fuente curada a mano: data/catalog/puertos_fuente.csv (capitanías y estaciones de la Armada con nombre
real, más puertos principales que no tienen estación: Antofagasta, Castro, Punta Arenas, Porvenir,
Puerto Williams). Comuna: la que contiene el punto (polígonos de web/public/geo); si cae en el mar, la
comuna costera de cabecera más cercana. Después: scripts/export_seed.py y scripts/migrate.py --seed.

Uso: python scripts/build_puertos.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from climapp_etl import correccion, geo  # noqa: E402

CATALOG = ROOT / "data" / "catalog"
WEB_INDEX = ROOT.parent / "web" / "public" / "puertos.json"


def slugify(s: str) -> str:
    import re
    import unicodedata
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()).strip("-")


def main() -> None:
    comunas = list(csv.DictReader((CATALOG / "comunas.csv").open(encoding="utf-8")))
    costeras = {r["cut"] for r in csv.DictReader((CATALOG / "comunas_costa.csv").open(encoding="utf-8"))
                if r["es_costera"] == "True"}
    por_slug = {slugify(c["nombre"]): c for c in comunas}
    filas = []
    for p in csv.DictReader((CATALOG / "puertos_fuente.csv").open(encoding="utf-8")):
        lat, lon = float(p["lat"]), float(p["lon"])
        slug = geo.comuna_de(lat, lon)
        if slug not in por_slug:   # en el mar (o sin polígono): la cabecera costera más cercana
            slug = slugify(min((c for c in comunas if c["cut"] in costeras),
                               key=lambda c: correccion.km(lat, lon, float(c["lat"]), float(c["lon"])))["nombre"])
        filas.append({"slug": p["slug"], "nombre": p["nombre"], "comuna": slug, "comuna_nombre": por_slug[slug]["nombre"],
                      "lat": p["lat"], "lon": p["lon"]})
    with (CATALOG / "puertos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "nombre", "comuna", "lat", "lon"])
        w.writeheader()
        w.writerows({k: f[k] for k in ("slug", "nombre", "comuna", "lat", "lon")} for f in filas)
    WEB_INDEX.write_text(json.dumps([{"s": f["slug"], "n": f["nombre"], "c": f["comuna"]} for f in filas],
                                    ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for f in filas:
        print(f"  {f['nombre']:20} → {f['comuna_nombre']}")
    print(f"{len(filas)} puertos → {CATALOG / 'puertos.csv'} y {WEB_INDEX}")


if __name__ == "__main__":
    main()
