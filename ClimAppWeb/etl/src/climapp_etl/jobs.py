"""Trabajos de ingesta. Cada uno registra su corrida en ingestion_runs."""

from __future__ import annotations

import functools
from concurrent.futures import ThreadPoolExecutor
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

from . import (armada, avisos, correccion, dmc_obs, dmc_pasos, geo, localidades, metno, open_meteo, redis, sinca,
               snapshot, web)
from .db import last_success, track_run

log = logging.getLogger("climapp_etl")

FORECAST_DAYS = 7
ARCHIVE_DAYS = 3            # los días cuentan desde las 00:00 UTC; 3 cubren 48 h desde cualquier hora
ARCHIVE_HORIZON = timedelta(hours=48)
ARCHIVE_STEP_HOURS = 6

# Frecuencias objetivo; el modo "auto" las aplica según la última corrida exitosa,
# así tolera retrasos del disparador.
# El pronóstico se descarga por modelo cuando Open-Meteo publica una corrida nueva (se revisa cada
# hora). FORECAST_EVERY es el respaldo si los metadatos no responden; MODEL_MAX_AGE fuerza una
# descarga si un modelo no se renueva por mucho tiempo.
FORECAST_EVERY = timedelta(hours=6)
MODEL_MAX_AGE = timedelta(hours=9)
# GFS solo aporta índice UV y visibilidad: 2 veces al día bastan (ahorra cuota de Open-Meteo).
MODEL_MIN_INTERVAL = {"gfs": timedelta(hours=11)}
MODEL_MAX_AGE_POR_MODELO = {"gfs": timedelta(hours=15)}
STATION_FORECAST_MAX_AGE = timedelta(hours=6)   # respaldo si no hay registro de corridas
LOCALIDADES_PERFIL_EVERY = timedelta(hours=24)
MARINE_EVERY = timedelta(hours=3)
PASOS_DMC_EVERY = timedelta(hours=3)   # la DMC emite ~2 veces al día
CORRECTION_EVERY = timedelta(hours=3)
VALIDATION_EVERY = timedelta(hours=20)  # validación del algoritmo ClimApp (una vez al día)
RESIDUOS_HORAS = 48                    # horas hacia atrás que revisa el registro de errores
DMC_MAX_AGE = timedelta(hours=3)       # lecturas más antiguas del mapa DMC no se guardan
PUBLICA_EN_WEB = {"snapshots", "armada_avisos", "pasos_dmc", "residuos", "localidades"}   # tras ellos, renovar la web
ARCHIVE_EVERY = timedelta(hours=24)
MAINTENANCE_EVERY = timedelta(hours=1)   # limpieza cada hora: cada historial se borra apenas cumple su plazo
SINCA_CATALOGO_EVERY = timedelta(days=7)
MARGIN = timedelta(minutes=30)

# Retención (docs/localidades-propuesta.md §5; aprobada por el usuario el 2026-10-03). Se revisa según
# la capacidad disponible: el job `mantencion` informa el tamaño de cada tabla en ingestion_runs.
RETENTION = {
    "forecast_archive": timedelta(days=30),     # ICON, ECMWF y Yr en las estaciones (~1,1 MB/día)
    "observations": timedelta(days=60),         # ~0,8 MB/día
    "observations_raw": timedelta(days=14),
    "ingestion_runs": timedelta(days=30),
    "station_residuals": timedelta(days=35),    # el sesgo usa 30 días (~0,8 MB/día)
    "algoritmo_validacion": timedelta(days=365),
    "station_forecast": timedelta(days=7),      # se reemplaza con cada corrida; esto limpia estaciones dadas de baja
}
TABLAS_INFORME = ["forecast_current", "forecast_archive", "observations", "station_residuals",
                  "location_snapshots", "forecast_marine", "ingestion_runs"]

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
            if m not in state
            or (runs[m].init > state[m][0] and now - state[m][1] >= MODEL_MIN_INTERVAL.get(m, timedelta(0)))
            or now - state[m][1] >= MODEL_MAX_AGE_POR_MODELO.get(m, MODEL_MAX_AGE)]


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
        modelos = ["icon", "ecmwf"]
        responses = open_meteo.fetch(points, open_meteo.ARCHIVE_VARIABLES, ARCHIVE_DAYS, models=modelos)

        def vale(valid_time: datetime) -> bool:
            return issued_at <= valid_time <= issued_at + ARCHIVE_HORIZON and valid_time.hour % ARCHIVE_STEP_HOURS == 0

        records = [
            (point.key, model, issued_at, valid_time, *values.values())
            for point, data in responses
            for model, valid_time, values in open_meteo.rows(data, open_meteo.ARCHIVE_VARIABLES, models=modelos)
            if vale(valid_time)
        ]
        # Yr (MET Norway), para comparar con la mezcla: misma grilla de horas.
        columnas = list(open_meteo.ARCHIVE_VARIABLES.values())

        def yr(point: open_meteo.Point):
            try:
                return point, metno.rows(metno.fetch(point.lat, point.lon)), None
            except Exception as exc:
                return point, [], exc

        with ThreadPoolExecutor(max_workers=4) as pool:
            yr_resultados = list(pool.map(yr, points))
        records += [(point.key, "yr", issued_at, t, *(v.get(c) for c in columnas))
                    for point, serie, _ in yr_resultados for t, v in serie if vale(t)]
        fallas = sum(1 for _, _, exc in yr_resultados if exc)
        if fallas:
            run.warn(f"Yr: {fallas} de {len(points)} estaciones sin pronóstico")
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
                               "altura_m", "elevacion_m"), r))
                     for r in conn.execute("""select id, slug, nombre, alias, region, tipo, lat, lon, es_costera,
                                                     altura_m, elevacion_m from locations order by id""")]
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
        observations = _mediciones(conn, locations)

        estaciones_sesgo = _estaciones_con_sesgo(conn)
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
                    correccion.correccion(loc["lat"], loc["lon"], loc["elevacion_m"], loc["es_costera"],
                                          estaciones_sesgo))
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


