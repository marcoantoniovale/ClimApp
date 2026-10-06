#!/usr/bin/env bash
# Exploración temporal: muestra recortada del visor de precipitación DMC (se borra al terminar).
set -u
UA="Mozilla/5.0 (ClimApp; https://climapp-chile.vercel.app)"
for cod in 320056 330020; do
  curl -sS -m 40 -A "$UA" "https://climatologia.meteochile.gob.cl/application/diariob/visorEmaPrecipitacion/$cod" > /tmp/pp_$cod.html
  python3 - "$cod" <<'PY'
import re, sys, gzip, base64
cod=sys.argv[1]
p=open(f'/tmp/pp_{cod}.html',encoding='utf-8',errors='replace').read()
partes=[]
i=p.find('<table', p.find('Horas </th>')-400); j=p.find('</table>', i)+8
partes.append(p[i:j])
k=p.find("Pluviógrafo 48 Horas"); s=p.rfind('<script', 0, k); e=p.find('</script>', k)+9
chart=p[s:e]
def corta(m):
    vals=m.group(2).split(',')
    return m.group(1)+','.join(vals[-240:])+m.group(3)
chart=re.sub(r'(categories:\s*\[)(.*?)(\])', corta, chart, count=1, flags=re.S)
chart=re.sub(r'(data:\s*\[)(.*?)(\])', corta, chart, count=1, flags=re.S)
partes.append(chart)
out='\n'.join(partes)
print(f'### {cod} {len(out)}')
print(base64.b64encode(gzip.compress(out.encode())).decode())
print('### fin')
PY
done
