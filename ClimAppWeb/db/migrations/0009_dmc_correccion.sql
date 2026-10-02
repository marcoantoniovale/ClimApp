-- Estaciones automáticas de la DMC (Dirección Meteorológica de Chile) como fuente de mediciones,
-- y sesgos de ICON por estación para el algoritmo de corrección ClimApp (docs/precision-evaluacion.md).
alter table stations drop constraint if exists stations_red_check;
alter table stations add constraint stations_red_check check (red in ('ema', 'capitania', 'dmc'));

-- Sesgo de la temperatura de ICON (pronóstico − medición) por estación y franja del día (hora de Chile):
-- 0 = 00–05 h, 1 = 06–11 h, 2 = 12–17 h, 3 = 18–23 h.
create table station_bias (
    station_id      text not null references stations (id) on delete cascade,
    franja          smallint not null check (franja between 0 and 3),
    sesgo           real not null,          -- °C, ya atenuado según la cantidad de datos
    sesgo_bruto     real not null,          -- °C, promedio simple
    n               integer not null,       -- horas comparadas
    error_antes     real,                   -- error medio absoluto de ICON sin corregir (°C)
    updated_at      timestamptz not null default now(),
    primary key (station_id, franja)
);

alter table station_bias enable row level security;
