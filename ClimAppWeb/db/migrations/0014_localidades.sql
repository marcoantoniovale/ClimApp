-- Localidades (docs/localidades-propuesta.md) y ahorro de cuota de Open-Meteo.

-- Pronóstico base (ICON y ECMWF) en las estaciones: se renueva solo con cada corrida nueva, en vez de
-- pedirlo cada hora para calcular el error (~10.000 → ~1.800 llamadas al día).
create table station_forecast (
    station_id   text not null references stations (id) on delete cascade,
    modelo       text not null,
    valid_time   timestamptz not null,
    temperatura  real not null,
    fetched_at   timestamptz not null,
    primary key (station_id, modelo, valid_time)
);
alter table station_forecast enable row level security;

-- Perfil de las localidades lejanas a su cabecera (etapa L2): °C a sumar a la curva de la comuna por
-- hora local (24 valores). Se renueva una vez al día.
create table localidad_perfil (
    lugar       text primary key,          -- '<comuna>/<slug>' (data/catalog/localidades.csv)
    perfil      real[] not null,
    fetched_at  timestamptz not null default now()
);
alter table localidad_perfil enable row level security;
