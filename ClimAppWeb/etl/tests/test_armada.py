import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from climapp_etl import armada

FIXTURES = Path(__file__).parent / "fixtures" / "armada"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_hora_de_chile_a_utc():
    # Octubre: horario de verano de Chile (UTC−3).
    assert armada.parse_local("2026-10-01T17:08:07") == datetime(2026, 10, 1, 20, 8, 7, tzinfo=timezone.utc)
    # Julio: horario de invierno (UTC−4).
    assert armada.parse_local("2026-07-01T12:00") == datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc)
    assert armada.parse_local("Fecha inválida") is None
    assert armada.parse_local(None) is None


def test_capitanias():
    raw = load("meteo_observaciones_directemar.json")
    rows = armada.parse_capitanias(raw)
    assert len(rows) == len(raw) - 3            # 3 con "Fecha inválida"
    arica = next(r for r in rows if r["station_id"] == "ARICA")
    assert arica["temperatura"] == 21.6
    assert arica["presion"] == pytest.approx(1015.11)
    assert arica["viento_dir"] == 175
    assert arica["viento_vel"] == pytest.approx(5.2 * 0.514444, abs=1e-3)   # nudos → m/s
    assert arica["raw"]["codigo"] == "ARICA"


def test_ema_usa_hora_local_y_unidad_declarada():
    raw = load("meteo_observaciones.json")
    rows = armada.parse_ema(raw)
    assert len(rows) == len(raw)
    valpo = next(r for r in rows if r["station_id"] == "66666")
    # timeLocal "2026-10-01T11:30" (Chile, UTC−3) → 14:30 UTC; el campo "time" (16:30) se ignora.
    assert valpo["observed_at"] == datetime(2026, 10, 1, 14, 30, tzinfo=timezone.utc)
    assert valpo["viento_vel"] == pytest.approx(4.7265 * 0.514444, abs=1e-3)
    assert valpo["temperatura"] is not None and -10 < valpo["temperatura"] < 40


def test_lecturas_antiguas():
    now = datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc)
    assert armada.is_recent({"observed_at": datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)}, now)
    assert not armada.is_recent({"observed_at": datetime(2025, 9, 29, 19, 0, tzinfo=timezone.utc)}, now)
    assert not armada.is_recent({"observed_at": datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)}, now)
