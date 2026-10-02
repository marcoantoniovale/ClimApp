from datetime import datetime, timedelta, timezone

import pytest

from climapp_etl import correccion as c

T0 = datetime(2026, 10, 1, 3, tzinfo=timezone.utc)   # 00:00 en Chile
AHORA = T0 + timedelta(hours=48)


def residuos(valor_por_hora, horas=48, desde=T0):
    return [(desde + timedelta(hours=i), valor_por_hora(i)) for i in range(horas)]


# --- sesgo sistemático -------------------------------------------------------------------------------

def test_sesgo_por_franja_y_atenuacion():
    s = c.sesgos(residuos(lambda i: 3.0 if 12 <= (i % 24) < 18 else 0.0), AHORA)   # ICON +3 °C en la tarde
    assert s[2]["sesgo_bruto"] == pytest.approx(3.0) and s[2]["n"] == 12
    assert 0 < s[2]["sesgo"] < 3.0                                   # atenuado: pocas horas
    assert s[0]["sesgo"] == pytest.approx(0.0)


def test_sesgo_olvida_lo_antiguo_y_se_limita():
    viejo = residuos(lambda i: 4.0, horas=24 * 14, desde=AHORA - timedelta(days=28))
    nuevo = residuos(lambda i: 0.0, horas=24 * 7, desde=AHORA - timedelta(days=7))
    s = c.sesgos(viejo + nuevo, AHORA)
    assert all(v["sesgo"] < 1.5 for v in s.values())                 # pesa más la última semana
    s = c.sesgos(residuos(lambda i: 9.0, horas=24 * 20, desde=AHORA - timedelta(days=20)), AHORA)
    assert all(v["sesgo"] == c.MAX_SESGO for v in s.values())
    assert c.sesgos(residuos(lambda i: 1.0, desde=AHORA - timedelta(days=40)), AHORA) == {}   # fuera de la ventana


# --- interpolación por cuadrantes --------------------------------------------------------------------

def est(id, lat, lon, valor=2.0, costera=False, altura=None):
    return {"id": id, "nombre": id, "lat": lat, "lon": lon, "costera": costera, "altura": altura, "valor": valor}


def test_estacion_propia_domina_y_lejos_vuelve_a_cero():
    propia = c.interpolar(-33.45, -70.66, None, False, [est("a", -33.45, -70.66)])
    assert propia["valor"] == pytest.approx(2.0, abs=0.02)
    a25 = c.interpolar(-33.45, -70.66, None, False, [est("a", -33.675, -70.66)])   # ~25 km
    assert a25["valor"] == pytest.approx(1.0, abs=0.05)
    assert c.interpolar(-33.45, -70.66, None, False, [est("a", -34.0, -70.66)]) is None   # > 50 km
    assert c.interpolar(-33.45, -70.66, None, True, [est("a", -33.45, -70.66)]) is None   # otra zona


def test_un_cuadrante_no_domina():
    # tres estaciones al norte (mismo cuadrante) valen 3; una al sur, a la misma distancia, vale 1
    norte = [est(f"n{i}", -33.40 + i * 0.01, -70.65, valor=3.0) for i in range(3)]
    sur = [est("s", -33.50, -70.65, valor=1.0)]
    r = c.interpolar(-33.45, -70.66, None, False, norte + sur)
    assert len(r["estaciones"]) == 2                                 # solo la más cercana de cada cuadrante
    assert r["valor"] == pytest.approx(2.0, abs=0.25)


def test_altura_resta_peso():
    baja = est("baja", -33.40, -70.66, valor=0.0, altura=500)
    alta = est("alta", -33.50, -70.66, valor=4.0, altura=1500)
    r = c.interpolar(-33.45, -70.66, 500, False, [baja, alta])
    assert r["valor"] < 1.0
    assert r["estaciones"][0]["nombre"] == "baja"


def test_correccion_por_franja_y_exclusion():
    estaciones = [{"id": "a", "nombre": "a", "lat": -33.45, "lon": -70.66, "costera": False, "altura": None,
                   "sesgos": {2: 1.5}}]
    corr = c.correccion(-33.45, -70.66, None, False, estaciones)
    assert set(corr["franjas"]) == {2} and corr["franjas"][2] == pytest.approx(1.5, abs=0.02)
    assert c.correccion(-33.45, -70.66, None, False, estaciones, excluir="a")["franjas"] == {}