def _mediciones(conn: psycopg.Connection, locations: list[dict]) -> dict[int, dict]:
    """Por comuna, la última medición (≤ 3 h) de la estación más cercana de la misma zona (algoritmo ClimApp)."""
    lecturas = _lecturas(conn)
    out = {}
    for loc in locations:
        if loc["tipo"] != "comuna":
            continue
        m = correccion.medicion_cercana(loc["lat"], loc["lon"], loc["es_costera"], lecturas)
        if m:
            out[loc["id"]] = m
    return out


def _lecturas(conn: psycopg.Connection) -> list[dict]:
    """Última lectura válida (≤ 3 h) de cada estación, para mostrar como "Medido en …"."""
    return [{"estacion": r[0], "red": r[1], "hora": snapshot._iso_local(r[2]), "temperatura": r[3],
                 "humedad": r[4], "presion": r[5], "viento": None if r[6] is None else round(r[6] * 3.6),
                 "viento_dir": r[7], "lat": r[8], "lon": r[9], "costera": r[10]}
                for r in conn.execute("""
        select distinct on (s.id) s.nombre, s.red, o.observed_at, o.temperatura, o.humedad, o.presion,
               o.viento_vel, o.viento_dir, s.lat, s.lon, coalesce(l.es_costera, false)
        from observations o join stations s on s.id = o.station_id
        left join locations l on l.id = s.location_id
        where o.observed_at > now() - interval '3 hours' and o.temperatura is not null
          and not exists (select 1 from station_residuals r where r.station_id = s.id
                          and r.hora = date_trunc('hour', o.observed_at) and r.qc <> 'ok')
        order by s.id, o.observed_at desc""")]


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


def _ubicador(conn: psycopg.Connection):
    """Función (lat, lon) → location_id de la comuna que contiene el punto (polígonos comunales); si el
    punto cae fuera de todo polígono (mar, Antártica), la comuna de cabecera más cercana."""
    comunas = [(r[0], r[1], r[2], r[3]) for r in conn.execute(
        "select id, slug, lat, lon from locations where tipo = 'comuna'")]
    por_slug = {slug: i for i, slug, _, _ in comunas}

    def ubicar(lat: float, lon: float) -> int:
        slug = geo.comuna_de(lat, lon)
        if slug in por_slug:
            return por_slug[slug]
        return min(comunas, key=lambda c: correccion.km(lat, lon, c[2], c[3]))[0]
    return ubicar


def _upsert_stations(conn: psycopg.Connection, red: str, estaciones: list[dict]) -> None:
    """Estaciones [{id, nombre, lat, lon}] en `stations`, asociadas a la comuna que las contiene."""
    ubicar = _ubicador(conn)
    with conn.cursor() as cur:
        cur.executemany("""
            insert into stations (id, red, nombre, lat, lon, location_id)
            values (%(id)s, %(red)s, %(nombre)s, %(lat)s, %(lon)s, %(loc)s)
            on conflict (id) do update set nombre = excluded.nombre, lat = excluded.lat, lon = excluded.lon,
                location_id = excluded.location_id""",
            [e | {"red": red, "loc": ubicar(e["lat"], e["lon"])} for e in estaciones])


def _upsert_dmc_stations(conn: psycopg.Connection, estaciones: list[dict]) -> None:
    _upsert_stations(conn, "dmc", [{"id": f"dmc-{e['codigo']}", "nombre": e["nombre"], "lat": e["lat"],
                                    "lon": e["lon"]} for e in estaciones])


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


