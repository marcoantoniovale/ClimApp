"""Trabajos de ingesta. Cada uno registra su corrida en ingestion_runs."""

from __future__ import annotations

import functools
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

from . import armada, avisos, correccion, dmc_obs, dmc_pasos, open_meteo, redis, snapshot
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
PASOS_DMC_EVERY = timedelta(hours=3)   # la DMC emite ~2 veces al día
CORRECTION_EVERY = timedelta(hours=3)
CORRECTION_DAYS = 14                   # ventana de mediciones para el sesgo
DMC_MAX_AGE = timedelta(hours=3)       # lecturas más antiguas del mapa DMC no se guardan
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
        comunas = [open_meteo.Point(*r) for r in conn.execute(
            "select id, lat, lon from locations where tipo = 'comuna' order by id")]
        # Pasos fronterizos: con su altura, para que la temperatura corresponda a la cota del paso.
        pasos = [open_meteo.Point(r[0], r[1], r[2], r[3]) for r in conn.execute(
            "select id, lat, lon, altura_m from locations where tipo = 'paso' order by id")]
        fetched_at = datetime.now(timezone.utc)
        budget = open_meteo.MinuteBudget()
        records = []
        location_ids = [p.key for p in comunas + pasos]
        for model in models:  # una petición por modelo (y grupo), cada modelo con sus variables
            variables = open_meteo.MODEL_VARIABLES[model]
            for group in (comunas, pasos):
                if not group:
                    continue
                responses = open_meteo.fetch(group, variables, FORECAST_DAYS, past_days=1, models=[model],
                                             budget=budget)
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
        locations = [dict(zip(("id", "slug", "nombre", "alias", "region", "tipo", "lat", "lon", "es_costera",
                               "altura_m"), r))
                     for r in conn.execute("""select id, slug, nombre, alias, region, tipo, lat, lon, es_costera,
                                                     altura_m from locations order by id""")]
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

        estaciones_sesgo: dict[str, dict] = {}
        for sid, nombre, lat, lon, costera, f, sesgo in conn.execute("""
                select s.id, s.nombre, s.lat, s.lon, coalesce(l.es_costera, false), b.franja, b.sesgo
                from station_bias b join stations s on s.id = b.station_id
                left join locations l on l.id = s.location_id"""):
            e = estaciones_sesgo.setdefault(sid, {"id": sid, "nombre": nombre, "lat": lat, "lon": lon,
                                                  "costera": costera, "sesgos": {}})
            e["sesgos"][f] = sesgo
        estaciones_sesgo_lista = list(estaciones_sesgo.values())
        corregidas = 0

        corridas = {r[0]: snapshot._iso_local(r[1]) for r in conn.execute(
            "select modelo, run_init from model_runs where modelo = any(%s)", (list(open_meteo.MODELS),))}
        cercanas = _nearest_locations(locations, n=6)

        payloads = {}
        for loc in locations:
            if not rows.get(loc["id"]):
                run.warn(f"Sin pronóstico: {loc['slug']}")
                continue
            corr = ({"franjas": {}, "estaciones": []} if loc["tipo"] != "comuna" else
                    correccion.correccion(loc["lat"], loc["lon"], loc["es_costera"], estaciones_sesgo_lista))
            corregidas += bool(corr["franjas"])
            payloads[loc["id"]] = snapshot.build(loc, correccion.aplicar(rows[loc["id"]], corr), marine.get(loc["id"]),
                                                 observations.get(loc["id"]), fetched.get(loc["id"]), now,
                                                 corridas=corridas, cercanas=cercanas[loc["id"]], correccion=corr)

        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany("""
                    insert into location_snapshots (location_id, slug, payload, updated_at)
                    values (%s, %s, %s, now())
                    on conflict (location_id) do update set payload = excluded.payload, updated_at = now()""",
                    [(loc_id, p["ubicacion"]["slug"], Jsonb(p)) for loc_id, p in payloads.items()])

        # lat/lon de la cabecera comunal: la web busca la comuna más cercana a la posición del
        # usuario en el propio dispositivo (la ubicación no se envía al servidor).
        # Solo comunas: los pasos no deben aparecer en el buscador ni al ubicar al usuario.
        index = [{"slug": l["slug"], "nombre": l["nombre"], "alias": l["alias"], "region": l["region"],
                  "costera": l["es_costera"], "lat": round(l["lat"], 3), "lon": round(l["lon"], 3)}
                 for l in locations if l["tipo"] == "comuna"]
        items = {f"loc:{p['ubicacion']['slug']}": p for p in payloads.values()}
        items["indice"] = index
        items["pasos"] = _pasos_payload(locations, payloads, now)
        items["meta"] = {"generado": snapshot._iso_local(now), "ubicaciones": len(payloads)}
        published = redis.publish(items)
        if not redis.configured():
            run.detalle.append("Redis no configurado: solo location_snapshots")
        run.filas = len(payloads)
        run.detalle.append(f"{corregidas} comunas con corrección de temperatura")
        log.info("snapshots: %d ubicaciones (%d corregidas), redis=%d claves", len(payloads), corregidas, published)


