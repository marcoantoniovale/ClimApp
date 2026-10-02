from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from climapp_etl import dmc_obs

FIX = Path(__file__).parent / "fixtures" / "dmc"


def test_mapa_quintero():
    est = dmc_obs.parse_mapa((FIX / "mapa_quintero.html").read_text(encoding="utf-8"))
    assert len(est) == 1
    q = est[0]
    assert q["codigo"] == "320056" and q["nombre"] == "Quintero, Climatológica"
    assert (q["lat"], q["lon"]) == (-32.78417, -71.52278)
    assert q["observed_at"] == datetime(2026, 10, 2, 0, 15, tzinfo=timezone.utc)   # 21:15 en Chile
    assert q["temperatura"] == 14.8 and q["humedad"] == 83 and q["viento_vel"] == 0.0


def _visor(rotulos, valores):
    horas = ",".join(f'"{h:02d}:{m:02d}"' for h in range(24) for m in range(60))
    series = "".join(f"{{ name: '{r}', data: [{','.join(str(v) for v in vals)}] }}," for r, vals in zip(rotulos, valores))
    return f"categories: [{horas}], series: [{series}]"


def test_historial_rotulado_con_fecha_utc_despues_de_las_21():
    # Página descargada el 1-oct a las 21:35 (Chile): la DMC rotula "hoy" como 02-10 (fecha UTC).
    hoy = [10.0] * 60 + [11.0] * 60 + [None] * (22 * 60)   # 00:00 y 01:00 con datos
    ayer = [20.0] * (24 * 60)
    page = _visor(["02-10-2026", "01-10-2026"], [[("null" if v is None else v) for v in hoy], ayer])
    obs = dmc_obs.parse_historial(page, date(2026, 10, 1))
    assert obs[datetime(2026, 10, 1, 3, tzinfo=timezone.utc)] == 10.0     # 00:00 del 1-oct en Chile
    assert obs[datetime(2026, 9, 30, 3, tzinfo=timezone.utc)] == 20.0     # ayer = 30-sep
    assert max(obs) < datetime(2026, 10, 1, 5, tzinfo=timezone.utc)


def test_historial_solo_el_primer_grafico():
    page = _visor(["01-10-2026", "30-09-2026", "01-10-2026", "30-09-2026"],
                  [[15.0] * 1440, [14.0] * 1440, [80.0] * 1440, [70.0] * 1440])   # 2.º gráfico: humedad
    obs = dmc_obs.parse_historial(page, date(2026, 10, 1))
    assert set(obs.values()) == {15.0, 14.0}