def sinca_observations(conn: psycopg.Connection) -> None:
    """Temperatura horaria de las estaciones SINCA con temperatura (catálogo) → stations + observations."""
    with track_run(conn, "sinca_obs") as run:
        catalogo = [sinca.Estacion(r[0].removeprefix("sinca-"), r[1].removesuffix(" (SINCA)"), "", r[2], r[3], r[4])
                    for r in conn.execute("""select id, nombre, lat, lon, serie from stations
                                             where red = 'sinca' and activa and serie is not null""")]
        catalogo = catalogo or sinca.cargar_catalogo()   # primera vez: la semilla del repositorio
        if not catalogo:
            raise RuntimeError("Sin catálogo SINCA (job sinca_catalogo o scripts/build_sinca.py)")
        now = datetime.now(timezone.utc)

        def leer(est: sinca.Estacion):
            try:
                return est, sinca.fetch_temperaturas(est, now - timedelta(days=1), now), None
            except Exception as exc:  # una estación caída no detiene a las demás
                return est, {}, exc

        with ThreadPoolExecutor(max_workers=6) as pool:
            resultados = list(pool.map(leer, catalogo))
        errores = [f"{e.nombre}: {exc}" for e, _, exc in resultados if exc]
        with conn.transaction():
            _guardar_sinca(conn, catalogo)
            with conn.cursor() as cur:
                cur.executemany("""insert into observations (station_id, observed_at, temperatura) values (%s, %s, %s)
                                   on conflict (station_id, observed_at) do nothing""",
                                [(e.id, t, v) for e, serie, _ in resultados for t, v in serie.items()])
                run.filas = max(cur.rowcount, 0)
        if errores:
            run.warn(f"{len(errores)} estaciones sin datos: {'; '.join(errores[:5])}")
        if len(errores) == len(catalogo):
            raise RuntimeError("SINCA no respondió")
        log.info("SINCA: %d estaciones, %d lecturas nuevas, %d con error", len(catalogo), run.filas, len(errores))


def _guardar_sinca(conn: psycopg.Connection, catalogo: list[sinca.Estacion]) -> None:
    _upsert_stations(conn, "sinca", [{"id": e.id, "nombre": f"{e.nombre} (SINCA)", "lat": e.lat, "lon": e.lon}
                                     for e in catalogo])
    with conn.cursor() as cur:
        cur.executemany("update stations set serie = %s, activa = true where id = %s",
                        [(e.serie, e.id) for e in catalogo])


def sinca_catalog(conn: psycopg.Connection) -> None:
    """Renueva el catálogo SINCA (estaciones con temperatura vigente) en `stations`. Las que dejan de
    publicar temperatura quedan inactivas (sus datos se conservan hasta que vence su retención)."""
    with track_run(conn, "sinca_catalogo") as run:
        estaciones, total = sinca.descubrir()
        if len(estaciones) < 20:   # protección: una respuesta rota no debe desactivar la red
            raise RuntimeError(f"SINCA entregó solo {len(estaciones)} estaciones con temperatura")
        with conn.transaction():
            _guardar_sinca(conn, estaciones)
            bajas = conn.execute("update stations set activa = false where red = 'sinca' and activa and id <> all(%s)",
                                 ([e.id for e in estaciones],)).rowcount
        run.filas = len(estaciones)
        run.detalle.append(f"{len(estaciones)} con temperatura de {total}; {bajas} desactivadas")
        log.info("catálogo SINCA: %d estaciones con temperatura de %d, %d desactivadas", len(estaciones), total, bajas)


def _completar_alturas(conn: psycopg.Connection, budget: open_meteo.MinuteBudget) -> None:
    """Altura del terreno de estaciones y comunas que aún no la tienen (una vez por punto)."""
    for tabla, columna, filtro in (("stations", "altura_m", "true"), ("locations", "elevacion_m", "tipo = 'comuna'")):
        puntos = [open_meteo.Point(r[0], r[1], r[2]) for r in conn.execute(
            f"select id, lat, lon from {tabla} where {columna} is null and {filtro}")]
        if not puntos:
            continue
        try:
            alturas = open_meteo.elevations(puntos, budget)
        except Exception:  # auxiliar: sin altura, la interpolación solo usa la distancia
            log.exception("alturas de %s", tabla)
            continue
        with conn.cursor() as cur:
            cur.executemany(f"update {tabla} set {columna} = %s where id = %s", [(h, k) for k, h in alturas.items()])
        log.info("alturas: %d puntos en %s", len(alturas), tabla)


