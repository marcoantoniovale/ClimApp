from datetime import datetime, timedelta, timezone

import pytest

from climapp_etl import correccion as c

T0 = datetime(2026, 10, 1, 3, tzinfo=timezone.utc)   # 00:00 en Chile


def serie(valor_por_hora, horas=48):
    return {T0 + timedelta(hours=i): valor_por_hora(i) for i in range(horas)}


def test_sesgo_por_franja_y_atenuacion():
    obs = serie(lambda i: 15.0)
    icon = serie(lambda i: 18.0 if 12 <= (i % 24) < 18 else 15.0)   # ICON +3 °C solo en la tarde
    s = c.sesgos(icon, obs)
    assert s[2]["sesgo_bruto"] == pytest.approx(3.0) and s[2]["n"] == 12
    assert s[2]["sesgo"] == pytest.approx(3.0 * 12 / 24)            # atenuado a la mitad con 12 horas
    assert s[0]["sesgo"] == pytest.approx(0.0)


def test_diferencias_absurdas_se_descartan_y_el_sesgo_se_limita():
    obs = serie(lambda i: 10.0)
    assert c.sesgos(serie(lambda i: 40.0), obs) == {}                # 30 °C de diferencia: error de dato
    s = c.sesgos(serie(lambda i: 24.0), serie(lambda i: 10.0, horas=2000))
    assert all(v["sesgo"] == c.MAX_SESGO for v in s.values())


def estacion(id, lat, lon, costera=True, sesgo=2.0):
    return {"id": id, "nombre": id, "lat": lat, "lon": lon, "costera": costera, "sesgos": {f: sesgo for f in range(4)}}


def test_correccion_por_distancia_y_zona():
    cerca = c.correccion(-32.78, -71.52, True, [estacion("a", -32.78, -71.52)])
    assert cerca["franjas"][2] == pytest.approx(2.0 / 1.25)          # misma ubicación: 80 % del sesgo
    lejos = c.correccion(-32.78, -71.52, True, [estacion("a", -32.92, -71.52)])   # ~15,6 km
    assert 0 < lejos["franjas"][2] < cerca["franjas"][2]
    assert c.correccion(-32.78, -71.52, True, [estacion("a", -33.50, -71.52)])["franjas"] == {}   # > 25 km
    assert c.correccion(-32.78, -71.52, False, [estacion("a", -32.78, -71.52)])["franjas"] == {}  # otra zona


def test_aplicar_solo_a_icon_temperatura():
    t = T0 + timedelta(hours=15)                                     # 15 h en Chile → franja 2
    rows = [("icon", t, {"temperatura": 20.0, "sensacion_termica": 19.0, "humedad": 60}),
            ("gfs", t, {"indice_uv": 5})]
    out = c.aplicar(rows, {"franjas": {2: 1.5}, "estaciones": []})
    assert out[0][2] == {"temperatura": 18.5, "sensacion_termica": 17.5, "humedad": 60}
    assert out[1][2] == {"indice_uv": 5}
    assert c.aplicar(rows, {"franjas": {}, "estaciones": []}) is rows


def test_validacion_cruzada_no_usa_la_propia_estacion():
    estaciones = [estacion("a", -33.0, -71.6, sesgo=2.0), estacion("b", -33.05, -71.6, sesgo=2.0)]
    obs = {"a": serie(lambda i: 10.0), "b": serie(lambda i: 10.0)}
    icon = {"a": serie(lambda i: 12.0), "b": serie(lambda i: 12.0)}
    r = c.validacion_cruzada(estaciones, icon, obs)
    assert r["error_antes"] == pytest.approx(2.0) and r["error_despues"] < 2.0
    sola = c.validacion_cruzada(estaciones[:1], icon, obs)
    assert sola["n"] == 0                                            # sin vecinas no se evalúa


def test_medicion_cercana_usa_la_estacion_mas_proxima_de_la_misma_zona():
    mediciones = [
        {"estacion": "Costa", "temperatura": 14.0, "lat": -33.44, "lon": -70.66, "costera": True},
        {"estacion": "Lejos", "temperatura": 15.0, "lat": -33.60, "lon": -70.66, "costera": False},
        {"estacion": "Quinta Normal", "temperatura": 16.6, "lat": -33.445, "lon": -70.683, "costera": False},
    ]
    m = c.medicion_cercana(-33.437, -70.665, False, mediciones)
    assert m["estacion"] == "Quinta Normal" and m["temperatura"] == 16.6
    assert 1 < m["km"] < 3 and "lat" not in m and "costera" not in m
    assert c.medicion_cercana(-34.5, -70.66, False, mediciones) is None   # nada a ≤ 15 km
