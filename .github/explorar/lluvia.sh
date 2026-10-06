#!/usr/bin/env bash
# Exploración temporal: qué fuentes publican lluvia medida (se borra al terminar).
set -u
UA="Mozilla/5.0 (ClimApp; https://climapp-chile.vercel.app)"
g() { curl -sS -m 40 -A "$UA" "$@"; }
g "https://climatologia.meteochile.gob.cl/application/index/menuTematicoEmas" > /tmp/mapa.html
echo "=== popup 320056 completo ==="
python3 - <<'PY'
import re
p=open('/tmp/mapa.html',encoding='utf-8',errors='replace').read()
i=p.find('(320056)'); s=p.rfind('bindPopup',0,i); e=p.find('");',i)
print(p[s:e+3])
print('=== contexto Agua Caída Horaria ===')
for m in re.finditer('Agua Ca[ií]da Horaria|Agua Ca[ií]da de la Estaci', p):
    print(m.start(), repr(p[max(0,m.start()-600):m.start()+400])); print('----')
print('=== otras rutas menuTematico ===')
print(sorted(set(re.findall(r'/application/[A-Za-z]+/[A-Za-z]+', p)))[:200])
PY
echo "=== visorEmaPrecipitacion 320056 ==="
g "https://climatologia.meteochile.gob.cl/application/diariob/visorEmaPrecipitacion/320056" > /tmp/pp.html
wc -c /tmp/pp.html
python3 - <<'PY'
import re
p=open('/tmp/pp.html',encoding='utf-8',errors='replace').read()
for kw in ["text: '", "name:", "categories", "<table", "<th", "Agua"]:
    idx=[m.start() for m in re.finditer(re.escape(kw), p)][:6]
    for i in idx: print(kw, '@', i, repr(p[i:i+300]))
print("=== series data (inicio) ===")
for m in list(re.finditer(r"data:\s*\[", p))[:6]:
    print(m.start(), repr(p[m.start()-200:m.start()+500]))
PY
