#!/usr/bin/env bash
# Exploración temporal: qué fuentes publican lluvia medida (se borra al terminar).
set -u
UA="Mozilla/5.0 (ClimApp; https://climapp-chile.vercel.app)"
g() { curl -sS -m 40 -A "$UA" "$@"; }
g "https://climatologia.meteochile.gob.cl/application/index/menuTematicoEmas" > /tmp/mapa.html
python3 - <<'PY'
import re, collections
p=open('/tmp/mapa.html',encoding='utf-8',errors='replace').read()
print("=== quinto campo del popup por estación ===")
c=collections.Counter(); rows=[]
for m in re.finditer(r"bindPopup\(\"<div class='card'>(.*?)\"\);", p, re.S):
    pop=m.group(1)
    cod=re.search(r"\((\d{6})\)</small>", pop); nom=re.search(r"<h5>(.*?)<small", pop)
    h6=re.findall(r"<td class='([^']*)'><h6>\s*(.*?)\s*</h6>", pop)
    fecha=re.search(r"text-blanco'>([^<]+)<", pop)
    v=[x for x in h6]
    rows.append((cod.group(1) if cod else '?', nom.group(1) if nom else '?', fecha.group(1) if fecha else '', v))
    if len(v)>3: c[v[3][1]]+=1
print(c.most_common(30))
for r in rows:
    if len(r[3])>3 and r[3][3][1] not in ('.',''):
        print(r)
print("n popups", len(rows))
open('/tmp/lluvia_cod.txt','w').write(' '.join(r[0] for r in rows if len(r[3])>3 and r[3][3][1] not in ('.',''))[:200])
PY
for cod in 320056 330020 $(cut -d' ' -f1-2 /tmp/lluvia_cod.txt); do
  echo "=== visorEmaPrecipitacion $cod: tablas ==="
  g "https://climatologia.meteochile.gob.cl/application/diariob/visorEmaPrecipitacion/$cod" > /tmp/pp.html
  python3 - <<'PY'
import re
p=open('/tmp/pp.html',encoding='utf-8',errors='replace').read()
t=lambda s: re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s)).strip()
for kw in ['Agua Caída Totales Diarios','Horas </th>','Hora del Reporte']:
    i=p.find(kw)
    if i<0: print('no', kw); continue
    j=p.find('</table>', i)
    print('##', kw, '::', t(p[i:j])[:900])
i=p.find("Pluviógrafo 48 Horas")
if i>0:
    cats=re.search(r'categories:\s*\[(.*?)\]', p[i:]).group(1).split(',')
    data=re.search(r"data:\s*\[(.*?)\]", p[i:]).group(1).split(',')
    print('pluviografo', len(cats), len(data), cats[:2], cats[-3:], data[-15:])
    nz=[(c,d) for c,d in zip(cats,data) if d not in ('0.0','','null')]
    print('no cero', len(nz), nz[-10:])
i=p.find("Precipitación Acumulada Diaria (48 horas)")
if i>0:
    data=re.search(r"data:\s*\[(.*?)\]", p[i:]).group(1).split(',')
    print('acumulada', len(data), data[-8:])
PY
done
