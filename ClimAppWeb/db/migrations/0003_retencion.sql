-- Retención de datos para caber en Supabase Free (500 MB). Medido el 2026-10-01:
-- forecast_archive crece ~1,2 MB/día y observations ~1,1 MB/día (casi todo es el JSON original).
-- La limpieza la hace el job "mantencion" (etl/src/climapp_etl/jobs.py).

-- El JSON original de cada observación se conserva solo unos días; después queda null.
alter table observations alter column raw drop not null;

-- Índice no usado por ninguna consulta (las búsquedas van por la clave primaria).
drop index if exists forecast_archive_valid_time_idx;

-- Índices que usa la limpieza.
create index if not exists forecast_archive_issued_at_idx on forecast_archive (issued_at);
create index if not exists ingestion_runs_started_at_idx on ingestion_runs (started_at);
