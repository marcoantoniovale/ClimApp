#!/usr/bin/env bash
# Medición temporal (plazo 8 s) de velocidad de SINCA y DMC con el código de la rama (se borra al terminar).
set -eu
cd ClimAppWeb/etl && pip install -q -e . && python - <<'PY'
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from climapp_etl import sinca, dmc_obs
cat = sinca.cargar_catalogo()
for intento in (1, 2):
    now = datetime.now(timezone.utc); t0 = time.time(); tiempos = []
    def leer(e):
        t = time.time()
        try: n, ok = len(sinca.fetch_temperaturas(e, now - timedelta(days=1), now)), True
        except Exception: n, ok = 0, False
        tiempos.append(time.time() - t); return ok, n
    with ThreadPoolExecutor(max_workers=6) as pool:
        r = list(pool.map(leer, cat))
    tiempos.sort()
    print(f"SINCA ({intento}): {time.time()-t0:.0f} s, mediana {tiempos[len(tiempos)//2]:.1f} s, máx {tiempos[-1]:.1f} s, errores {sum(1 for ok,_ in r if not ok)}, lecturas {sum(n for _,n in r)}")
est = dmc_obs.fetch_mapa(); t0 = time.time()
with ThreadPoolExecutor(max_workers=12) as pool:
    r = list(pool.map(lambda e: dmc_obs.fetch_precipitacion(e["codigo"]), est))
print(f"DMC lluvia: {time.time()-t0:.0f} s, {sum(1 for p in r if p)} con pluviómetro")
PY
