-- Mezcla ICON + ECMWF IFS (pronóstico base) y comparación con Yr (MET Norway) en forecast_archive.
alter table forecast_archive drop constraint if exists forecast_archive_modelo_check;
alter table forecast_archive add constraint forecast_archive_modelo_check
    check (modelo in ('gfs', 'ecmwf', 'icon', 'yr'));
