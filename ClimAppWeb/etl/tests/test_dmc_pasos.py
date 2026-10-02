from datetime import date, datetime, timezone
from pathlib import Path

from climapp_etl import dmc_pasos

FIXTURES = Path(__file__).parent / "fixtures" / "dmc_pasos"
HOY = date(2026, 10, 1)


def leer(nombre):
    return (FIXTURES / nombre).read_text(encoding="utf-8", errors="replace")


def test_paso_con_cinco_dias():
    p = dmc_pasos.parse(leer("datos_pasos_fronterizos_maule_v2.js"), "PronoVergara", HOY)
    assert p["emision"].startswith("Jueves 01 de Octubre del 2026")
    assert p["apreciacion"] == "Paso de dorsal en altura."
    assert len(p["dias"]) == 5
    d0 = p["dias"][0]
    assert d0["fecha"] == "2026-10-02" and d0["etiqueta"] == "Viernes 02"
    assert d0["icono"] == "lluviaelectrica.png"
    assert "rachas de 70 km/h" in d0["texto"] and d0["isoterma"] == "3200-1800"


def test_los_libertadores_sin_sufijo_de_region():
    p = dmc_pasos.parse(leer("datos_lib_pronostico.js"), "PronoLosLibertadores", HOY)
    assert p and len(p["dias"]) == 5 and p["dias"][0]["fecha"] == "2026-10-02"


def test_variable_que_es_prefijo_de_otra_no_se_confunde():
    js = 'var PronoRioMayer="a.png|Uno:b.png|Dos";\nvar PronoRio="c.png|Tres";'
    assert dmc_pasos.parse(js, "PronoRio", HOY)["dias"][0]["texto"] == "Tres."


def test_todos_los_pasos_del_catalogo_estan_en_los_archivos():
    archivos = {f.name: f.read_text(encoding="utf-8", errors="replace") for f in FIXTURES.glob("*.js")}
    datos, errores = dmc_pasos.fetch(get_text=lambda url: archivos[url.rsplit("/", 1)[1]],
                                     now=datetime(2026, 10, 1, 20, tzinfo=timezone.utc))
    assert errores == []
    assert len(datos) == len(dmc_pasos.catalogo()) == 37
    assert all(len(p["dias"]) == 5 for p in datos.values())


def test_archivos_sin_datos_personales():
    for f in FIXTURES.glob("*.js"):
        texto = f.read_text(encoding="utf-8", errors="replace").lower()
        assert "usuario" not in texto and "192.168" not in texto, f.name
