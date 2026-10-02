from datetime import datetime, timezone
from pathlib import Path

import pytest

from climapp_etl import geo, sinca

FIXTURES = Path(__file__).parent / "fixtures"


def test_csv_de_airviro_en_hora_utc4_centrada():
    serie = sinca.parse_csv((FIXTURES / "sinca_temp.csv").read_text(encoding="utf-8"))
    # "260930;0100;11,3833" = promedio de 01:00–02:00 en UTC−4 → centro 01:30 UTC−4 = 05:30 UTC
    assert serie[datetime(2026, 9, 30, 5, 30, tzinfo=timezone.utc)] == pytest.approx(11.3833)
    assert all(t.minute == 30 for t in serie)


def test_horas_sin_dato_se_omiten():
    assert sinca.parse_csv("FECHA (YYMMDD);HORA (HHMM);;\n261002;2100;;\n261002;2200;12,5;\n") == {
        datetime(2026, 10, 3, 2, 30, tzinfo=timezone.utc): 12.5}


def test_serie_de_temperatura_vigente():
    pagina = (FIXTURES / "sinca_estacion.txt").read_text(encoding="utf-8")
    assert sinca.serie_temperatura(pagina) == ("./RM/D14/Met/TEMP//horario_003.ic", "261001")
    assert sinca.serie_temperatura("sin series") is None


def test_catalogo_versionado():
    catalogo = sinca.cargar_catalogo()
    assert len(catalogo) >= 50
    assert any(e.nombre == "Quilicura" and e.serie.startswith("./RM/") for e in catalogo)


@pytest.mark.parametrize("lat, lon, comuna", [
    (-33.4378, -70.6504, "santiago"),         # Plaza de Armas
    (-33.445, -70.68278, "estacion-central"), # estación "Quinta Normal" (coordenadas DMC)
    (-33.37833, -70.78778, "pudahuel"),       # estación Pudahuel (por cabecera caía en Quilicura)
    (-33.06528, -71.55639, "valparaiso"),     # Rodelillo (por cabecera caía en Viña del Mar)
    (-32.7861, -71.5080, "quintero"),         # Loncura
    (-33.6, -72.5, None),                     # mar
])
def test_comuna_por_poligono(lat, lon, comuna):
    assert geo.comuna_de(lat, lon) == comuna
