-- Lluvia por mediana de modelos (algoritmo ClimApp, docs/precision-evaluacion.md §10): UKMO (Met Office) y
-- JMA se guardan en forecast_current (solo la columna precipitacion) y su descarga se registra en
-- model_runs. Mientras esta migración no esté aplicada, el ETL no los descarga (jobs.modelos_activos) y la
-- mediana usa ICON, ECMWF y GFS.
--
-- Se eliminan las restricciones CHECK sobre "modelo" de ambas tablas cualquiera sea su nombre (un nombre
-- distinto del esperado dejaría la restricción vieja y haría fallar toda la descarga) y se crean de nuevo.

do $$
declare
    r record;
begin
    for r in
        select c.conrelid::regclass as tabla, c.conname
        from pg_constraint c
        where c.contype = 'c'
          and c.conrelid in ('forecast_current'::regclass, 'model_runs'::regclass)
          and pg_get_constraintdef(c.oid) like '%modelo%'
    loop
        execute format('alter table %s drop constraint %I', r.tabla, r.conname);
    end loop;
end;
$$;

alter table forecast_current add constraint forecast_current_modelo_check
    check (modelo in ('gfs', 'ecmwf', 'icon', 'ukmo', 'jma'));
alter table model_runs add constraint model_runs_modelo_check
    check (modelo in ('gfs', 'ecmwf', 'icon', 'ukmo', 'jma'));
