import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from climapp_etl import open_meteo
from climapp_etl.open_meteo import MinuteBudget, Point, call_weight

FIXTURES = Path(__file__).parent / "fixtures" / "open_meteo"


@pytest.fixture(scope="module")
def response():
    # 2 puntos × 3 modelos × 8 variables × 7 días (spike del 2026-10-01).
    return json.loads((FIXTURES / "forecast_3modelos_2puntos.json").read_text(encoding="utf-8"))


def test_filas_por_modelo_y_hora(response):
    rows = list(open_meteo.rows(response[0], open_meteo.VARIABLES))
    assert len(rows) == 3 * 168
    assert {m for m, _, _ in rows} == {"gfs", "ecmwf", "icon"}
    model, valid_time, values = rows[0]
    assert valid_time == datetime(2026, 10, 1, 0, tzinfo=timezone.utc)
    assert set(values) == set(open_meteo.VARIABLES.values())


def test_variables_ausentes_quedan_nulas(response):
    # El fixture no pide weather_code ni uv_index: deben quedar en None, sin romper.
    _, _, values = next(open_meteo.rows(response[0], open_meteo.VARIABLES))
    assert values["estado_cielo"] is None and values["indice_uv"] is None
    assert values["temperatura"] is not None and values["presion"] > 900


def test_horas_sin_datos_se_omiten():
    data = {"hourly": {"time": ["2026-10-01T00:00", "2026-10-01T01:00"],
                       "temperature_2m_gfs_seamless": [10.0, None]}}
    rows = list(open_meteo.rows(data, {"temperature_2m": "temperatura"}))
    assert [(m, t.hour) for m, t, _ in rows] == [("gfs", 0)]


def test_peso_de_llamadas():
    assert call_weight(1, 8, 1, 7) == 1                        # ≤ 10 variables
    assert call_weight(50, 11, 3, 7) == pytest.approx(165)     # 33 variables → 3,3 por punto
    assert call_weight(10, 7, 3, 3) == pytest.approx(21)


def test_fetch_en_lotes_y_alineado():
    points = [Point(i, -33.0 - i / 100, -71.0) for i in range(120)]
    calls = []

    def fake_get_json(url, params):
        n = len(params["latitude"].split(","))
        calls.append(n)
        return [{"hourly": {"time": []}} for _ in range(n)]

    budget = MinuteBudget(per_minute=10_000)
    result = open_meteo.fetch(points, open_meteo.VARIABLES, 7, budget=budget, get_json=fake_get_json)
    assert calls == [50, 50, 20]
    assert [p.key for p, _ in result] == list(range(120))


def test_fetch_falla_si_la_respuesta_no_calza():
    with pytest.raises(RuntimeError):
        open_meteo.fetch([Point(1, -33, -71), Point(2, -34, -71)], open_meteo.VARIABLES, 7,
                         budget=MinuteBudget(per_minute=10_000), get_json=lambda url, params: [{}])


def test_presupuesto_por_minuto_espera():
    clock = {"t": 0.0}
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        clock["t"] += seconds

    budget = MinuteBudget(per_minute=500, clock=lambda: clock["t"], sleep=sleep)
    budget.acquire(300)
    budget.acquire(300)          # supera 500 en la misma ventana → espera ~60 s
    assert len(sleeps) == 1 and 59 < sleeps[0] < 62


def test_ultima_corrida_por_modelo():
    from datetime import datetime, timezone

    ts = lambda h: datetime(2026, 10, 1, h, tzinfo=timezone.utc).timestamp()
    meta = {
        "ncep_gfs013": {"last_run_initialisation_time": ts(12), "last_run_availability_time": ts(17)},
        "ncep_gfs025": {"last_run_initialisation_time": ts(6), "last_run_availability_time": ts(19)},
        "ecmwf_ifs025": {"last_run_initialisation_time": ts(12), "last_run_availability_time": ts(20)},
        "dwd_icon": {"last_run_initialisation_time": ts(18), "last_run_availability_time": ts(21)},
    }
    runs = open_meteo.latest_runs(get_json=lambda url, **kw: meta[url.split("/data/")[1].split("/")[0]])
    assert runs["gfs"].init.hour == 12          # la más nueva entre GFS 0.13° y 0.25°
    assert runs["icon"].init.hour == 18 and runs["icon"].available.hour == 21


def test_fetch_solo_los_modelos_pedidos():
    params = {}

    def fake(url, p):
        params.update(p)
        return [{"hourly": {"time": []}}]

    open_meteo.fetch([Point(1, -33, -71)], open_meteo.VARIABLES, 7, models=["icon"],
                     budget=MinuteBudget(per_minute=10_000), get_json=fake)
    assert params["models"] == "icon_seamless"
