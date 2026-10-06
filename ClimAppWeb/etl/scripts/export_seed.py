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
    costeras = {r["cut"] for r in read_csv("comunas_costa.csv") if r["es_costera"] == "True"}

    lines = [
        "-- Generado por etl/scripts/export_seed.py a partir de etl/data/catalog. No editar a mano.",
        "-- Idempotente: se puede volver a aplicar con etl/scripts/migrate.py --seed.",
        "",
        "insert into locations (tipo, cut, slug, nombre, alias, region_id, region, lat, lon, es_costera) values",
    ]
    lines.append(",\n".join(
        f"  ('comuna', {sql_str(c['cut'])}, {sql_str(slugify(c['nombre']))}, {sql_str(c['nombre'])}, "
        f"{sql_str(c['alias'])}, {sql_str(c['region_id'])}, {sql_str(c['region'])}, {c['lat']}, {c['lon']}, "
        f"{'true' if c['cut'] in costeras else 'false'})"
        for c in comunas
    ) + "\non conflict (cut) do update set nombre = excluded.nombre, alias = excluded.alias,"
        " lat = excluded.lat, lon = excluded.lon, es_costera = excluded.es_costera;")

    pasos = read_csv("pasos.csv")
    lines += ["", "-- Pasos fronterizos (catálogo pasos.csv); slug con prefijo para no chocar con comunas.",
              "insert into locations (tipo, slug, nombre, region_id, region, lat, lon, altura_m, es_costera) values"]
    lines.append(",\n".join(
        f"  ('paso', {sql_str('paso-' + p['slug'])}, {sql_str(p['nombre'])}, {sql_str(p['region_id'])}, "
        f"{sql_str(p['region'])}, {p['lat']}, {p['lon']}, {p['altura_m']}, false)"
        for p in pasos
    ) + "\non conflict (slug) do update set nombre = excluded.nombre, lat = excluded.lat, lon = excluded.lon,"
        " altura_m = excluded.altura_m, region = excluded.region, region_id = excluded.region_id;")

    puertos = read_csv("puertos.csv")
    lines += ["", "-- Puertos (catálogo puertos.csv, scripts/build_puertos.py); slug con prefijo, ligados a su comuna.",
              "insert into locations (tipo, slug, nombre, region_id, region, lat, lon, es_costera, comuna_id)",
              "select 'puerto', v.slug, v.nombre, c.region_id, c.region, v.lat, v.lon, true, c.id from (values"]
    lines.append(",\n".join(
        f"  ({sql_str('puerto-' + p['slug'])}, {sql_str(p['nombre'])}, {sql_str(p['comuna'])}, {p['lat']}, {p['lon']})"
        for p in puertos
    ) + ") as v (slug, nombre, comuna, lat, lon)\njoin locations c on c.slug = v.comuna and c.tipo = 'comuna'"
        "\non conflict (slug) do update set nombre = excluded.nombre, lat = excluded.lat, lon = excluded.lon,"
        " region = excluded.region, region_id = excluded.region_id, comuna_id = excluded.comuna_id;")

    lines += ["", "insert into stations (id, red, nombre, lat, lon, location_id) values"]
    lines.append(",\n".join(
        f"  ({sql_str(s['id'])}, {sql_str(s['red'])}, {sql_str(s['nombre'])}, {s['lat']}, {s['lon']}, "
        f"(select id from locations where cut = {sql_str(s['comuna_cut'])}))"
        for s in estaciones if s["coord_valida"] == "True"
    ) + "\non conflict (id) do update set nombre = excluded.nombre, lat = excluded.lat,"
        " lon = excluded.lon, location_id = excluded.location_id;")
    lines.append("")

    SEEDS.mkdir(parents=True, exist_ok=True)
    out = SEEDS / "0001_catalogo.sql"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{out.relative_to(ROOT.parent)}: {len(comunas)} comunas ({len(costeras)} costeras), "
          f"{len(pasos)} pasos, {len(puertos)} puertos, {len(estaciones)} estaciones")


if __name__ == "__main__":
    main()
