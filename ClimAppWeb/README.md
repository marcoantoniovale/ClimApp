# ClimAppWeb

Código fuente de ClimApp. Contexto, decisiones y bitácora en [../CLAUDE.md](../CLAUDE.md); diseño de la Fase 1 en [../docs/fase1-mapeo-requisitos.md](../docs/fase1-mapeo-requisitos.md).

| Carpeta | Contenido | Tecnología |
|---|---|---|
| [etl/](etl/) | Conectores (Open-Meteo, Armada), normalización, precálculo; scripts de catálogo | Python 3.12 |
| [db/](db/) | Migraciones SQL del esquema | PostgreSQL (Supabase) |
| [web/](web/) | Frontend y API (Route Handlers) | Next.js + Tailwind (semana 4) |

## Requisitos locales

- Python 3.12 (`%LOCALAPPDATA%\Programs\Python\Python312\python.exe`)
- Node.js 24 LTS (`C:\Program Files\nodejs`)

## ETL

```powershell
cd ClimAppWeb\etl
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python scripts\build_catalog.py          # regenera data/catalog desde data/sources
.venv\Scripts\python scripts\build_catalog.py --refresh  # vuelve a descargar las fuentes
```

### Catálogo geográfico (`etl/data/catalog/`)

- `comunas.csv` — 346 comunas (lista oficial SUBDERE) con nombre, alias, región y coordenadas de la cabecera comunal.
- `estaciones_armada.csv` — estaciones de la Armada (red EMA y capitanías de puerto) con su comuna más cercana.

Fuentes y licencias:
- Códigos territoriales SUBDERE vía [chilemapas](https://github.com/pachadotdev/chilemapas) (Apache-2.0).
- Coordenadas y nombres: [Wikidata](https://www.wikidata.org) (CC0); respaldo con [Open-Meteo Geocoding](https://open-meteo.com) (CC BY 4.0).
- Estaciones: API pública del mapa de estaciones de la Armada de Chile (`serviciosonline.directemar.cl/meteomapa`).

Correcciones manuales a coordenadas: ver `COMUNA_OVERRIDES` y `STATION_OVERRIDES` en `etl/scripts/build_catalog.py`.

### Muestras de prueba (`etl/tests/fixtures/`)

Respuestas reales capturadas el 2026-10-01 durante los spikes, para pruebas sin red.
