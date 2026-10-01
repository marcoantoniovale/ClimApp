"""Pruebas de integridad del catálogo geográfico generado (data/catalog)."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_seed import slugify  # noqa: E402


def read(name: str) -> list[dict]:
    with open(ROOT / "data" / "catalog" / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def comunas():
    return read("comunas.csv")


@pytest.fixture(scope="module")
def estaciones():
    return read("estaciones_armada.csv")


def test_estan_las_346_comunas_con_cut_unico(comunas):
    assert len(comunas) == 346
    assert len({c["cut"] for c in comunas}) == 346


def test_16_regiones(comunas):
    assert len({c["region_id"] for c in comunas}) == 16


def test_todas_las_comunas_tienen_coordenadas_en_chile(comunas):
    for c in comunas:
        assert c["fuente_coord"] != "SIN_COORDENADAS", c
        assert -90 <= float(c["lat"]) <= -17, c
        assert -110 <= float(c["lon"]) <= -53, c


def test_slugs_unicos(comunas):
    slugs = [slugify(c["nombre"]) for c in comunas]
    assert len(set(slugs)) == len(slugs)


@pytest.mark.parametrize("cut, lat, lon", [
    ("13101", -33.45, -70.66),   # Santiago
    ("05101", -33.05, -71.62),   # Valparaíso
    ("12101", -53.16, -70.91),   # Punta Arenas
    ("15101", -18.48, -70.31),   # Arica
])
def test_coordenadas_de_referencia(comunas, cut, lat, lon):
    c = next(c for c in comunas if c["cut"] == cut)
    assert abs(float(c["lat"]) - lat) < 0.1 and abs(float(c["lon"]) - lon) < 0.1, c


def test_estaciones_validas_tienen_comuna(estaciones):
    validas = [s for s in estaciones if s["coord_valida"] == "True"]
    assert len(validas) >= 90
    assert all(s["comuna_cut"] for s in validas)