def _estaciones(conn: psycopg.Connection, where: str = "true", params: tuple = ()) -> list[dict]:
    return [{"id": r[0], "nombre": r[1], "red": r[2], "lat": r[3], "lon": r[4], "altura": r[5], "costera": r[6]}
            for r in conn.execute(f"""
        select s.id, s.nombre, s.red, s.lat, s.lon, s.altura_m, coalesce(l.es_costera, false)
        from stations s left join locations l on l.id = s.location_id
        where s.red in ('dmc', 'sinca') and {where} order by s.id""", params)]


def _estaciones_con_sesgo(conn: psycopg.Connection) -> list[dict]:
    sesgos: dict[str, dict] = defaultdict(dict)
    for sid, f, s in conn.execute("select station_id, franja, sesgo from station_bias"):
        sesgos[sid][f] = s
    return [e | {"sesgos": sesgos[e["id"]]} for e in _estaciones(conn) if e["id"] in sesgos]


def _interpolar_icon(serie: dict[datetime, float], t: datetime) -> float | None:
    """ICON (horario) interpolado linealmente al instante t."""
    t0 = t.replace(minute=0, second=0, microsecond=0)
    a, b = serie.get(t0), serie.get(t0 + timedelta(hours=1))
    if a is None or b is None:
        return a if t == t0 else None
    return a + (b - a) * (t - t0).total_seconds() / 3600


def residuals(conn: psycopg.Connection, reconstruir_dias: int = 0) -> None:
    """Algoritmo ClimApp, paso 1: error de ICON por estación y hora (con control de calidad) →
    station_residuals (una fila por hora, con la lectura más reciente de esa hora).
    reconstruir_dias > 0: vuelve a calcular esos días con el pronóstico base actual (p. ej. al cambiar
    la mezcla de modelos), reemplazando lo registrado. Luego publica el ajuste del momento por comuna (clave `algoritmo`)."""
    with track_run(conn, "residuos") as run:
        budget = open_meteo.MinuteBudget()
        _completar_alturas(conn, budget)
        horas = max(RESIDUOS_HORAS, reconstruir_dias * 24)
        extra_dias = max(0, reconstruir_dias - 2)
        estaciones = {e["id"]: e for e in _estaciones(conn, f"""exists (select 1 from observations o
            where o.station_id = s.id and o.observed_at > now() - interval '{horas} hours')""")}
        lecturas: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        for sid, t, v in conn.execute(f"""
                select station_id, observed_at, temperatura from observations
                where station_id = any(%s) and temperatura is not null
                  and observed_at > now() - interval '{horas + 8} hours'
                order by station_id, observed_at""", (list(estaciones),)):
            lecturas[sid].append((t, v))
        existentes = {} if reconstruir_dias else {
            (r[0], r[1]): r[2] for r in conn.execute(f"""select station_id, hora, observed_at from station_residuals
                                                      where hora > now() - interval '{horas + 1} hours'""")}

        icon = _pronostico_estaciones(conn, estaciones, budget, 3 + extra_dias, forzar=bool(reconstruir_dias))

        desde = datetime.now(timezone.utc) - timedelta(hours=horas)
        nuevas: dict[datetime, list[dict]] = defaultdict(list)
        for sid, serie in lecturas.items():
            por_hora: dict[datetime, tuple[datetime, float]] = {}
            for t, v in serie:   # la última lectura de cada hora
                por_hora[t.replace(minute=0, second=0, microsecond=0)] = (t, v)
            previas: list[tuple[datetime, float]] = []
            for hora in sorted(por_hora):
                t, v = por_hora[hora]
                p = _interpolar_icon(icon.get(sid, {}), t)
                # nueva hora, o una lectura más reciente dentro de una hora ya registrada
                if p is not None and hora >= desde and existentes.get((sid, hora), t - timedelta(seconds=1)) < t:
                    e = estaciones[sid]
                    nuevas[hora].append({"station_id": sid, "hora": hora, "observed_at": t, "medido": v, "icon": p,
                                         "residuo": p - v, "qc": correccion.qc_lectura(v, p, previas, t),
                                         "lat": e["lat"], "lon": e["lon"], "costera": e["costera"]})
                previas.append((t, v))
        for grupo in nuevas.values():
            correccion.qc_vecinas(grupo)
        filas = [f for grupo in nuevas.values() for f in grupo]
        with conn.transaction():
            if reconstruir_dias:
                conn.execute("delete from station_residuals where hora >= %s", (desde,))
            with conn.cursor() as cur:
                cur.executemany("""insert into station_residuals (station_id, hora, observed_at, medido, icon, qc)
                                   values (%(station_id)s, %(hora)s, %(observed_at)s, %(medido)s, %(icon)s, %(qc)s)
                                   on conflict (station_id, hora) do update set observed_at = excluded.observed_at,
                                       medido = excluded.medido, icon = excluded.icon, qc = excluded.qc
                                   where excluded.observed_at > station_residuals.observed_at""", filas)
        rechazadas: dict[str, int] = defaultdict(int)
        for f in filas:
            if f["qc"] != "ok":
                rechazadas[f["qc"]] += 1
        run.filas = len(filas)
        run.detalle.append(f"{len(estaciones)} estaciones; {len(filas)} horas nuevas; control de calidad: "
                           f"{dict(rechazadas) or 'todo ok'}")
        comunas = _publicar_algoritmo(conn)
        log.info("residuos: %d estaciones, %d horas nuevas, qc %s; ajuste publicado para %d comunas",
                 len(estaciones), len(filas), dict(rechazadas), comunas)


