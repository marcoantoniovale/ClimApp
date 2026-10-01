from datetime import datetime, timedelta, timezone

import pytest

from climapp_etl import snapshot

NOW = datetime(2026, 10, 1, 15, 20, tzinfo=timezone.utc)   # 12:20 en Chile
LOCATION = {"slug": "valparaiso", "nombre": "Valparaíso", "region": "Valparaiso", "tipo": "comuna",
            "lat": -33.05, "lon": -71.62, "es_costera": True}


def values(temp, code=1, wind=5.0, wind_dir=0.0, rain=0.0, pp=10.0, uv=None):
    return {"temperatura": temp, "sensacion_termica": temp - 1, "estado_cielo": code, "indice_uv": uv,
            "humedad": 70.0, "precip_prob": pp, "precipitacion": rain, "viento_vel": wind,
            "viento_dir": wind_dir, "viento_rafaga": wind * 2, "presion": 1015.0}


def make_rows(hours=72):
    start = NOW.replace(hour=0, minute=0)
    rows = []
    for i in range(hours):
        t = start + timedelta(hours=i)
        rows.append(("gfs", t, values(10 + i % 24 / 2, code=1, wind=4.0, wind_dir=350, uv=5.0)))
        rows.append(("ecmwf", t, values(12 + i % 24 / 2, code=1, wind=6.0, wind_dir=10)))
        rows.append(("icon", t, values(14 + i % 24 / 2, code=61, wind=5.0, wind_dir=0, rain=0.5)))
    return rows


def test_hora_de_consenso():
    hours = snapshot.consensus_hours(make_rows(1))
    h = next(iter(hours.values()))
    assert h["temperatura"] == pytest.approx(12)
    assert (h["temperatura_min"], h["temperatura_max"]) == (10, 14)
    assert h["estado_cielo"] == 1                      # dos modelos dicen 1, uno 61
    assert h["viento_dir"] == pytest.approx(0, abs=0.5) or h["viento_dir"] == pytest.approx(360, abs=0.5)
    assert h["indice_uv"] == 5.0                       # solo GFS lo trae


def test_payload():
    p = snapshot.build(LOCATION, make_rows(), marine=None, observation=None, fetched_at=NOW, now=NOW)
    assert p["ubicacion"]["slug"] == "valparaiso" and p["provisional"] is True
    assert p["modelos"] == ["ecmwf", "gfs", "icon"]
    assert len(p["horas"]) == 48
    assert p["horas"][0]["hora"] == "2026-10-01T12:00-03:00"      # hora actual, en hora de Chile
    assert p["horas"][0]["viento"] == round(5.0 * 3.6)            # m/s → km/h
    assert p["unidades"]["viento"] == "km/h"
    assert p["marino"] is None


def test_dias_en_hora_de_chile_con_rango_entre_modelos():
    p = snapshot.build(LOCATION, make_rows(), marine=None, observation=None, fetched_at=NOW, now=NOW)
    dias = p["dias"]
    assert dias[0]["fecha"] == "2026-10-01"
    d1 = dias[1]                                   # primer día completo
    assert d1["rango_max"][0] < d1["temperatura_max"] < d1["rango_max"][1]
    assert d1["estado_cielo"] == 1
    assert d1["precipitacion"] == pytest.approx(0.5 * 24 / 3, abs=0.1)   # solo ICON llueve: promedio de 3
    assert d1["viento_max"] == 18


def test_dia_incompleto_no_inventa_maximas():
    p = snapshot.build(LOCATION, make_rows(30), marine=None, observation=None, fetched_at=NOW, now=NOW)
    ultimo = p["dias"][-1]
    assert ultimo["temperatura_max"] is None and ultimo["rango_max"] is None


def test_oleaje_solo_en_costeras():
    marine = [(NOW.replace(minute=0) + timedelta(hours=i),
               {"oleaje_altura": 1.5, "oleaje_periodo": 11.0, "oleaje_dir": 225.0, "marejada_altura": 1.2})
              for i in range(48)]
    p = snapshot.build(LOCATION, make_rows(), marine, None, NOW, now=NOW)
    assert p["marino"]["horas"][0] == {"hora": "2026-10-01T12:00-03:00", "altura": 1.5, "periodo": 11.0,
                                       "direccion": 225.0, "marejada": 1.2}
    assert p["marino"]["dias"][0]["altura_max"] == 1.5
    interior = dict(LOCATION, es_costera=False)
    assert snapshot.build(interior, make_rows(), marine, None, NOW, now=NOW)["marino"] is None


def test_modelos_pendientes():
    from climapp_etl.jobs import pending_models
    from climapp_etl.open_meteo import Run

    h = lambda hour: datetime(2026, 10, 1, hour, tzinfo=timezone.utc)
    runs = {"gfs": Run(h(12), h(17)), "ecmwf": Run(h(12), h(20)), "icon": Run(h(18), h(21))}
    state = {"gfs": (h(12), h(20)), "ecmwf": (h(12), h(20)), "icon": (h(12), h(20))}
    assert pending_models(state, runs, now=h(22)) == ["icon"]                 # solo ICON trae corrida nueva
    assert pending_models({k: v for k, v in state.items() if k != "gfs"}, runs, now=h(22)) == ["gfs", "icon"]
    viejo = {m: (h(12), h(5)) for m in runs}
    assert set(pending_models(viejo, runs, now=h(22))) == {"gfs", "ecmwf", "icon"}   # > 9 h sin renovar
