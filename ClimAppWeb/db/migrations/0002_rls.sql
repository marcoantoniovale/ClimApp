-- Seguridad para Supabase: las tablas del esquema public quedan expuestas en la API REST
-- (PostgREST) con la clave anónima, a menos que tengan Row Level Security.
-- Se activa RLS sin políticas: los roles anon y authenticated no pueden leer ni escribir.
-- El ETL se conecta como dueño de las tablas (postgres), que no está sujeto a RLS.
-- La web no lee Supabase directamente: usa el JSON precalculado en Redis.

alter table locations                enable row level security;
alter table stations                 enable row level security;
alter table forecast_current         enable row level security;
alter table forecast_archive         enable row level security;
alter table observations             enable row level security;
alter table marine_warnings          enable row level security;
alter table marine_warning_locations enable row level security;
alter table bulletins_raw            enable row level security;
alter table ingestion_runs           enable row level security;
