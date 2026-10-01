-- Corrida de cada modelo que hay en forecast_current. El ETL consulta cada hora los metadatos de
-- Open-Meteo y descarga un modelo solo cuando publicó una corrida más nueva que la registrada aquí.
create table model_runs (
    modelo          text primary key check (modelo in ('gfs', 'ecmwf', 'icon')),
    run_init        timestamptz not null,   -- hora de inicio de la corrida (p. ej. 12 UTC)
    available_at    timestamptz,            -- cuándo Open-Meteo la dejó disponible
    fetched_at      timestamptz not null    -- cuándo la descargamos
);

alter table model_runs enable row level security;