def _pronostico_estaciones(conn: psycopg.Connection, estaciones: dict[str, dict], budget: open_meteo.MinuteBudget,
                           past_days: int, forzar: bool = False) -> dict[str, dict[datetime, float]]:
    """Pronóstico base (promedio ICON + ECMWF) en cada estación, desde station_forecast. Solo se pide a
    Open-Meteo lo que falta o lo que tiene una corrida más nueva (model_runs)."""
    now = datetime.now(timezone.utc)
    base = list(correccion.MODELOS_BASE)
    corridas = dict(conn.execute("select modelo, fetched_at from model_runs where modelo = any(%s)", (base,)).fetchall())
    guardado = {(r[0], r[1]): r[2] for r in conn.execute(
        "select station_id, modelo, max(fetched_at) from station_forecast group by 1, 2")}
    variables = {"temperature_2m": "temperatura"}
    pedidas = 0
    for m in base:
        def vencido(sid: str) -> bool:
            f = guardado.get((sid, m))
            return forzar or f is None or (m in corridas and f < corridas[m]) or now - f >= STATION_FORECAST_MAX_AGE
        puntos = [open_meteo.Point(e["id"], e["lat"], e["lon"]) for e in estaciones.values() if vencido(e["id"])]
        if not puntos:
            continue
        filas = [(p.key, m, t, v["temperatura"], now)
                 for p, data in open_meteo.fetch(puntos, variables, 1, past_days=past_days, budget=budget, models=[m])
                 for _, t, v in open_meteo.rows(data, variables, models=[m]) if v["temperatura"] is not None]
        with conn.transaction():
            conn.execute("delete from station_forecast where modelo = %s and station_id = any(%s)",
                         (m, [p.key for p in puntos]))
            _copy(conn, "station_forecast", ["station_id", "modelo", "valid_time", "temperatura", "fetched_at"], filas)
        pedidas += len(puntos)
    if pedidas:
        log.info("pronóstico en estaciones: %d descargas (corrida nueva o faltante)", pedidas)
    out: dict[str, dict[datetime, float]] = defaultdict(dict)
    for sid, t, v in conn.execute("""select station_id, valid_time, avg(temperatura) from station_forecast
                                     where station_id = any(%s) and modelo = any(%s)
                                     group by 1, 2 having count(*) = %s""", (list(estaciones), base, len(base))):
        out[sid][t] = v
    return out


def _ultima_validacion(conn: psycopg.Connection) -> tuple[datetime | None, dict]:
    fila = conn.execute("select fecha, metricas from algoritmo_validacion order by fecha desc limit 1").fetchone()
    return (fila[0], fila[1]) if fila else (None, {})


def _anomalias(conn: psycopg.Connection) -> list[dict]:
    """Anomalía del momento en cada estación: medido − (pronóstico base − sesgo), última lectura válida (≤ 3 h)."""
    todas = {e["id"]: e for e in _estaciones(conn)}
    sesgos = {e["id"]: e["sesgos"] for e in _estaciones_con_sesgo(conn)}
    anomalias = []
    for sid, t, medido, p in conn.execute("""
            select distinct on (station_id) station_id, observed_at, medido, icon from station_residuals
            where qc = 'ok' and observed_at > now() - %s order by station_id, hora desc""",
            (correccion.ANOMALIA_MAX_EDAD,)):
        if sid in todas:
            sesgo = sesgos.get(sid, {}).get(correccion.franja(t), 0.0)
            anomalias.append(todas[sid] | {"valor": medido - (p - sesgo), "t": t})
    return anomalias


def _anomalia_en(lat: float, lon: float, altura: float | None, costera: bool, anomalias: list[dict],
                 max_estaciones: int | None = None) -> dict:
    """{anomalia, hora (promedio ponderado de las lecturas), estaciones} interpolados en un punto, o {}."""
    r = correccion.interpolar(lat, lon, altura, costera, anomalias)
    if not r:
        return {}
    instantes = {a["nombre"]: a["t"] for a in anomalias}
    t_medio = sum(instantes[x["nombre"]].timestamp() * x["peso"] for x in r["estaciones"]) \
        / sum(x["peso"] for x in r["estaciones"])
    return {"anomalia": round(r["valor"], 2),
            "hora": snapshot._iso_local(datetime.fromtimestamp(t_medio, timezone.utc)),
            "estaciones": r["estaciones"][:max_estaciones]}


