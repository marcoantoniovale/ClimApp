import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from climapp_etl import avisos
from climapp_etl.avisos import Comuna, ZoneResolver

ROOT = Path(__file__).resolve().parents[1]
PORTADA = ROOT / "tests" / "fixtures" / "armada" / "meteoarmada_portada.html"


@pytest.fixture(scope="module")
def coastal():
    with open(ROOT / "data" / "catalog" / "comunas.csv", encoding="utf-8") as f:
        comunas = {r["cut"]: r for r in csv.DictReader(f)}
    with open(ROOT / "data" / "catalog" / "comunas_costa.csv", encoding="utf-8") as f:
        costa = {r["cut"] for r in csv.DictReader(f) if r["es_costera"] == "True"}
    return [Comuna(int(cut), c["nombre"], c["region_id"], float(c["lat"]), float(c["lon"]))
            for cut, c in comunas.items() if cut in costa]


@pytest.fixture(scope="module")
def resolver(coastal):
    return ZoneResolver(coastal)


@pytest.fixture(scope="module")
def nombres(coastal):
    return {c.id: c.nombre for c in coastal}


def names(resolver, nombres, zona):
    ids, unresolved = resolver.resolve(zona)
    assert unresolved == [], unresolved
    return {nombres[i] for i in ids}


def test_portada_real():
    warnings = avisos.parse_portada(PORTADA.read_text(encoding="utf-8"))
    assert len(warnings) == 12
    w = next(w for w in warnings if w.zona == "PUNTA LAVAPIÉ A CORRAL")
    assert w.tipo == "mal_tiempo"
    assert w.emitido_at == datetime(2026, 10, 1, 20, 15, tzinfo=timezone.utc)   # 17:15 hora de Chile
    assert w.url_fuente == "https://meteoarmada.directemar.cl/meteo/punta-lavapie-a-corral"
    assert w.id == "punta-lavapie-a-corral-202610012015"
    assert {w.tipo for w in warnings} >= {"marejadas", "mal_tiempo", "temporal", "viento", "convectivas"}


def test_todas_las_zonas_de_la_portada_se_resuelven(resolver):
    for w in avisos.parse_portada(PORTADA.read_text(encoding="utf-8")):
        ids, unresolved = resolver.resolve(w.zona)
        assert ids and not unresolved, (w.zona, unresolved)


def test_tramo_entre_accidente_y_comuna(resolver, nombres):
    n = names(resolver, nombres, "PUNTA LAVAPIÉ A CORRAL")
    assert {"Lebu", "Corral", "Valdivia", "Tirúa"} <= n
    assert not n & {"Talcahuano", "Puerto Montt"}


def test_tramo_largo_con_isla(resolver, nombres):
    n = names(resolver, nombres, "GOLFO DE PENAS HASTA ARICA Y ARCH. JUAN FERNÁNDEZ")
    assert {"Arica", "Valparaíso", "Puerto Montt", "Juan Fernández"} <= n
    assert not n & {"Isla de Pascua", "Punta Arenas"}


def test_tramo_entre_regiones(resolver, nombres):
    n = names(resolver, nombres, "MAULE A LOS RIOS")
    assert {"Constitución", "Corral", "Valdivia", "Talcahuano"} <= n
    assert not n & {"Puerto Montt", "Pichilemu"}


def test_islas_y_lugares_unicos(resolver, nombres):
    assert names(resolver, nombres, "RAPA NUI") == {"Isla de Pascua"}
    assert names(resolver, nombres, "ARCHIPIÉLAGO JUAN FERNÁNDEZ") == {"Juan Fernández"}
    assert "Punta Arenas" in names(resolver, nombres, "BAHIA DE PUNTA ARENAS Y PUERTO HARRIS")


def test_zona_desconocida_queda_sin_resolver(resolver):
    ids, unresolved = resolver.resolve("CABO INVENTADO A CORRAL")
    assert not ids and unresolved == ["cabo inventado a corral"]


def test_documento_del_detalle():
    page = ('<img src="/meteo/site/artic/20250514/imag/x/email-1.png">'
            '<img src="/meteo/site/artic/20261001/imag/y/AVISO.jpg">'
            '<a href="/meteo/site/docs/20261001/1/aviso.pdf">Descarga</a>')
    url = "https://meteoarmada.directemar.cl/meteo/zona"
    assert avisos.parse_documento(page, url) == "https://meteoarmada.directemar.cl/meteo/site/docs/20261001/1/aviso.pdf"
    assert avisos.parse_documento(page.split("<a")[0], url).endswith("/20261001/imag/y/AVISO.jpg")
