-- Catálogo SINCA en la base (renovado cada semana por el job sinca_catalogo): serie de temperatura de
-- cada estación. Retención menor y limpieza cada hora (docs/localidades-propuesta.md §5).
alter table stations add column if not exists serie text;