def _publicar_algoritmo(conn: psycopg.Connection) -> int:
    """Clave `algoritmo`: por comuna, la anomalía del momento interpolada (°C a sumar a la curva corregida),
    su hora, las estaciones usadas y la medición más cercana para mostrar; además τ y la última validación."""
    anomalias = _anomalias(conn)
    locations = [dict(zip(("id", "slug", "tipo", "lat", "lon", "es_costera", "elevacion_m"), r)) for r in conn.execute(
        "select id, slug, tipo, lat, lon, es_costera, elevacion_m from locations where tipo = 'comuna'")]
    mediciones = _mediciones(conn, locations)
    _, validacion = _ultima_validacion(conn)
    tau = validacion.get("tau_h") or correccion.TAU_H
    comunas = {}
    for loc in locations:
        entrada = _anomalia_en(loc["lat"], loc["lon"], loc["elevacion_m"], loc["es_costera"], anomalias)
        if loc["id"] in mediciones:
            entrada["medicion"] = mediciones[loc["id"]]
        if entrada:
            comunas[loc["slug"]] = entrada
    redis.publish({"algoritmo": {"generado": snapshot._iso_local(datetime.now(timezone.utc)), "tau_h": tau,
                                 "validacion": validacion, "comunas": comunas}})
    return sum(1 for c in comunas.values() if "anomalia" in c)


def localities_profiles(conn: psycopg.Connection) -> None:
    """Localidades lejanas a su cabecera (etapa L2): mezcla ICON + ECMWF en el centro de su celda de 0,1° y
    perfil por hora local respecto de la comuna → localidad_perfil. Una vez al día (cuota gratuita)."""
    with track_run(conn, "localidades_perfil") as run:
        lejanas = [l for l in localidades.cargar() if l["km_cabecera"] > localidades.LEJOS_KM]
        grupos: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for l in lejanas:
            grupos[localidades.celda(l["lat"], l["lon"])].append(l)
        centros = [open_meteo.Point(k, sum(l["lat"] for l in ls) / len(ls), sum(l["lon"] for l in ls) / len(ls))
                   for k, ls in grupos.items()]
        base = list(correccion.MODELOS_BASE)
        variables = {"temperature_2m": "temperatura"}
        curvas: dict[tuple[int, int], dict[datetime, list[float]]] = defaultdict(lambda: defaultdict(list))
        alturas: dict[tuple[int, int], float] = {}
        for m in base:
            for p, data in open_meteo.fetch(centros, variables, FORECAST_DAYS, models=[m]):
                alturas[p.key] = data.get("elevation")
                for _, t, v in open_meteo.rows(data, variables, models=[m]):
                    if v["temperatura"] is not None:
                        curvas[p.key][t].append(v["temperatura"])
        comunas: dict[str, dict[datetime, float]] = defaultdict(dict)
        for slug, t, v in conn.execute("""
                select l.slug, f.valid_time, avg(f.temperatura) from forecast_current f
                join locations l on l.id = f.location_id
                where l.tipo = 'comuna' and f.modelo = any(%s) and f.temperatura is not null and f.valid_time >= now()
                group by 1, 2 having count(*) = %s""", (base, len(base))):
            comunas[slug][t] = v
        filas = []
        for k, ls in grupos.items():
            mezcla = {t: sum(vs) / len(vs) for t, vs in curvas.get(k, {}).items() if len(vs) == len(base)}
            for l in ls:
                ref = comunas.get(l["comuna"], {})
                dif = {t: v + localidades.por_altura(alturas.get(k), l["altura"]) - ref[t]
                       for t, v in mezcla.items() if t in ref}
                perfil = localidades.perfil_horario(dif)
                if perfil:
                    filas.append((localidades.clave(l), perfil))
        with conn.transaction():
            conn.execute("delete from localidad_perfil")
            with conn.cursor() as cur:
                cur.executemany("insert into localidad_perfil (lugar, perfil) values (%s, %s)", filas)
        run.filas = len(filas)
        run.detalle.append(f"{len(lejanas)} localidades lejanas en {len(centros)} celdas; {len(filas)} perfiles")
        log.info("perfiles de localidades: %d localidades lejanas, %d celdas, %d perfiles",
                 len(lejanas), len(centros), len(filas))


