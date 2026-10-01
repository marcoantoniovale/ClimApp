-- Semana 3: oleaje en tabla propia y JSON precalculado por ubicación.

-- El oleaje viene de la API marina de Open-Meteo (un solo modelo), no de GFS/ECMWF/ICON:
-- se saca de forecast_current a su propia tabla, solo para comunas costeras.
alter table forecast_current
    drop column if exists oleaje_altura,
    drop column if exists oleaje_periodo,
    drop column if exists oleaje_dir;

create table forecast_marine (
    location_id         integer not null references locations (id),
    valid_time          timestamptz not null,
    fetched_at          timestamptz not null,
    oleaje_altura       real,                 -- m (altura significativa)
    oleaje_periodo      real,                 -- s
    oleaje_dir          real,                 -- grados (desde donde viene)
    marejada_altura     real,                 -- m (swell)
    primary key (location_id, valid_time)
);

-- Respuesta lista para la API (docs/fase1-mapeo-requisitos.md §4.6). Copia durable de lo que
-- se publica en Redis; la API puede leer de aquí si Redis no está disponible.
create table location_snapshots (
    location_id         integer primary key references locations (id),
    slug                text not null unique,
    payload             jsonb not null,
    updated_at          timestamptz not null default now()
);

alter table forecast_marine     enable row level security;
alter table location_snapshots  enable row level security;