def _pasos_payload(locations: list[dict], payloads: dict[int, dict], now: datetime) -> dict:
    """Resumen de los pasos fronterizos para la página /pasos: hoy y alertas de los próximos días."""
    pasos = []
    for loc in locations:
        p = payloads.get(loc["id"])
        if loc["tipo"] != "paso" or not p:
            continue
        hoy = p["dias"][0] if p["dias"] else {}
        pasos.append({
            "slug": loc["slug"], "nombre": loc["nombre"], "region": loc["region"], "altura_m": loc["altura_m"],
            "lat": loc["lat"], "lon": loc["lon"],
            "hoy": {k: hoy.get(k) for k in ("estado_cielo", "temperatura_max", "temperatura_min", "nieve", "rafaga_max")},
            "alertas": p["alertas"],
        })
    pasos.sort(key=lambda x: -x["lat"])   # de norte a sur
    return {"generado": snapshot._iso_local(now), "pasos": pasos}


def _nearest_locations(locations: list[dict], n: int) -> dict[int, list[dict]]:
    """Para cada ubicación, las n comunas más cercanas (para el módulo "comunas cercanas" de la web)."""
    def km(a, b):
        return math.dist((a["lat"], a["lon"] * math.cos(math.radians(a["lat"]))),
                         (b["lat"], b["lon"] * math.cos(math.radians(a["lat"])))) * 111.2
    result = {}
    for loc in locations:
        near = sorted(((km(loc, o), o) for o in locations if o["id"] != loc["id"] and o.get("tipo", "comuna") == "comuna"),
                      key=lambda x: x[0])[:n]
        result[loc["id"]] = [{"slug": o["slug"], "nombre": o["nombre"], "km": round(d)} for d, o in near]
    return result


def dmc_passes(conn: psycopg.Connection) -> None:
    """Pronóstico oficial de pasos fronterizos de la DMC → Redis (clave pasos_dmc)."""
    with track_run(conn, "pasos_dmc") as run:
        datos, errores = dmc_pasos.fetch()
        for e in errores:
            run.warn(e)
        if not datos:
            raise RuntimeError("La DMC no entregó pronósticos de pasos: " + "; ".join(errores[:3]))
        payload = {"generado": snapshot._iso_local(datetime.now(timezone.utc)),
                   "pasos": {f"paso-{slug}": p for slug, p in datos.items()}}
        published = redis.publish({"pasos_dmc": payload})
        run.filas = len(datos)
        log.info("pasos DMC: %d pasos, %d errores, redis=%d", len(datos), len(errores), published)


def _upsert_dmc_stations(conn: psycopg.Connection, estaciones: list[dict]) -> None:
    """Estaciones DMC en `stations` (id dmc-<código>), asociadas a la comuna más cercana."""
    with conn.cursor() as cur:
        cur.executemany("""
            insert into stations (id, red, nombre, lat, lon, location_id)
            values (%(id)s, 'dmc', %(nombre)s, %(lat)s, %(lon)s,
                    (select id from locations where tipo = 'comuna'
                     order by (lat - %(lat)s) ^ 2 + ((lon - %(lon)s) * cos(radians(%(lat)s))) ^ 2 limit 1))
            on conflict (id) do update set nombre = excluded.nombre, lat = excluded.lat, lon = excluded.lon,
                location_id = excluded.location_id""",
            [{"id": f"dmc-{e['codigo']}", "nombre": e["nombre"], "lat": e["lat"], "lon": e["lon"]} for e in estaciones])


def dmc_observations(conn: psycopg.Connection) -> None:
    """Última medición de todas las estaciones automáticas DMC (una página) → stations + observations."""
    with track_run(conn, "dmc_obs") as run:
        now = datetime.now(timezone.utc)
        estaciones = dmc_obs.fetch_mapa()
        if not estaciones:
            raise RuntimeError("El mapa de la DMC no trajo estaciones (¿cambió el formato?)")
        frescas = [e for e in estaciones
                   if e["observed_at"] and now - DMC_MAX_AGE <= e["observed_at"] <= now + timedelta(hours=1)
                   and e["temperatura"] is not None]
        with conn.transaction():
            _upsert_dmc_stations(conn, estaciones)
            with conn.cursor() as cur:
                cur.executemany("""
                    insert into observations (station_id, observed_at, temperatura, humedad, presion, viento_vel, viento_dir)
                    values (%s, %s, %s, %s, %s, %s, %s) on conflict (station_id, observed_at) do nothing""",
                    [(f"dmc-{e['codigo']}", e["observed_at"], e["temperatura"], e["humedad"], e["presion"],
                      e["viento_vel"], e["viento_dir"]) for e in frescas])
                run.filas = max(cur.rowcount, 0)
        run.detalle.append(f"{len(estaciones)} estaciones, {len(frescas)} con lectura reciente")
        log.info("DMC: %d estaciones, %d lecturas recientes, %d nuevas", len(estaciones), len(frescas), run.filas)