def test_aplicar_solo_a_icon_temperatura():
    t = T0 + timedelta(hours=15)                                     # 15 h en Chile → franja 2
    rows = [("icon", t, {"temperatura": 20.0, "sensacion_termica": 19.0, "humedad": 60}),
            ("gfs", t, {"indice_uv": 5})]
    out = c.aplicar(rows, {"franjas": {2: 1.5}, "estaciones": []})
    assert out[0][2] == {"temperatura": 18.5, "sensacion_termica": 17.5, "humedad": 60}
    assert out[1][2] == {"indice_uv": 5}
    assert c.aplicar(rows, {"franjas": {}, "estaciones": []}) is rows


# --- control de calidad ------------------------------------------------------------------------------

def test_control_de_calidad_por_lectura():
    t = T0 + timedelta(hours=10)
    previas = [(t - timedelta(hours=i), 15.0) for i in range(5, 0, -1)]
    assert c.qc_lectura(16.0, 17.0, previas, t) == "ok"
    assert c.qc_lectura(60.0, 17.0, previas, t) == "rango"
    assert c.qc_lectura(1.0, 17.0, previas, t) == "residuo"
    assert c.qc_lectura(25.0, 24.0, previas, t) == "salto"            # +10 °C en una hora
    assert c.qc_lectura(15.0, 16.0, previas, t) == "pegado"           # 6 lecturas idénticas
    assert c.qc_lectura(15.0, 16.0, previas[-3:], t) == "ok"


def test_control_de_calidad_con_vecinas():
    filas = [{"lat": -33.45 + i * 0.05, "lon": -70.66, "costera": False, "residuo": 1.0, "qc": "ok"} for i in range(4)]
    filas.append({"lat": -33.47, "lon": -70.70, "costera": False, "residuo": 8.0, "qc": "ok"})
    c.qc_vecinas(filas)
    assert [f["qc"] for f in filas] == ["ok"] * 4 + ["vecinas"]


# --- persistencia y validación -----------------------------------------------------------------------

def test_tau_se_ajusta_a_la_persistencia():
    serie = {}
    for k in range(40):                                              # anomalías que decaen con τ = 10 h
        inicio = T0 + timedelta(hours=30 * k)
        for h in range(24):
            serie[inicio + timedelta(hours=h)] = (1 if k % 2 else -1) * 2.0 * 0.904837 ** h
    tau, factores = c.ajustar_tau({f"e{i}": serie for i in range(5)})
    assert 8 <= tau <= 12 and factores[1] == pytest.approx(0.9048, abs=0.01)
    assert c.ajustar_tau({})[0] == c.TAU_H


def test_validacion_no_usa_la_propia_estacion():
    estaciones = [{"id": i, "nombre": i, "lat": -33.0 - n * 0.05, "lon": -71.6, "costera": False, "altura": None,
                   "sesgos": {f: 2.0 for f in range(4)}} for n, i in enumerate("ab")]
    serie = {T0 + timedelta(hours=h): 2.0 for h in range(48)}       # ICON 2 °C sobre lo medido, siempre
    r = c.validar(estaciones, {"a": serie, "b": serie}, tau=20)
    assert r["icon"] == pytest.approx(2.0)
    assert r["sin_estacion"]["sesgo"] < 1.0 and r["con_estacion"]["sesgo"] == pytest.approx(0.0)
    sola = c.validar(estaciones[:1], {"a": serie}, tau=20)
    assert sola["sin_estacion"]["sesgo"] == pytest.approx(2.0)      # sin vecinas: queda ICON


def test_medicion_cercana_usa_la_estacion_mas_proxima_de_la_misma_zona():
    mediciones = [
        {"estacion": "Costa", "temperatura": 14.0, "lat": -33.44, "lon": -70.66, "costera": True},
        {"estacion": "Lejos", "temperatura": 15.0, "lat": -33.60, "lon": -70.66, "costera": False},
        {"estacion": "Quinta Normal", "temperatura": 16.6, "lat": -33.445, "lon": -70.683, "costera": False},
    ]
    m = c.medicion_cercana(-33.437, -70.665, False, mediciones)
    assert m["estacion"] == "Quinta Normal" and m["temperatura"] == 16.6
    assert 1 < m["km"] < 3 and "lat" not in m and "costera" not in m
    assert c.medicion_cercana(-34.5, -70.66, False, mediciones) is None
