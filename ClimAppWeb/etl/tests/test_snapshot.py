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
    assert len(p["horas"]) == 72 - 15            # desde la hora actual hasta el fin de los datos (≤ 6 días)
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
    assert pending_models({k: v for k, v in state.items() if k != "gfs"}, runs, now=h(22)) == ["icon", "gfs"]
    viejo = {m: (h(12), h(5)) for m in runs}
    assert set(pending_models(viejo, runs, now=h(22))) == {"gfs", "ecmwf", "icon"}   # > 9 h sin renovar


def test_dias_limitados_a_hoy_mas_seis():
    p = snapshot.build(LOCATION, make_rows(24 * 8), marine=None, observation=None, fetched_at=NOW, now=NOW,
                       cercanas=[{"slug": "vina-del-mar", "nombre": "Viña del Mar", "km": 8}])
    assert len(p["dias"]) == 7
    assert p["horas"][-1]["hora"].startswith("2026-10-07T23:00")
    assert p["cercanas"][0]["slug"] == "vina-del-mar" and p["version"] == 2


def test_comunas_cercanas_con_empates():
    from climapp_etl.jobs import _nearest_locations

    locs = [{"id": i, "slug": f"c{i}", "nombre": f"C{i}", "lat": -33.0, "lon": -71.0 + d}
            for i, d in enumerate([0, 0.1, -0.1, 0.2])]   # c1 y c2 a la misma distancia de c0
    near = _nearest_locations(locs, n=2)
    assert {c["slug"] for c in near[0]} == {"c1", "c2"}
    assert all(c["slug"] != "c0" for c in near[0])


def test_alertas_de_paso():
    dia = lambda **kw: {"fecha": "2026-10-02", "nieve": 0, "rafaga_max": 20, "temperatura_min": 2,
                        "isoterma_0_min": 4000, "precipitacion": 0, **kw}
    a = snapshot.alertas_paso
    assert a([dia()], 2900) == []
    assert [x["texto"] for x in a([dia(nieve=12)], 2900)] == ["Nieve intensa: 12 cm"]
    ventisca = a([dia(nieve=3, rafaga_max=65)], 2900)
    assert {x["tipo"] for x in ventisca} == {"nieve", "ventisca"} and any(x["nivel"] == "alerta" for x in ventisca)
    assert a([dia(rafaga_max=85)], 2900)[0]["nivel"] == "alerta"
    assert a([dia(rafaga_max=62)], 2900)[0]["nivel"] == "aviso"
    assert a([dia(temperatura_min=-14)], 2900)[0]["tipo"] == "frio"
    assert a([dia(isoterma_0_min=2500, precipitacion=4)], 2900)[0]["tipo"] == "hielo"
    assert a([dia(isoterma_0_min=2500, precipitacion=4)], 2000) == []      # isoterma sobre el paso


def test_solo_los_pasos_llevan_alertas():
    rows = make_rows(48)
    assert snapshot.build(LOCATION, rows, None, None, NOW, now=NOW)["alertas"] == []
    paso = dict(LOCATION, tipo="paso", altura_m=2900, es_costera=False)
    p = snapshot.build(paso, rows, None, None, NOW, now=NOW)
    assert p["ubicacion"]["altura_m"] == 2900 and isinstance(p["alertas"], list)


def test_umbrales_de_viento_mas_altos_en_el_altiplano():
    dia = {"fecha": "2026-10-02", "nieve": 0, "rafaga_max": 70, "temperatura_min": -5,
           "isoterma_0_min": 5000, "precipitacion": 0}
    assert snapshot.alertas_paso([dia], 2900)[0]["nivel"] == "aviso"     # 70 km/h a 2.900 m: aviso
    assert snapshot.alertas_paso([dia], 4680) == []                       # 70 km/h en Chungará: habitual
    assert snapshot.alertas_paso([dict(dia, rafaga_max=100)], 4680)[0]["nivel"] == "alerta"


def test_lluvia_diaria_no_cuenta_modelos_sin_lluvia():
    rows = [("icon", NOW + timedelta(hours=h), {"temperatura": 15.0, "precipitacion": 0.5}) for h in range(24)]
    rows += [("gfs", NOW + timedelta(hours=h), {"indice_uv": 3.0}) for h in range(24)]
    rows += [("ecmwf", NOW + timedelta(hours=h), {"temperatura": 13.0}) for h in range(24)]
    dia = snapshot.daily(rows, NOW.astimezone(snapshot.CHILE).date(), 2)[0]
    assert dia["precipitacion"] == pytest.approx(0.5 * len([r for r in rows[:24]
                                                           if r[1].astimezone(snapshot.CHILE).date() == NOW.astimezone(snapshot.CHILE).date()]))


def test_gfs_solo_dos_veces_al_dia():
    from climapp_etl.jobs import pending_models
    from climapp_etl.open_meteo import Run

    h = lambda hour: datetime(2026, 10, 1, hour, tzinfo=timezone.utc)
    runs = {"gfs": Run(h(18), h(21)), "ecmwf": Run(h(12), h(20)), "icon": Run(h(12), h(20))}
    reciente = {"gfs": (h(12), h(19)), "ecmwf": (h(12), h(20)), "icon": (h(12), h(20))}
    assert pending_models(reciente, runs, now=h(22)) == []                      # GFS nuevo, pero hace 3 h
    luego = reciente | {m: (h(12), h(22) + timedelta(hours=7)) for m in ("icon", "ecmwf")}
    assert pending_models(luego, runs, now=h(22) + timedelta(hours=8)) == ["gfs"]   # pasaron 11 h


def test_lluvia_rotulada_por_la_hora_que_empieza():
    t0 = NOW.replace(minute=0)
    rows = [("icon", t0, {"temperatura": 15.0, "precipitacion": 0.0, "precip_prob": 5, "estado_cielo": 3}),
            ("icon", t0 + timedelta(hours=1), {"temperatura": 14.0, "precipitacion": 0.3, "precip_prob": 60, "estado_cielo": 61})]
    out = snapshot.a_hora_de_inicio(rows)
    assert out[0][2] == {"temperatura": 15.0, "precipitacion": 0.3, "precip_prob": 60, "estado_cielo": 61}
    assert out[1][2]["temperatura"] == 14.0 and out[1][2]["precipitacion"] is None   # sin hora siguiente
    gfs = snapshot.a_hora_de_inicio([("gfs", t0, {"indice_uv": 3.0})])
    assert gfs[0][2] == {"indice_uv": 3.0}                                           # no agrega columnas


def test_lluvia_de_consenso_entre_modelos():
    t0 = NOW.replace(minute=0)
    h = snapshot.consensus_hours([("icon", t0, {"precipitacion": 0.0, "precip_prob": 10, "estado_cielo": 3}),
                                  ("ecmwf", t0, {"precipitacion": 0.4, "precip_prob": 30, "estado_cielo": 61})])[t0]
    assert h["precipitacion"] == pytest.approx(0.2) and h["precip_prob"] == pytest.approx(20)
    assert h["estado_cielo"] == 61                                                   # el más severo
