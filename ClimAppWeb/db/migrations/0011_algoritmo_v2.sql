-- Algoritmo ClimApp v2 (docs/precision-evaluacion.md §7): registro hora a hora del error de ICON en cada
-- estación, control de calidad, segunda red de mediciones (SINCA) y validación diaria.

-- Red SINCA (Ministerio del Medio Ambiente): estaciones de calidad del aire con temperatura.
alter table stations drop constraint if exists stations_red_check;
alter table stations add constraint stations_red_check check (red in ('ema', 'capitania', 'dmc', 'sinca'));

-- Altura del terreno (m, modelo digital de Open-Meteo) para penalizar estaciones a otra altura.
alter table stations add column if not exists altura_m real;
alter table locations add column if not exists elevacion_m real;

-- Error de ICON por estación y hora: medido vs ICON en el punto de la estación, a la hora de la lectura.
-- Una fila por hora: la lectura más reciente de esa hora.
create table station_residuals (
    station_id   text not null references stations (id) on delete cascade,
    hora         timestamptz not null,            -- inicio de la hora (UTC)
    observed_at  timestamptz not null,            -- instante de la lectura usada
    medido       real not null,                   -- °C
    icon         real not null,                   -- °C, ICON interpolado al instante de la lectura
    qc           text not null default 'ok',      -- ok | rango | residuo | salto | pegado | vecinas
    primary key (station_id, hora)
);
create index station_residuals_hora on station_residuals (hora);
alter table station_residuals enable row level security;

-- Validación diaria del algoritmo (dejando cada estación fuera): errores medios en °C.
create table algoritmo_validacion (
    fecha     timestamptz primary key default now(),
    metricas  jsonb not null
);
alter table algoritmo_validacion enable row level security;
