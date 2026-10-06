#!/usr/bin/env bash
# Exploración temporal: qué fuentes publican lluvia medida (se borra al terminar).
set -u
UA="Mozilla/5.0 (ClimApp; https://climapp-chile.vercel.app)"
g() { curl -sS -m 40 -A "$UA" "$@"; }
echo "=== SINCA: series Met por estación (Quintero/Puchuncaví/Concón) ==="
for k in 567 566 572 565 569 570 571 573 568 562; do
  echo "--- $k"; g "https://sinca.mma.gob.cl/index.php/estacion/index/key/$k" | grep -o 'macropath=[^&"]*/Met/[A-Z0-9]*&amp;macro=horario_[0-9]*&amp;from=[0-9]*&amp;to=[0-9]*' | sort -u
done
echo "=== SINCA: todas las variables Met distintas del listado (muestra 40 estaciones) ==="
g "https://sinca.mma.gob.cl/index.php/json/listadomapa2k19/" > /tmp/listado.json
python3 - <<'PY'
import json; d=json.load(open('/tmp/listado.json')); print(len(d)); print(json.dumps(d[0])[:1500])
PY
echo "=== DMC visor 320056 (Quintero): títulos y nombres de series ==="
g "https://climatologia.meteochile.gob.cl/application/diariob/visorDeDatosEma/320056" > /tmp/visor.html
wc -c /tmp/visor.html
grep -o -i "text: *'[^']*'\|title[^,]\{0,80\}\|agua ca[^<]\{0,80\}\|precip[^<]\{0,80\}\|pp[A-Za-z ]\{0,30\}mm" /tmp/visor.html | sort | uniq -c | head -60
grep -n -i "agua\|precip\|lluvia" /tmp/visor.html | cut -c1-300 | head -30
echo "=== DMC mapa: popup de Quintero ==="
g "https://climatologia.meteochile.gob.cl/application/index/menuTematicoEmas" > /tmp/mapa.html
grep -o "bindPopup(\"<div class='card'>[^;]*320056[^;]*" /tmp/mapa.html | head -c 2500; echo
grep -o -i "agua ca[^<]\{0,60\}\|precip[^<]\{0,60\}" /tmp/mapa.html | sort | uniq -c | head
echo "=== DMC recursos: otros menús de EMA ==="
grep -o 'href="[^"]*application[^"]*"' /tmp/visor.html /tmp/mapa.html | sort -u | head -60
echo "=== condicionactual.js ==="
g "https://archivos.meteochile.gob.cl/portaldmc/appdata/condicionactual.js" | head -c 3000; echo
