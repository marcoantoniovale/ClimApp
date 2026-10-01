"""Trabajos de ingesta. Cada uno registra su corrida en ingestion_runs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

from . import armada, open_meteo
from .db import last_success, track_run

log = logging.getLogger("climapp_etl")

FORECAST_DAYS = 7
ARCHIVE_DAYS = 4            # los días cuentan desde las 00:00 UTC; 4 cubren 72 h desde cualquier hora
ARCHIVE_HORIZON = timedelta(hours=72)
ARCHIVE_STEP_HOURS = 3

# Frecuencias objetivo; el modo "auto" las aplica según la última corrida exitosa,
# así tolera retrasos del cron de GitHub Actions.
FORECAST_EVERY = timedelta(hours=6)
ARCHIVE_EVERY = timedelta(hours=12)
MAINTENANCE_EVERY = timedelta(hours=24)
MARGIN = timedelta(minutes=30)

# Retención (pendiente de aprobación; ver db/migrations/0003_retencion.sql y CLAUDE.md).
RETENTION = {
    "forecast_archive": timedelta(days=90),
    "observations": timedelta(days=365),
    "observations_raw": timedelta(days=14),
    "ingestion_runs": timedelta(days=90),
}

CURRENT_COLUMNS = ["location_id", "modelo", "valid_time", "fetched_at", *open_meteo.VARIABLES.values()]
ARCHIVE_COLUMNS = ["station_id", "modelo", "issued_at", "valid_time", *open_meteo.ARCHIVE_VARIABLES.values()]
OBS_COLUMNS = ["temperatura", "punto_rocio", "humedad", "presion", "viento_vel", "viento_dir",
               "viento_rafaga", "precipitacion_1h"]


def forecast(conn: psycopg.Connection) -> None:
    """Pronóstico vigente de todas las comunas → forecast_current (reemplaza el anterior)."""
    with track_run(conn, "open_meteo") as run:
        points = [open_meteo.Point(*r) for r in conn.execute(
            "select id, lat, lon from locations where tipo = 'comuna' order by id")]
        fetched_at = datetime.now(timezone.utc)
        responses = open_meteo.fetch(points, open_meteo.VARIABLES, FORECAST_DAYS)

        records = [
            (point.key, model, valid_time, fetched_at, *values.values())
            for point, data in responses
            for model, valid_time, values in open_meteo.rows(data, open_meteo.VARIABLES)
        ]
        missing = {m for m in open_meteo.MODELS} - {r[1] for r in records}
        if missing:
            run.warn(f"Sin datos de: {', '.join(sorted(missing))}")

        location_ids = [p.key for p, _ in responses]
        with conn.transaction():
            conn.execute("delete from forecast_current where location_id = any(%s)", (location_ids,))
            _copy(conn, "forecast_current", CURRENT_COLUMNS, records)
        run.filas = len(records)
        log.info("forecast_current: %d filas, %d ubicaciones", len(records), len(location_ids))


def archive(conn: psycopg.Connection) -> None:
    """Pronóstico en los puntos de las estaciones (≤ 72 h, cada 3 h) → forecast_archive.
    Estaciones: capitanías y cualquier estación con observaciones en los últimos 7 días."""
    with track_run(conn, "open_meteo_archivo") as run:
        points = [open_meteo.Point(*r) for r in conn.execute("""
            select s.id, s.lat, s.lon from stations s
            where s.activa and (s.red = 'capitania' or exists (
                select 1 from observations o
                where o.station_id = s.id and o.observed_at > now() - interval '7 days'))
            order by s.id""")]
        issued_at = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        responses = open_meteo.fetch(points, open_meteo.ARCHIVE_VARIABLES, ARCHIVE_DAYS)

        records = [
            (point.key, model, issued_at, valid_time, *values.values())
            for point, data in responses
            for model, valid_time, values in open_meteo.rows(data, open_meteo.ARCHIVE_VARIABLES)
            if issued_at <= valid_time <= issued_at + ARCHIVE_HORIZON
            and valid_time.hour % ARCHIVE_STEP_HOURS == 0
        ]
        with conn.transaction():
            conn.execute("delete from forecast_archive where issued_at = %s", (issued_at,))
            _copy(conn, "forecast_archive", ARCHIVE_COLUMNS, records)
        run.filas = len(records)
        log.info("forecast_archive: %d filas, %d estaciones", len(records), len(points))


def observations(conn: psycopg.Connection) -> None:
    """Observaciones actuales de la Armada → observations (sin duplicar lecturas repetidas)."""
    with track_run(conn, "armada_obs") as run:
        now = datetime.now(timezone.utc)
        rows = armada.fetch_observations()
        known = {r[0] for r in conn.execute("select id from stations")}

        unknown = sorted({r["station_id"] for r in rows} - known)
        if unknown:
            run.warn(f"Estaciones no catalogadas: {', '.join(unknown)}")
        stale = [r["station_id"] for r in rows if r["station_id"] in known and not armada.is_recent(r, now)]
        fresh = [r for r in rows if r["station_id"] in known and armada.is_recent(r, now)]

        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany(
                    f"insert into observations (station_id, observed_at, {', '.join(OBS_COLUMNS)}, raw)"
                    f" values (%s, %s, {', '.join(['%s'] * len(OBS_COLUMNS))}, %s)"
                    " on conflict (station_id, observed_at) do nothing",
                    [(r["station_id"], r["observed_at"], *(r.get(c) for c in OBS_COLUMNS), Jsonb(r["raw"]))
                     for r in fresh],
                )
                inserted = cur.rowcount
        run.filas = max(inserted, 0)
        if stale:
            run.detalle.append(f"Lecturas antiguas omitidas ({len(stale)}): {', '.join(sorted(stale))}")
        log.info("observations: %d recibidas, %d vigentes, %d nuevas, %d antiguas",
                 len(rows), len(fresh), run.filas, len(stale))


def maintenance(conn: psycopg.Connection) -> None:
    """Aplica la retención: borra datos antiguos y el JSON original de observaciones viejas."""
    with track_run(conn, "mantencion") as run:
        now = datetime.now(timezone.utc)
        statements = {
            "forecast_archive": ("delete from forecast_archive where issued_at < %s",
                                 now - RETENTION["forecast_archive"]),
            "observations": ("delete from observations where observed_at < %s",
                             now - RETENTION["observations"]),
            "observations_raw": ("update observations set raw = null where raw is not null and observed_at < %s",
                                 now - RETENTION["observations_raw"]),
            "ingestion_runs": ("delete from ingestion_runs where started_at < %s and id <> %s",
                               now - RETENTION["ingestion_runs"]),
        }
        counts = {}
        for name, (sql, cutoff) in statements.items():
            params = (cutoff, run.id) if name == "ingestion_runs" else (cutoff,)
            counts[name] = conn.execute(sql, params).rowcount
        size = conn.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
        run.filas = sum(counts.values())
        run.detalle.append(f"{counts}; tamaño de la base: {size}")
        log.info("mantención: %s; base %s", counts, size)


def auto(conn: psycopg.Connection, with_observations: bool = True) -> None:
    """Lo que corresponda según la última corrida exitosa: observaciones siempre,
    pronóstico cada 6 h, archivo cada 12 h y mantención cada 24 h. Pensado para un cron horario.

    with_observations=False: la API de observaciones de la Armada bloquea las redes de nube
    (GitHub Actions/Azure, AWS); ahí las observaciones se recolectan desde un equipo en Chile."""
    now = datetime.now(timezone.utc)
    failures = []
    jobs = [("open_meteo", forecast, FORECAST_EVERY),
            ("open_meteo_archivo", archive, ARCHIVE_EVERY),
            ("mantencion", maintenance, MAINTENANCE_EVERY)]
    if with_observations:
        jobs.insert(0, ("armada_obs", observations, None))
    for name, job, every in jobs:
        last = last_success(conn, name)
        if every and last and now - last < every - MARGIN:
            log.info("%s: no corresponde (última %s)", name, last.isoformat(timespec="minutes"))
            continue
        try:
            job(conn)
        except Exception as exc:  # un conector caído no detiene a los demás
            log.exception("%s falló", name)
            failures.append(f"{name}: {exc}")
    if failures:
        raise RuntimeError("; ".join(failures))


def _copy(conn: psycopg.Connection, table: str, columns: list[str], records: list[tuple]) -> None:
    with conn.cursor() as cur:
        with cur.copy(f"copy {table} ({', '.join(columns)}) from stdin") as copy:
            for record in records:
                copy.write_row(record)
