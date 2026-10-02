"""Trabajos de ingesta. Cada uno registra su corrida en ingestion_runs."""

from __future__ import annotations

import functools
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

from . import armada, avisos, open_meteo, redis, snapshot
from .db import last_success, track_run

log = logging.getLogger("climapp_etl")

FORECAST_DAYS = 7
ARCHIVE_DAYS = 4            # los días cuentan desde las 00:00 UTC; 4 cubren 72 h desde cualquier hora
ARCHIVE_HORIZON = timedelta(hours=72)
ARCHIVE_STEP_HOURS = 3

# Frecuencias objetivo; el modo "auto" las aplica según la última corrida exitosa,
# así tolera retrasos del disparador.
# El pronóstico se descarga por modelo cuando Open-Meteo publica una corrida nueva (se revisa cada
# hora). FORECAST_EVERY es el respaldo si los metadatos no responden; MODEL_MAX_AGE fuerza una
# descarga si un modelo no se renueva por mucho tiempo.
FORECAST_EVERY = timedelta(hours=6)
MODEL_MAX_AGE = timedelta(hours=9)
MARINE_EVERY = timedelta(hours=3)
ARCHIVE_EVERY = timedelta(hours=12)
MAINTENANCE_EVERY = timedelta(hours=24)
MARGIN = timedelta(minutes=30)

# Retención aprobada el 2026-10-01 (~210 MB estables; ver db/migrations/0003_retencion.sql).
RETENTION = {
    "forecast_archive": timedelta(days=90),
    "observations": timedelta(days=365),
    "observations_raw": timedelta(days=14),
    "ingestion_runs": timedelta(days=90),
}

CURRENT_COLUMNS = ["location_id", "modelo", "valid_time", "fetched_at", *open_meteo.COLUMNS]
ARCHIVE_COLUMNS = ["station_id", "modelo", "issued_at", "valid_time", *open_meteo.ARCHIVE_VARIABLES.values()]
MARINE_COLUMNS = ["location_id", "valid_time", "fetched_at", *open_meteo.MARINE_VARIABLES.values()]
OBS_COLUMNS = ["temperatura", "punto_rocio", "humedad", "presion", "viento_vel", "viento_dir",
               "viento_rafaga", "precipitacion_1h"]


def forecast(conn: psycopg.Connection, models: list[str] | None = None,
             runs: dict[str, open_meteo.Run] | None = None) -> None:
    """Pronóstico de todas las comunas → forecast_current. Reemplaza solo los modelos pedidos
    (por defecto, todos) y registra su corrida en model_runs."""
    models = models or list(open_meteo.MODELS)
    with track_run(conn, "open_meteo") as run:
        if runs is None:
            try:
                runs = open_meteo.latest_runs()
            except Exception as exc:  # sin metadatos igual se descarga; solo no se registra la corrida
                run.warn(f"Metadatos de corridas: {exc}")
                runs = {}
        points = [open_meteo.Point(*r) for r in conn.execute(
            "select id, lat, lon from locations where tipo = 'comuna' order by id")]
        fetched_at = datetime.now(timezone.utc)
        budget = open_meteo.MinuteBudget()
        records = []
        location_ids: list = []
        for model in models:  # una petición por modelo, cada uno con sus variables
            variables = open_meteo.MODEL_VARIABLES[model]
            responses = open_meteo.fetch(points, variables, FORECAST_DAYS, past_days=1, models=[model],
                                         budget=budget)
            location_ids = [p.key for p, _ in responses]
            records += [
                (point.key, m, valid_time, fetched_at, *(values.get(c) for c in open_meteo.COLUMNS))
                for point, data in responses
                for m, valid_time, values in open_meteo.rows(data, variables, models=[model])
            ]
        received = {r[1] for r in records}
        if set(models) - received:
            run.warn(f"Sin datos de: {', '.join(sorted(set(models) - received))}")

        with conn.transaction():
            conn.execute("delete from forecast_current where location_id = any(%s) and modelo = any(%s)",
                         (location_ids, sorted(received)))
            _copy(conn, "forecast_current", CURRENT_COLUMNS, records)
            for model in sorted(received):
                if model in runs:
                    conn.execute("""
                        insert into model_runs (modelo, run_init, available_at, fetched_at) values (%s, %s, %s, %s)
                        on conflict (modelo) do update set run_init = excluded.run_init,
                            available_at = excluded.available_at, fetched_at = excluded.fetched_at""",
                        (model, runs[model].init, runs[model].available, fetched_at))
        run.filas = len(records)
        run.detalle.append("modelos: " + ", ".join(
            f"{m} {runs[m].init:%d %H}Z" if m in runs else m for m in sorted(received)))
        log.info("forecast_current: %d filas, modelos %s", len(records), ", ".join(sorted(received)))

        last_marine = conn.execute("select max(fetched_at) from forecast_marine").fetchone()[0]
        if last_marine is None or fetched_at - last_marine >= MARINE_EVERY - MARGIN:
            try:  # el oleaje es complementario: si falla, el pronóstico igual queda
                run.filas += _marine(conn, fetched_at)
            except Exception as exc:
                run.warn(f"Oleaje: {exc}")
                log.exception("oleaje falló")


