"""Catálogo de estaciones SINCA con temperatura → data/catalog/estaciones_sinca.csv (semilla y respaldo).

Uso: python scripts/build_sinca.py
En producción el catálogo se renueva solo cada semana (job `sinca_catalogo`, en la base de datos).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from climapp_etl import sinca  # noqa: E402


def main() -> None:
    estaciones, total = sinca.descubrir()
    sinca.guardar_catalogo(estaciones)
    print(f"{len(estaciones)} estaciones con temperatura de {total} → {sinca.CATALOGO}")


if __name__ == "__main__":
    main()