def localities(conn: psycopg.Connection) -> None:
    """Ajuste de cada localidad (etapa L1) → Redis, una clave por comuna (`lugares:<comuna>`). Cada hora."""
    with track_run(conn, "localidades") as run:
        catalogo = localidades.cargar()
        if not catalogo:
            raise RuntimeError("Sin catálogo de localidades (scripts/build_localidades.py)")
        estaciones = _estaciones_con_sesgo(conn)
        anomalias = _anomalias(conn)
        lecturas = _lecturas(conn)
        perfiles = dict(conn.execute("select lugar, perfil from localidad_perfil").fetchall())
        comunas = {r[0]: {"lat": r[1], "lon": r[2], "elevacion_m": r[3], "es_costera": r[4]} for r in conn.execute(
            "select slug, lat, lon, elevacion_m, es_costera from locations where tipo = 'comuna'")}
        sesgo_comuna = {s: correccion.correccion(c["lat"], c["lon"], c["elevacion_m"], c["es_costera"], estaciones)["franjas"]
                        for s, c in comunas.items()}
        _, validacion = _ultima_validacion(conn)
        generado = snapshot._iso_local(datetime.now(timezone.utc))
        por_comuna: dict[str, dict] = defaultdict(dict)
        for l in catalogo:
            c = comunas.get(l["comuna"])
            if c is None:
                continue
            costera = c["es_costera"]   # zona de la comuna (validado: ver correccion.interpolar)
            propio = correccion.correccion(l["lat"], l["lon"], l["altura"], costera, estaciones)["franjas"]
            entrada = localidades.ajuste(l, sesgo_comuna[l["comuna"]], propio, perfiles.get(localidades.clave(l)),
                                         c["elevacion_m"])
            entrada |= _anomalia_en(l["lat"], l["lon"], l["altura"], costera, anomalias, max_estaciones=2)
            m = correccion.medicion_cercana(l["lat"], l["lon"], costera, lecturas)
            if m:
                entrada["medicion"] = {k: m.get(k) for k in ("estacion", "red", "hora", "temperatura", "viento", "km")}
            por_comuna[l["comuna"]][l["slug"]] = entrada
        tau = validacion.get("tau_h") or correccion.TAU_H
        publicadas = redis.publish({f"lugares:{s}": {"generado": generado, "tau_h": tau, "lugares": lugares}
                                    for s, lugares in por_comuna.items()})
        run.filas = sum(len(v) for v in por_comuna.values())
        con_perfil = sum(1 for l in catalogo if localidades.clave(l) in perfiles)
        run.detalle.append(f"{run.filas} localidades en {len(por_comuna)} comunas ({con_perfil} con perfil propio); "
                           f"redis={publicadas}")
        log.info("localidades: %d en %d comunas, %d con perfil propio, redis=%d",
                 run.filas, len(por_comuna), con_perfil, publicadas)


def corrections(conn: psycopg.Connection) -> None:
    """Algoritmo ClimApp, paso 2: sesgo de ICON por estación y franja desde el registro de errores
    (olvido exponencial) → station_bias. Una vez al día, validación y ajuste de τ."""
    with track_run(conn, "correccion") as run:
        now = datetime.now(timezone.utc)
        residuos: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        for sid, t, r in conn.execute("""
                select station_id, hora, icon - medido from station_residuals
                where qc = 'ok' and hora > now() - make_interval(days => %s)""", (correccion.VENTANA_DIAS,)):
            residuos[sid].append((t, r))
        filas = []
        for sid, serie in residuos.items():
            filas += [(sid, f, v["sesgo"], v["sesgo_bruto"], v["n"], v["error_antes"])
                      for f, v in correccion.sesgos(serie, now).items()]
        with conn.transaction():
            conn.execute("delete from station_bias")
            with conn.cursor() as cur:
                cur.executemany("insert into station_bias (station_id, franja, sesgo, sesgo_bruto, n, error_antes)"
                                " values (%s, %s, %s, %s, %s, %s)", filas)
        run.filas = len(filas)
        run.detalle.append(f"{len(residuos)} estaciones con sesgo")

        ultima, _ = _ultima_validacion(conn)
        if ultima is None or now - ultima >= VALIDATION_EVERY - MARGIN:
            metricas = _validar(conn, residuos, now)
            conn.execute("insert into algoritmo_validacion (metricas) values (%s)", (Jsonb(metricas),))
            resumen = (f"validación ({metricas['horas']} h): ICON {metricas['icon']} °C; sin estación "
                       f"{metricas['sin_estacion']}; con estación {metricas['con_estacion']}; τ {metricas['tau_h']} h")
            run.detalle.append(resumen)
            log.info("corrección: %s", resumen)
        log.info("corrección: %d estaciones con sesgo", len(residuos))


