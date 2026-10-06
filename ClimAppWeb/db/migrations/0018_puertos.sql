-- Puertos (tipo 'puerto', ya admitido desde 0008): cada puerto se liga a su comuna (avisos de la Armada,
-- nombre de la comuna). Catálogo en etl/data/catalog/puertos.csv (scripts/build_puertos.py); se cargan con
-- la semilla (scripts/migrate.py --seed).
alter table locations add column if not exists comuna_id integer references locations (id);
