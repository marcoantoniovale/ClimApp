#!/usr/bin/env bash
# Prueba temporal del lector de lluvia DMC en todas las estaciones, sin base de datos (se borra al terminar).
set -eu
cd ClimAppWeb/etl && pip install -q -e . && python - <<'PY'
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from climapp_etl import dmc_obs
t0 = time.time()
est = dmc_obs.fetch_mapa()
def leer(e):
    try:
        return e, dmc_obs.fetch_precipitacion(e["codigo"]), None
    except Exception as exc:
        return e, None, exc
with ThreadPoolExecutor(max_workers=6) as pool:
    res = list(pool.map(leer, est))
now = datetime.now(timezone.utc)
ok = [(e, p) for e, p, x in res if p]
print(f"{len(est)} estaciones, {len(ok)} con pluviómetro, {sum(1 for *_, x in res if x)} errores, {time.time()-t0:.0f} s")
print("edad (min) de 'hasta':", sorted(round((now - p['hasta']).total_seconds() / 60) for _, p in ok)[::10])
for e, p in ok:
    if p["mm"].get(3):
        print(e["codigo"], e["nombre"], p["hasta"].isoformat(), p["mm"], p["ultima"])
for e, p, x in res:
    if x: print("ERROR", e["codigo"], x)
PY