def _validar(conn: psycopg.Connection, residuos: dict[str, list[tuple[datetime, float]]], now: datetime) -> dict:
    """Validación de los últimos 7 días y ajuste de τ con la persistencia de la anomalía."""
    estaciones = _estaciones_con_sesgo(conn)
    desde = now - timedelta(days=7)
    recientes = {sid: {t: r for t, r in serie if t >= desde} for sid, serie in residuos.items()}
    por_id = {e["id"]: e for e in estaciones}
    anomalias = {sid: {t: por_id[sid]["sesgos"].get(correccion.franja(t), 0.0) - r for t, r in serie.items()}
                 for sid, serie in recientes.items() if sid in por_id}
    tau, factores = correccion.ajustar_tau(anomalias)
    metricas = correccion.validar(estaciones, recientes, tau)
    metricas["persistencia"] = {str(k): round(v, 3) for k, v in factores.items()}
    metricas["estaciones"] = len(estaciones)
    return metricas


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
            "station_residuals": ("delete from station_residuals where hora < %s", now - RETENTION["station_residuals"]),
            "algoritmo_validacion": ("delete from algoritmo_validacion where fecha < %s",
                                     now - RETENTION["algoritmo_validacion"]),
            "station_forecast": ("delete from station_forecast where valid_time < %s", now - RETENTION["station_forecast"]),
        }
        counts = {}
        for name, (sql, cutoff) in statements.items():
            params = (cutoff, run.id) if name == "ingestion_runs" else (cutoff,)
            counts[name] = conn.execute(sql, params).rowcount
        size = conn.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
        tablas = {t: round(conn.execute("select pg_total_relation_size(%s)", (t,)).fetchone()[0] / 1e6, 1)
                  for t in TABLAS_INFORME}
        run.filas = sum(counts.values())
        run.detalle.append(f"borradas: {counts}")
        run.detalle.append(f"tamaño: base {size}; MB por tabla {tablas}")
        log.info("mantención: borradas %s; base %s; MB por tabla %s", counts, size, tablas)


def auto(conn: psycopg.Connection, with_observations: bool = True) -> None:
    """Lo que corresponda según la última corrida exitosa: observaciones siempre,
    pronóstico por modelo al publicarse una corrida nueva, archivo cada 24 h, avisos cada hora,
    precálculo tras cada pronóstico y limpieza (retención) cada hora. Pensado para un disparo horario.

    with_observations=False: la API de observaciones de la Armada bloquea las redes de nube
    (GitHub Actions/Azure, AWS); ahí las observaciones se recolectan desde un equipo en Chile."""
    now = datetime.now(timezone.utc)
    failures = []
    publicado = False
    jobs = [("open_meteo", forecast, "por_corrida"),
            ("open_meteo_archivo", archive, ARCHIVE_EVERY),
            ("dmc_obs", dmc_observations, None),
            ("sinca_catalogo", sinca_catalog, SINCA_CATALOGO_EVERY),
            ("sinca_obs", sinca_observations, None),
            ("residuos", residuals, None),
            ("localidades_perfil", localities_profiles, LOCALIDADES_PERFIL_EVERY),
            ("correccion", corrections, CORRECTION_EVERY),
            ("armada_avisos", warnings, None),
            ("pasos_dmc", dmc_passes, PASOS_DMC_EVERY),
            ("snapshots", snapshots, "tras_pronostico"),
            ("localidades", localities, None),
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
        elif every == "tras_pronostico":   # si hay un pronóstico o una corrección más nuevos, o cambió el día
            forecast_at = max(filter(None, [last_success(conn, "open_meteo"), last_success(conn, "correccion")]),
                              default=None)
            mismo_dia = last and last.astimezone(snapshot.CHILE).date() == now.astimezone(snapshot.CHILE).date()
            if last and forecast_at and last > forecast_at and mismo_dia:
                log.info("%s: no corresponde (sin pronóstico nuevo)", name)
                continue
        elif every and last and now - last < every - MARGIN:
            log.info("%s: no corresponde (última %s)", name, last.isoformat(timespec="minutes"))
            continue
        try:
            job(conn)
            if name in PUBLICA_EN_WEB:
                publicado = True
        except Exception as exc:  # un conector caído no detiene a los demás
            log.exception("%s falló", name)
            failures.append(f"{name}: {exc}")
    if publicado:  # la web renueva sus páginas al instante (ver web.py)
        log.info("web: renovación %s", "ok" if web.revalidar() else "no disponible")
    if failures:
        raise RuntimeError("; ".join(failures))


def _copy(conn: psycopg.Connection, table: str, columns: list[str], records: list[tuple]) -> None:
    with conn.cursor() as cur:
        with cur.copy(f"copy {table} ({', '.join(columns)}) from stdin") as copy:
            for record in records:
                copy.write_row(record)
