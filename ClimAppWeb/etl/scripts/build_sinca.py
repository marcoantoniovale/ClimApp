"""Catálogo de estaciones SINCA con temperatura → data/catalog/estaciones_sinca.csv.

Uso: python scripts/build_sinca.py
Lee el listado del mapa de SINCA y la página de cada estación para encontrar su serie de temperatura
horaria vigente (actualizada en los últimos 30 días). Se vuelve a correr si SINCA agrega estaciones.
"""

from __future__ import annotations

import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from climapp_etl import http, sinca  # noqa: E402


def main() -> None:
    listado = http.get_json(sinca.LISTADO_URL)
    vigente = (datetime.now() - timedelta(days=30)).strftime("%y%m%d")

    def serie(est: dict):
        try:
            pagina = http.get_text(sinca.ESTACION_URL.format(key=est["key"]))
        except Exception as exc:  # una estación caída no detiene el catálogo
            print(f"  {est['nombre']}: {exc}", file=sys.stderr)
            return est, None
        return est, sinca.serie_temperatura(pagina)

    filas = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for est, encontrada in pool.map(serie, listado):
            if not encontrada or encontrada[1] < vigente:   # sin serie o sin datos recientes
                continue
            macro = encontrada[0]
            filas.append({"key": est["key"], "nombre": est["nombre"].strip(), "comuna": est["comuna"],
                          "lat": f"{float(est['latitud']):.5f}", "lon": f"{float(est['longitud']):.5f}",
                          "serie": macro})
    filas.sort(key=lambda f: (-float(f["lat"]), f["key"]))
    with sinca.CATALOGO.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key", "nombre", "comuna", "lat", "lon", "serie"])
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} estaciones con temperatura de {len(listado)} → {sinca.CATALOGO}")


if __name__ == "__main__":
    main()
