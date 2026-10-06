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


def test_precipitacion_quintero():
    # Visor de precipitación descargado el 5-oct a las 23:22 (Chile), con lluvia en la tarde (recortado).
    p = dmc_obs.parse_precipitacion((FIX / "precipitacion_320056.html").read_text(encoding="utf-8"))
    assert p["hasta"] == datetime(2026, 10, 6, 2, 15, tzinfo=timezone.utc)          # 23:15 en Chile
    assert p["mm"] == {1: 0.1, 3: 2.6, 6: 5.2, 12: 5.4, 24: 5.4, 36: 5.4}
    assert p["ultima"] == datetime(2026, 10, 6, 1, 58, tzinfo=timezone.utc)        # 22:58: pasó de 5,3 a 5,4 mm


def test_precipitacion_quinta_normal():
    p = dmc_obs.parse_precipitacion((FIX / "precipitacion_330020.html").read_text(encoding="utf-8"))
    assert p["mm"][1] == 0.2 and p["mm"][3] == 3.0 and p["mm"][24] == 7.9


def test_precipitacion_sin_pluviometro_y_sin_lluvia():
    assert dmc_obs.parse_precipitacion("<html>sin tabla</html>") is None
    fila = ('<tr><td><h4> {h}</h4></td><td> 05-10-2026 22:15 </td><td> 05-10-2026 23:15 </td>'
            '<td><h4>s/p</h4></td></tr>')
    page = "<th> Horas </th>" + "".join(fila.format(h=h) for h in (1, 3)) + "</table>"
    p = dmc_obs.parse_precipitacion(page.replace("<th> Horas </th>", '<th scope="col"> Horas </th>'))
    assert p["mm"] == {1: 0.0, 3: 0.0} and p["ultima"] is None