def dmc_history(conn: psycopg.Connection) -> None:
    """Carga inicial: temperatura horaria de hoy y ayer de cada estación DMC (visor por estación)."""
    with track_run(conn, "dmc_historial") as run:
        estaciones = dmc_obs.fetch_mapa()
        _upsert_dmc_stations(conn, estaciones)
        total = 0
        for e in estaciones:
            try:
                serie = dmc_obs.fetch_historial(e["codigo"])
            except Exception as exc:
                run.warn(f"{e['codigo']}: {exc}")
                continue
            with conn.cursor() as cur:
                cur.executemany("""insert into observations (station_id, observed_at, temperatura) values (%s, %s, %s)
                                   on conflict (station_id, observed_at) do nothing""",
                                [(f"dmc-{e['codigo']}", t, v) for t, v in serie.items()])
                total += max(cur.rowcount, 0)
        run.filas = total
        log.info("DMC historial: %d estaciones, %d horas nuevas", len(estaciones), total)


def corrections(conn: psycopg.Connection) -> None:
    """Algoritmo ClimApp: sesgo de ICON por estación DMC y franja → station_bias (+ validación cruzada)."""
    with track_run(conn, "correccion") as run:
        estaciones = conn.execute("""
            select s.id, s.nombre, s.lat, s.lon, coalesce(l.es_costera, false)
            from stations s left join locations l on l.id = s.location_id
            where s.red = 'dmc' and exists (select 1 from observations o where o.station_id = s.id
                                            and o.observed_at > now() - interval '2 days')
            order by s.id""").fetchall()
        obs: dict[str, dict] = defaultdict(dict)
        for sid, t, temp in conn.execute("""
                select station_id, date_trunc('hour', observed_at), avg(temperatura) from observations
                where station_id like 'dmc-%%' and temperatura is not null
                  and observed_at > now() - make_interval(days => %s)
                  and extract(minute from observed_at) <= 20
                group by 1, 2""", (CORRECTION_DAYS,)):
            obs[sid][t] = temp
        # ICON en el punto de cada estación, días pasados (pronóstico más reciente para cada hora).
        variables = {"temperature_2m": "temperatura"}
        points = [open_meteo.Point(r[0], r[2], r[3]) for r in estaciones]
        responses = open_meteo.fetch(points, variables, 1, past_days=CORRECTION_DAYS, models=["icon"])
        icon = {p.key: {t: v["temperatura"] for _, t, v in open_meteo.rows(data, variables, models=["icon"])}
                for p, data in responses}
        filas, info = [], []
        for sid, nombre, lat, lon, costera in estaciones:
            s = correccion.sesgos(icon.get(sid, {}), obs.get(sid, {}))
            if s:
                info.append({"id": sid, "nombre": nombre, "lat": lat, "lon": lon, "costera": costera,
                             "sesgos": {f: v["sesgo"] for f, v in s.items()}})
                filas += [(sid, f, v["sesgo"], v["sesgo_bruto"], v["n"], v["error_antes"]) for f, v in s.items()]
        with conn.transaction():
            conn.execute("delete from station_bias")
            with conn.cursor() as cur:
                cur.executemany("insert into station_bias (station_id, franja, sesgo, sesgo_bruto, n, error_antes)"
                                " values (%s, %s, %s, %s, %s, %s)", filas)
        cv = correccion.validacion_cruzada(info, icon, obs)
        run.filas = len(filas)
        resumen = (f"{len(info)} estaciones con sesgo; validación cruzada ({cv['n']} horas): "
                   f"error {cv['error_antes'] or 0:.2f} -> {cv['error_despues'] or 0:.2f} °C")
        run.detalle.append(resumen)
        log.info("corrección: %s", resumen)


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
            ("dmc_obs", dmc_observations, None),
            ("correccion", corrections, CORRECTION_EVERY),
            ("armada_avisos", warnings, None),
            ("pasos_dmc", dmc_passes, PASOS_DMC_EVERY),
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
        elif every == "tras_pronostico":   # solo si hay un pronóstico o una corrección más nuevos
            forecast_at = max(filter(None, [last_success(conn, "open_meteo"), last_success(conn, "correccion")]),
                              default=None)
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
