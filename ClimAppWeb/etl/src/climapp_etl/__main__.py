"""Línea de comandos del ETL.

Uso:
  python -m climapp_etl auto           # lo que corresponda (cron horario)
  python -m climapp_etl observaciones  # Armada → observations
  python -m climapp_etl pronostico     # Open-Meteo → forecast_current
  python -m climapp_etl archivo        # Open-Meteo en estaciones → forecast_archive
  python -m climapp_etl mantencion     # retención de datos
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import jobs
from .db import connect

COMMANDS = {
    "auto": jobs.auto,
    "observaciones": jobs.observations,
    "pronostico": jobs.forecast,
    "archivo": jobs.archive,
    "mantencion": jobs.maintenance,
}


def main() -> int:
    parser = argparse.ArgumentParser(prog="climapp_etl", description="Ingesta de ClimApp")
    parser.add_argument("comando", choices=COMMANDS)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with connect() as conn:
        try:
            COMMANDS[args.comando](conn)
        except Exception:
            logging.exception("La ingesta terminó con errores")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
