"""Copia estática del índice de comunas del buscador (la misma lista que publica el precálculo en la
clave Redis `indice`) en web/public/comunas.json. La web la usa si /api/locations falla (p. ej. si Redis
no responde), para que el buscador y "Mi ubicación" sigan funcionando. Regenerar si cambia el catálogo."""

import json
from pathlib import Path

from climapp_etl.db import connect

DESTINO = Path(__file__).resolve().parents[2] / "web" / "public" / "comunas.json"

with connect() as conn:
    indice = [{"slug": s, "nombre": n, "alias": a, "region": r, "costera": c, "lat": round(la, 3), "lon": round(lo, 3)}
              for s, n, a, r, c, la, lo in conn.execute(
                  "select slug, nombre, alias, region, es_costera, lat, lon from locations where tipo = 'comuna' order by id")]
DESTINO.write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{len(indice)} comunas → {DESTINO} ({DESTINO.stat().st_size // 1024} KB)")
