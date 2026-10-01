"""Exporta el catálogo (data/catalog/*.csv) como SQL de carga inicial en db/seeds/.

Uso: python scripts/export_seed.py
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "catalog"
SEEDS = ROOT.parent / "db" / "seeds"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def sql_str(value: str) -> str:
    return "null" if value == "" else "'" + value.replace("'", "''") + "'"


def read_csv(name: str) -> list[dict]:
    with open(CATALOG / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    comunas = read_csv("comunas.csv")
    estaciones = read_csv("estaciones_armada.csv")

    lines = [
        "-- Generado por etl/scripts/export_seed.py a partir de etl/data/catalog. No editar a mano.",
        "begin;",
        "",
        "insert into locations (tipo, cut, slug, nombre, alias, region_id, region, lat, lon) values",
    ]
    lines.append(",\n".join(
        f"  ('comuna', {sql_str(c['cut'])}, {sql_str(slugify(c['nombre']))}, {sql_str(c['nombre'])}, "
        f"{sql_str(c['alias'])}, {sql_str(c['region_id'])}, {sql_str(c['region'])}, {c['lat']}, {c['lon']})"
        for c in comunas
    ) + "\non conflict (cut) do update set nombre = excluded.nombre, alias = excluded.alias,"
        " lat = excluded.lat, lon = excluded.lon;")

    lines += ["", "insert into stations (id, red, nombre, lat, lon, location_id) values"]
    lines.append(",\n".join(
        f"  ({sql_str(s['id'])}, {sql_str(s['red'])}, {sql_str(s['nombre'])}, {s['lat']}, {s['lon']}, "
        f"(select id from locations where cut = {sql_str(s['comuna_cut'])}))"
        for s in estaciones if s["coord_valida"] == "True"
    ) + "\non conflict (id) do update set nombre = excluded.nombre, lat = excluded.lat,"
        " lon = excluded.lon, location_id = excluded.location_id;")
    lines += ["", "commit;", ""]

    SEEDS.mkdir(parents=True, exist_ok=True)
    out = SEEDS / "0001_catalogo.sql"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{out.relative_to(ROOT.parent)}: {len(comunas)} comunas, {len(estaciones)} estaciones")


if __name__ == "__main__":
    main()
