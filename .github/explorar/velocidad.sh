#!/usr/bin/env bash
# Medición temporal de velocidad de SINCA y DMC (se borra al terminar). Sin base de datos.
set -eu
cd ClimAppWeb/etl && pip install -q -e . && python - <<'PY'
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from climapp_etl import sinca, dmc_obs
cat = sinca.cargar_catalogo()
now = datetime.now(timezone.utc)
def prueba(nombre, workers, dias, estaciones):
    t0 = time.time(); tiempos = []
    def leer(e):
        t = time.time()
        try:
            n = len(sinca.fetch_temperaturas(e, now - timedelta(days=dias), now)); ok = True
        except Exception as exc:
            n, ok = 0, False
        tiempos.append(time.time() - t); return ok, n
    with ThreadPoolExecutor(max_workers=workers) as pool:
        r = list(pool.map(leer, estaciones))
    tiempos.sort()
    print(f"SINCA {nombre}: {len(estaciones)} est, {time.time()-t0:.0f} s total, por consulta mediana {tiempos[len(tiempos)//2]:.1f} s máx {tiempos[-1]:.1f} s, errores {sum(1 for ok,_ in r if not ok)}, lecturas {sum(n for _,n in r)}")
prueba("6 hilos, 1 día atrás (actual)", 6, 1, cat)
prueba("6 hilos, desde hace 3 h", 6, 0.125, cat)
prueba("12 hilos, desde hace 3 h", 12, 0.125, cat)
est = dmc_obs.fetch_mapa()
for w in (6, 12):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=w) as pool:
        r = list(pool.map(lambda e: dmc_obs.fetch_precipitacion(e["codigo"]), est))
    print(f"DMC lluvia {w} hilos: {len(est)} est, {time.time()-t0:.0f} s, {sum(1 for p in r if p)} con pluviómetro")
PY
