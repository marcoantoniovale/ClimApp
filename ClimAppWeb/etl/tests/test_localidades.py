from datetime import datetime, timedelta, timezone

import pytest

from climapp_etl import localidades as L

T0 = datetime(2026, 10, 3, 3, tzinfo=timezone.utc)   # 00:00 en Chile


def test_catalogo_incluye_los_casos_del_usuario():
    cat = {L.clave(l): l for l in L.cargar()}
    assert len(cat) > 3000
    assert cat["quintero/loncura"]["altura"] is not None
    assert {"quintero/valle-alegre", "puchuncavi/ventanas", "puchuncavi/horcon"} <= set(cat)
    assert all("/" not in l["slug"] for l in cat.values())


def test_altura_enfria_a_gradiente_estandar():
    assert L.por_altura(100, 600) == pytest.approx(-3.25)
    assert L.por_altura(None, 600) == 0.0


def test_perfil_por_hora_local_con_mediana():
    dif = {T0 + timedelta(hours=h): (2.0 if (h % 24) == 15 else 0.5) + (9.0 if h == 15 else 0.0) for h in range(72)}
    perfil = L.perfil_horario(dif)
    assert len(perfil) == 24 and perfil[0] == 0.5
    assert perfil[15] == 2.0                      # la mediana ignora el valor aislado de un día
    assert L.perfil_horario({T0: 1.0}) is None    # faltan horas


def test_ajuste_diferencia_de_sesgo_y_altura():
    lugar = {"nombre": "Loncura", "tipo": "suburb", "lat": -32.78617, "lon": -71.50806, "altura": 32.0}
    a = L.ajuste(lugar, {0: 0.8, 2: 0.4}, {0: 0.3, 2: 0.9}, None, 12.0)
    assert a["franjas"] == {"0": 0.5, "1": 0.0, "2": -0.5, "3": 0.0}
    assert a["por_altura"] == pytest.approx(-0.13) and "perfil" not in a
    assert "por_altura" not in L.ajuste(lugar, {}, {}, [0.1] * 24, 12.0)