def due_models(conn: psycopg.Connection, now: datetime) -> tuple[list[str], dict[str, open_meteo.Run]]:
    """Modelos con una corrida más nueva que la descargada (o demasiado antiguos). Si los metadatos
    no responden, vuelve al criterio de tiempo (FORECAST_EVERY) para todos los modelos."""
    state = {r[0]: (r[1], r[2]) for r in conn.execute("select modelo, run_init, fetched_at from model_runs")}
    try:
        runs = open_meteo.latest_runs()
    except Exception:
        log.exception("metadatos de corridas no disponibles; se usa el criterio de tiempo")
        last = last_success(conn, "open_meteo")
        return (list(open_meteo.MODELS) if not last or now - last >= FORECAST_EVERY - MARGIN else []), {}
    return pending_models(state, runs, now), runs


def pending_models(state: dict[str, tuple[datetime, datetime]], runs: dict[str, open_meteo.Run],
                   now: datetime) -> list[str]:
    """state: modelo → (run_init descargada, fetched_at). Pendiente si no hay registro, si hay una
    corrida más nueva o si la descarga es más antigua que MODEL_MAX_AGE."""
    return [m for m in open_meteo.MODELS
            if m not in state or runs[m].init > state[m][0] or now - state[m][1] >= MODEL_MAX_AGE]


