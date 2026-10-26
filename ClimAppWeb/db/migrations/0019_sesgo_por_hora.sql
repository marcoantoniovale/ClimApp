-- Sesgo de la temperatura por hora local (0–23) con las horas vecinas, en vez de 4 franjas de 6 h
-- (recalibración del 2026-10-26, docs/precision-evaluacion.md §11). El job `correccion` reescribe la tabla.
alter table station_bias drop constraint if exists station_bias_franja_check;
alter table station_bias add constraint station_bias_franja_check check (franja between 0 and 23);
