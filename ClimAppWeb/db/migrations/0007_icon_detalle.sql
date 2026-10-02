-- Modelo único ICON (decisión del usuario, 2026-10-01; ver docs/precision-evaluacion.md):
-- menor error contra las estaciones DMC y publicación más rápida. GFS queda solo como fuente
-- complementaria de índice UV y visibilidad, que ICON no entrega.
--
-- Variables nuevas para la vista hora a hora (estructura inspirada en Meteored).
alter table forecast_current
    add column if not exists punto_rocio  real,   -- °C
    add column if not exists nubosidad    real,   -- %
    add column if not exists visibilidad  real,   -- m (GFS)
    add column if not exists isoterma_0   real,   -- m sobre el nivel del mar
    add column if not exists nieve        real;   -- cm por hora

-- ECMWF deja de usarse.
delete from forecast_current where modelo = 'ecmwf';
delete from model_runs where modelo = 'ecmwf';