def _marine(conn: psycopg.Connection, fetched_at: datetime) -> int:
    points = [open_meteo.Point(*r) for r in conn.execute(
        "select id, lat, lon from locations where es_costera order by id")]
    responses = open_meteo.fetch_marine(points, FORECAST_DAYS)
    records = [(p.key, t, fetched_at, *values.values())
               for p, data in responses for t, values in open_meteo.marine_rows(data)]
    with conn.transaction():
        conn.execute("delete from forecast_marine where location_id = any(%s)", ([p.key for p in points],))
        _copy(conn, "forecast_marine", MARINE_COLUMNS, records)
    log.info("forecast_marine: %d filas, %d comunas costeras", len(records), len(points))
    return len(records)


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
        responses = open_meteo.fetch(points, open_meteo.ARCHIVE_VARIABLES, ARCHIVE_DAYS, models=["icon"])

        records = [
            (point.key, model, issued_at, valid_time, *values.values())
            for point, data in responses
            for model, valid_time, values in open_meteo.rows(data, open_meteo.ARCHIVE_VARIABLES, models=["icon"])
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


def warnings(conn: psycopg.Connection) -> None:
    """Avisos vigentes de la Armada → marine_warnings (+ comunas). Cierra los que ya no aparecen."""
    with track_run(conn, "armada_avisos") as run:
        coastal = [avisos.Comuna(*r) for r in conn.execute(
            "select id, nombre, region_id, lat, lon from locations where es_costera")]
        known = {r[0] for r in conn.execute("select id from marine_warnings")}
        vigentes = avisos.fetch_vigentes(coastal, known)

        with conn.transaction():
            for w in vigentes:
                conn.execute("""
                    insert into marine_warnings (id, tipo, titulo, zona, emitido_at, url_fuente, url_documento)
                    values (%s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do update set vigente_hasta = null, fetched_at = now(),
                        url_documento = coalesce(excluded.url_documento, marine_warnings.url_documento)""",
                    (w.id, w.tipo, w.titulo, w.zona, w.emitido_at, w.url_fuente, w.url_documento))
                conn.execute("delete from marine_warning_locations where warning_id = %s", (w.id,))
                with conn.cursor() as cur:
                    cur.executemany("insert into marine_warning_locations values (%s, %s)",
                                    [(w.id, loc) for loc in w.location_ids])
            closed = conn.execute(
                "update marine_warnings set vigente_hasta = now() where vigente_hasta is null and id <> all(%s)",
                ([w.id for w in vigentes],)).rowcount

        unresolved = sorted({p for w in vigentes for p in w.sin_resolver})
        if unresolved:
            run.warn(f"Zonas sin resolver (ampliar LANDMARKS en avisos.py): {'; '.join(unresolved)}")
        run.filas = len(vigentes)
        published = redis.publish({"avisos": _warnings_payload(conn)})
        log.info("avisos: %d vigentes, %d cerrados, %d zonas sin resolver, redis=%d",
                 len(vigentes), closed, len(unresolved), published)


def _warnings_payload(conn: psycopg.Connection) -> dict:
    rows = conn.execute("""
        select w.id, w.tipo, w.titulo, w.zona, w.emitido_at, w.url_fuente, w.url_documento,
               coalesce(array_agg(l.slug order by l.slug) filter (where l.slug is not null), '{}')
        from marine_warnings w
        left join marine_warning_locations wl on wl.warning_id = w.id
        left join locations l on l.id = wl.location_id
        where w.vigente_hasta is null
        group by w.id order by w.emitido_at desc""").fetchall()
    return {
        "generado": snapshot._iso_local(datetime.now(timezone.utc)),
        "avisos": [{"id": r[0], "tipo": r[1], "titulo": r[2], "zona": r[3],
                    "emitido": snapshot._iso_local(r[4]), "url": r[5], "documento": r[6], "ubicaciones": r[7]}
                   for r in rows],
    }


def snapshots(conn: psycopg.Connection) -> None:
    """JSON por ubicación → location_snapshots y Redis (claves loc:<slug>, indice y meta)."""
    with track_run(conn, "snapshots") as run:
        now = datetime.now(timezone.utc)
        cols = list(open_meteo.COLUMNS)
        locations = [dict(zip(("id", "slug", "nombre", "alias", "region", "tipo", "lat", "lon", "es_costera"), r))
                     for r in conn.execute("""select id, slug, nombre, alias, region, tipo, lat, lon, es_costera
                                              from locations order by id""")]
        rows, fetched = defaultdict(list), {}
        for r in conn.execute(f"""select location_id, modelo, valid_time, fetched_at, {', '.join(cols)}
                                  from forecast_current where valid_time >= now() - interval '30 hours'"""):
            rows[r[0]].append((r[1], r[2], dict(zip(cols, r[4:]))))
            fetched[r[0]] = max(r[3], fetched.get(r[0], r[3]))   # los modelos se descargan en momentos distintos
        marine = defaultdict(list)
        mcols = list(open_meteo.MARINE_VARIABLES.values())
        for r in conn.execute(f"""select location_id, valid_time, {', '.join(mcols)} from forecast_marine
                                  where valid_time >= now() - interval '1 hour'"""):
            marine[r[0]].append((r[1], dict(zip(mcols, r[2:]))))
        observations = {r[0]: {"estacion": r[1], "red": r[2], "hora": snapshot._iso_local(r[3]),
                               "temperatura": r[4], "humedad": r[5], "presion": r[6],
                               "viento": None if r[7] is None else round(r[7] * 3.6),
                               "viento_dir": r[8]}
                        for r in conn.execute("""
            select distinct on (s.location_id) s.location_id, s.nombre, s.red, o.observed_at,
                   o.temperatura, o.humedad, o.presion, o.viento_vel, o.viento_dir
            from observations o join stations s on s.id = o.station_id
            where o.observed_at > now() - interval '3 hours'
            order by s.location_id, o.observed_at desc""")}

        corridas = {r[0]: snapshot._iso_local(r[1]) for r in conn.execute(
            "select modelo, run_init from model_runs where modelo = any(%s)", (list(open_meteo.MODELS),))}
        cercanas = _nearest_locations(locations, n=6)

        payloads = {}
        for loc in locations:
            if not rows.get(loc["id"]):
                run.warn(f"Sin pronóstico: {loc['slug']}")
                continue
            payloads[loc["id"]] = snapshot.build(loc, rows[loc["id"]], marine.get(loc["id"]),
                                                 observations.get(loc["id"]), fetched.get(loc["id"]), now,
                                                 corridas=corridas, cercanas=cercanas[loc["id"]])

        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany("""
                    insert into location_snapshots (location_id, slug, payload, updated_at)
                    values (%s, %s, %s, now())
                    on conflict (location_id) do update set payload = excluded.payload, updated_at = now()""",
                    [(loc_id, p["ubicacion"]["slug"], Jsonb(p)) for loc_id, p in payloads.items()])

        # lat/lon de la cabecera comunal: la web busca la comuna más cercana a la posición del
        # usuario en el propio dispositivo (la ubicación no se envía al servidor).
        index = [{"slug": l["slug"], "nombre": l["nombre"], "alias": l["alias"], "region": l["region"],
                  "costera": l["es_costera"], "lat": round(l["lat"], 3), "lon": round(l["lon"], 3)}
                 for l in locations]
        items = {f"loc:{p['ubicacion']['slug']}": p for p in payloads.values()}
        items["indice"] = index
        items["meta"] = {"generado": snapshot._iso_local(now), "ubicaciones": len(payloads)}
        published = redis.publish(items)
        if not redis.configured():
            run.detalle.append("Redis no configurado: solo location_snapshots")
        run.filas = len(payloads)
        log.info("snapshots: %d ubicaciones, redis=%d claves", len(payloads), published)


def _nearest_locations(locations: list[dict], n: int) -> dict[int, list[dict]]:
    """Para cada ubicación, las n más cercanas (para el módulo "comunas cercanas" de la web)."""
    def km(a, b):
        return math.dist((a["lat"], a["lon"] * math.cos(math.radians(a["lat"]))),
                         (b["lat"], b["lon"] * math.cos(math.radians(a["lat"])))) * 111.2
    result = {}
    for loc in locations:
        near = sorted(((km(loc, o), o) for o in locations if o["id"] != loc["id"]), key=lambda x: x[0])[:n]
        result[loc["id"]] = [{"slug": o["slug"], "nombre": o["nombre"], "km": round(d)} for d, o in near]
    return result


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
    pronóstico por modelo al publicarse una corrida nueva, archivo cada 12 h, avisos cada hora,
    precálculo tras cada pronóstico y mantención cada 24 h. Pensado para un disparo horario.

    with_observations=False: la API de observaciones de la Armada bloquea las redes de nube
    (GitHub Actions/Azure, AWS); ahí las observaciones se recolectan desde un equipo en Chile."""
    now = datetime.now(timezone.utc)
    failures = []
    jobs = [("open_meteo", forecast, "por_corrida"),
            ("open_meteo_archivo", archive, ARCHIVE_EVERY),
            ("armada_avisos", warnings, None),
            ("snapshots", snapshots, "tras_pronostico"),
            ("mantencion", maintenance, MAINTENANCE_EVERY)]
    if with_observations:
        jobs.insert(0, ("armada_obs", observations, None))
    for name, job, every in jobs:
        last = last_success(conn, name)
        if every == "por_corrida":
            models, runs = due_models(conn, now)
            if not models:
                log.info("%s: sin corridas nuevas", name)
                continue
            log.info("%s: corridas nuevas de %s", name, ", ".join(models))
            job = functools.partial(forecast, models=models, runs=runs or None)
        elif every == "tras_pronostico":   # solo si hay un pronóstico más nuevo que el último precálculo
            forecast_at = last_success(conn, "open_meteo")
            if last and forecast_at and last > forecast_at:
                log.info("%s: no corresponde (sin pronóstico nuevo)", name)
                continue
        elif every and last and now - last < every - MARGIN:
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
