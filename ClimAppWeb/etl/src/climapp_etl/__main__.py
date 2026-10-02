"""Línea de comandos del ETL.

Uso:
  python -m climapp_etl auto [--sin-observaciones]  # lo que corresponda (cron horario)
  python -m climapp_etl observaciones               # Armada → observations
  python -m climapp_etl pronostico                  # Open-Meteo → forecast_current
  python -m climapp_etl archivo                     # Open-Meteo en estaciones → forecast_archive
  python -m climapp_etl avisos                      # avisos Armada → marine_warnings + Redis
  python -m climapp_etl precalculo                  # JSON por ubicación → location_snapshots + Redis
  python -m climapp_etl pasos                       # pronóstico DMC de pasos fronterizos → Redis
  python -m climapp_etl mantencion                  # retención de datos

Opción --log ARCHIVO: escribe el registro en un archivo (para pythonw.exe, que no tiene consola).
"""

from __future__ import annotations

import argparse
import functools
import logging
import sys

from . import jobs
from .db import connect

COMMANDS = {
    "auto": jobs.auto,
    "observaciones": jobs.observations,
    "pronostico": jobs.forecast,
    "archivo": jobs.archive,
    "avisos": jobs.warnings,
    "precalculo": jobs.snapshots,
    "pasos": jobs.dmc_passes,
    "mantencion": jobs.maintenance,
}


def main() -> int:
    parser = argparse.ArgumentParser(prog="climapp_etl", description="Ingesta de ClimApp")
    parser.add_argument("comando", choices=COMMANDS)
    parser.add_argument("--sin-observaciones", action="store_true",
                        help="en 'auto', omitir las observaciones de la Armada")
    parser.add_argument("--log", metavar="ARCHIVO", help="escribir el registro en este archivo")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        **({"filename": args.log, "encoding": "utf-8"} if args.log else {}))

    command = COMMANDS[args.comando]
    if args.comando == "auto":
        command = functools.partial(jobs.auto, with_observations=not args.sin_observaciones)

    try:
        with connect() as conn:
            command(conn)
    except Exception:
        logging.exception("La ingesta terminó con errores")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
