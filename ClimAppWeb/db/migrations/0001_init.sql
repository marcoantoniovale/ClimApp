-- ClimApp — esquema inicial (v1), Fase 1.
-- Diseño: docs/fase1-mapeo-requisitos.md §4.2.
-- Se aplica con etl/scripts/migrate.py, que envuelve cada archivo en una transacción.
-- Convenciones: tiempos en UTC (timestamptz); unidades canónicas:
--   temperatura °C, presión hPa, precipitación mm, viento m/s, oleaje m / s / grados.


-- ---------------------------------------------------------------------------
-- Catálogo geográfico
-- ---------------------------------------------------------------------------

create table locations (
    id          serial primary key,
    tipo        text not null check (tipo in ('comuna', 'puerto', 'sector_costero')),
    cut         char(5) unique,               -- código CUT SUBDERE (solo comunas)
    slug        text not null unique,         -- usado en la URL: /comuna/valparaiso
    nombre      text not null,
    alias       text,                         -- nombre alternativo para la búsqueda
    region_id   char(2) not null,
    region      text not null,
    lat         double precision not null check (lat between -90 and -17),
    lon         double precision not null check (lon between -110 and -53),
    es_costera  boolean not null default false -- incluye pronóstico marino
);

create table stations (
    id            text primary key,           -- código en la fuente (p. ej. '66666', 'VALPARAISO')
    red           text not null check (red in ('ema', 'capitania')),
    nombre        text not null,
    lat           double precision not null,
    lon           double precision not null,
    location_id   integer references locations (id),
    activa        boolean not null default true
);

-- ---------------------------------------------------------------------------
-- Pronósticos de modelos (Open-Meteo)
-- ---------------------------------------------------------------------------

-- Último pronóstico por ubicación y modelo. Se reemplaza en cada corrida.
create table forecast_current (
    location_id         integer not null references locations (id),
    modelo              text not null check (modelo in ('gfs', 'ecmwf', 'icon')),
    valid_time          timestamptz not null,
    fetched_at          timestamptz not null,
    temperatura         real,
    sensacion_termica   real,
    estado_cielo        smallint,             -- código WMO (weather_code de Open-Meteo)
    indice_uv           real,
    humedad             real,                 -- %
    precip_prob         real,                 -- %
    precipitacion       real,
    viento_vel          real,
    viento_dir          real,                 -- grados
    viento_rafaga       real,
    presion             real,                 -- nivel del mar
    oleaje_altura       real,                 -- solo ubicaciones costeras
    oleaje_periodo      real,
    oleaje_dir          real,
    primary key (location_id, modelo, valid_time)
);

-- Archivo para verificación y corrección de sesgo (Fase 2): solo en estaciones,
-- horizonte <= 72 h, resolución 3-horaria.
create table forecast_archive (
    station_id          text not null references stations (id),
    modelo              text not null check (modelo in ('gfs', 'ecmwf', 'icon')),
    issued_at           timestamptz not null,  -- hora de la corrida que se consultó
    valid_time          timestamptz not null,
    temperatura         real,
    humedad             real,
    precipitacion       real,
    viento_vel          real,
    viento_dir          real,
    viento_rafaga       real,
    presion             real,
    primary key (station_id, modelo, issued_at, valid_time)
);

-- ---------------------------------------------------------------------------
-- Datos Armada de Chile
-- ---------------------------------------------------------------------------

create table observations (
    station_id          text not null references stations (id),
    observed_at         timestamptz not null,
    fetched_at          timestamptz not null default now(),
    temperatura         real,
    punto_rocio         real,
    humedad             real,
    presion             real,
    viento_vel          real,
    viento_dir          real,
    viento_rafaga       real,
    precipitacion_1h    real,
    raw                 jsonb not null,        -- registro original para trazabilidad
    primary key (station_id, observed_at)
);

-- Avisos (marejadas, mal tiempo, temporal). En la Fase 1 se guardan los metadatos
-- de la página de avisos y el enlace al documento original (imagen/PDF escaneado).
create table marine_warnings (
    id                  text primary key,      -- identificador estable derivado de la fuente
    tipo                text not null,         -- 'marejadas', 'mal_tiempo', 'temporal', ...
    titulo              text not null,
    zona                text not null,         -- texto de la fuente: 'Golfo de Penas hasta Arica ...'
    emitido_at          timestamptz not null,
    vigente_hasta       timestamptz,           -- null si la fuente no lo indica
    url_fuente          text not null,
    url_documento       text,
    texto               text,                  -- se completa cuando haya extracción (OCR/LLM, Fase 2)
    fetched_at          timestamptz not null default now()
);

-- Qué ubicaciones cubre cada aviso (zona de la fuente -> comunas costeras / puertos).
create table marine_warning_locations (
    warning_id          text not null references marine_warnings (id) on delete cascade,
    location_id         integer not null references locations (id),
    primary key (warning_id, location_id)
);

create table bulletins_raw (
    id                  bigserial primary key,
    fuente              text not null,
    emitido_at          timestamptz,
    url                 text not null,
    contenido           text,
    fetched_at          timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Operación
-- ---------------------------------------------------------------------------

create table ingestion_runs (
    id                  bigserial primary key,
    conector            text not null,          -- 'open_meteo', 'armada_obs', 'armada_avisos', ...
    started_at          timestamptz not null default now(),
    finished_at         timestamptz,
    estado              text not null default 'en_curso'
                        check (estado in ('en_curso', 'ok', 'parcial', 'error')),
    filas               integer,
    detalle             text
);

-- Índices para las consultas habituales.
create index observations_observed_at_idx on observations (observed_at);
create index forecast_archive_valid_time_idx on forecast_archive (valid_time);
create index marine_warnings_vigencia_idx on marine_warnings (emitido_at desc);
create index ingestion_runs_conector_idx on ingestion_runs (conector, started_at desc);

