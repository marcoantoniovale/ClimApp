import json
from datetime import datetime, timezone
from pathlib import Path

from climapp_etl import metno

DATA = json.loads((Path(__file__).parent / "fixtures" / "metno_santiago.json").read_text(encoding="utf-8"))


def test_filas_con_columnas_del_archivo():
    filas = metno.rows(DATA)
    t, v = filas[0]
    assert t == datetime(2026, 10, 2, 21, tzinfo=timezone.utc)
    assert v["temperatura"] == 16.7 and v["viento_vel"] == 3.2 and v["precipitacion"] == 0.5
    assert set(v) == {"temperatura", "humedad", "precipitacion", "viento_vel", "viento_dir", "viento_rafaga", "presion"}
    assert filas[-1][1]["precipitacion"] is None          # tramo de 6 h: sin lluvia horaria
