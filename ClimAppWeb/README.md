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

### Ingesta

```powershell
.venv\Scripts\python -m climapp_etl auto           # lo que corresponda (es lo que corre el cron)
.venv\Scripts\python -m climapp_etl observaciones  # Armada → observations (cada hora)
.venv\Scripts\python -m climapp_etl pronostico     # Open-Meteo, 346 comunas → forecast_current (cada 6 h, ~2 min)
.venv\Scripts\python -m climapp_etl archivo        # Open-Meteo en estaciones → forecast_archive (cada 12 h)
.venv\Scripts\python -m climapp_etl mantencion     # retención de datos (cada 24 h)
.venv\Scripts\python scripts\migrate.py [--seed]   # migraciones de db/migrations
```

Programación: [.github/workflows/ingesta.yml](../.github/workflows/ingesta.yml) ejecuta `auto` cada hora en GitHub Actions (secreto `DATABASE_URL`). Cada corrida queda en la tabla `ingestion_runs`.

| Módulo (`etl/src/climapp_etl/`) | Responsabilidad |
|---|---|
| `open_meteo.py` | Peticiones por lotes de 50 ubicaciones, control de cuota (500 llamadas/min), filas por modelo y hora |
| `armada.py` | Observaciones de capitanías y EMA: hora de Chile → UTC, nudos → m/s |
| `units.py` | Conversiones y rangos plausibles |
| `jobs.py` | Trabajos de ingesta, retención y modo `auto` |
| `db.py` | Conexión y registro de corridas |

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
