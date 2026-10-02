-- Pasos fronterizos como ubicaciones (tipo 'paso') con su altura, para pronosticarlos con ICON
-- ajustado a la cota del paso. Catálogo en etl/data/catalog/pasos.csv.
alter table locations drop constraint if exists locations_tipo_check;
alter table locations add constraint locations_tipo_check
    check (tipo in ('comuna', 'puerto', 'sector_costero', 'paso'));
alter table locations add column if not exists altura_m integer;   -- m s. n. m. (pasos)
