import pytest

from climapp_etl.units import ms_to_kmh, ms_to_knots, plausible, to_float, to_ms


def test_conversiones_de_viento():
    assert to_ms(10, "kn") == pytest.approx(5.1444, abs=1e-4)
    assert to_ms(36, "km/h") == pytest.approx(10.0)
    assert to_ms(7, "m/s") == 7
    assert to_ms(None, "kn") is None


def test_ida_y_vuelta():
    assert ms_to_kmh(to_ms(50, "km/h")) == pytest.approx(50)
    assert ms_to_knots(to_ms(12, "kn")) == pytest.approx(12)


@pytest.mark.parametrize("raw, expected", [("21.6", 21.6), ("", None), (None, None), ("abc", None), (5, 5.0)])
def test_to_float(raw, expected):
    assert to_float(raw) == expected


def test_valores_fuera_de_rango_se_descartan():
    assert plausible("humedad", 76) == 76
    assert plausible("humedad", 140) is None
    assert plausible("presion", 0) is None
    assert plausible("variable_sin_rango", 1e9) == 1e9
