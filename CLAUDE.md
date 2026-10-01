# CLAUDE.md — ClimApp

Contexto del proyecto, bitácora de cambios y pendientes. **Este archivo debe actualizarse en cada sesión de trabajo**: registrar qué se modificó (sección *Bitácora de cambios*) y qué queda por hacer (sección *Pendientes*).

---

## 1. Descripción del proyecto

**ClimApp — Plataforma Climática Inteligente para Chile (Ensemble AI Weather Platform).**

Plataforma web que recolecta, procesa y cruza datos meteorológicos de:
- **Modelos globales**: GFS, ECMWF, ICON (vía Open-Meteo, NOAA/GFS, ECMWF Open Data).
- **Red oficial de la Armada de Chile** (Directemar / Servimet): estaciones costeras, boyas, avisos de marejadas, boletines marinos.

Con esos datos genera un **pronóstico unificado** mediante un algoritmo de consenso (ensemble) con corrección de sesgo según la geografía chilena, y usa un **LLM** para redactar boletines climáticos y marítimo-costeros en español.

Fuente de requisitos: [ReqClimApp.docx](ReqClimApp.docx) (SRS v2.0, 18-ago-2026).

> La monetización está **fuera de alcance** hasta que la plataforma esté desplegada y con tráfico. El foco actual es factibilidad técnica, calidad del pronóstico y costo operacional mínimo.

## 2. Arquitectura objetivo

Servicios livianos / serverless, desacoplados en capas:

1. **Fuentes** — APIs de modelos globales + red Armada de Chile.
2. **Ingesta (ETL)** — normalización, GeoJSON, conversión de unidades, almacenamiento en BD/caché.
3. **Motor de IA** — ensemble ponderado por zona geográfica + LLM para boletines.
4. **API REST**.
5. **Frontend** — Next.js + Tailwind: visualización, mapas interactivos, resúmenes en lenguaje natural.

### Stack propuesto (prioriza free tiers)

| Capa | Tecnología |
|---|---|
| Frontend / hosting | Next.js en Vercel o Netlify |
| Backend / ETL | Node.js o Python (FastAPI) en Render o Cloudflare Workers |
| Base de datos | Supabase (PostgreSQL) |
| Caché / cron | Upstash Redis |
| LLM | Gemini Flash o GPT-4o-mini (definir) |

Costo objetivo MVP: ~1,5–10 USD/mes.

## 3. Requisitos clave

**Funcionales**
- **RF01** Ingesta multifuente: APIs de modelos globales (RF01.1) + scraping/API Armada de Chile (RF01.2).
- **RF02** Estandarización: unidades (°C, hPa, mm, km/h o nudos, oleaje) (RF02.1); indexación espacial por comuna, microclima y sector costero (RF02.2).
- **RF03** Ensemble: corrección de sesgo vs. observaciones reales (RF03.1); re-evaluación continua de pesos (RF03.2).
- **RF04** Boletín en lenguaje natural vía LLM.
- **RF05** Frontend: búsqueda por comuna/ciudad/puerto (RF05.1); panel a 7 días con temperatura, precipitación, viento, humedad y alertas marítimas (RF05.2); vista de "Fiabilidad del Pronóstico" (dispersión entre fuentes) (RF05.3); mapa de capas de viento, lluvia y variables costeras (RF05.4).

**No funcionales**
- **RNF01** API < 300 ms para datos en caché.
- **RNF02** 99,5 % uptime del frontend.
- **RNF03** Escalar ante picos (eventos meteorológicos / marejadas) vía serverless o CDN.
- **RNF04** Minimizar transferencias de BD; invocar el LLM solo desde tareas programadas (cron), nunca por request de usuario.

## 4. Hoja de ruta

| Fase | Semanas | Alcance |
|---|---|---|
| 1 — MVP & ingesta Armada | 1–4 | BD + ETL, ingesta Open-Meteo + Armada, UI básica de pronóstico |
| 2 — Algoritmo & IA | 5–8 | Ensemble ponderado, integración LLM (boletín), validación con datos Armada |
| 3 — Consolidación & negocio | 9–12 | Mapas interactivos, ajuste de rendimiento / pruebas de carga, definición de monetización |

## 5. Convenciones de trabajo

- Idioma de documentación y comunicación: **español**.
- **Todo el código fuente va dentro de [ClimAppWeb/](ClimAppWeb/)** (`etl/`, `db/`, `web/`). La documentación del proyecto queda en [docs/](docs/) y este archivo en la raíz.
- Control de versiones con git. El trabajo se hace en **ramas**, no directamente en `main`.
- Herramientas locales: Python 3.12 en `%LOCALAPPDATA%\Programs\Python\Python312\` (venv en `ClimAppWeb/etl/.venv`), Node.js 24 LTS en `C:\Program Files\nodejs\`. Pueden no estar en el PATH de la terminal: usar rutas completas.
- Ejecutar Python con `PYTHONIOENCODING=utf-8` (la consola de Windows rompe las tildes).
- Al terminar cada sesión o cambio relevante:
  1. Agregar una entrada en **Bitácora de cambios** (fecha, rama, qué se hizo).
  2. Actualizar **Pendientes** (marcar lo completado, agregar lo nuevo).
  3. Hacer commit en la rama de trabajo.

## 6. Estado actual

- Stack **aprobado** (2026-10-01): ETL en Python, API como Route Handlers de Next.js en Vercel leyendo Redis, cron en GitHub Actions, monorepo en `ClimAppWeb/`.
- Fase 1, semana 1 casi completa: spikes ([docs/spikes-semana1.md](docs/spikes-semana1.md)), catálogo geográfico, esquema de BD v1 y semilla SQL. Falta crear Supabase.
- Repositorio: https://github.com/marcoantoniovale/ClimApp (privado). `gh` instalado en `C:\Program Files\GitHub CLI\`.
- Diseño de la Fase 1: [docs/fase1-mapeo-requisitos.md](docs/fase1-mapeo-requisitos.md).
- Referencia visual del frontend: [Template/](Template/) (aportada por el usuario) con ajustes en [docs/frontend-template-analisis.md](docs/frontend-template-analisis.md). Paleta: fondo `#0F172A`, turquesa `#0EA5E9`, naranja `#F97316`.

---

## 7. Bitácora de cambios

### 2026-10-01 — rama `docs/claude-md-contexto`
- Inicializado repositorio git (`main` con el SRS como commit inicial).
- Creado `CLAUDE.md` con contexto del proyecto (resumen del SRS v2.0), arquitectura, requisitos, hoja de ruta, convenciones, bitácora y pendientes.
- Agregado `.gitignore` base.
- Intento de crear repositorio remoto: no realizado por falta de `gh` y credenciales; queda en Pendientes con los pasos.

### 2026-10-01 — rama `docs/fase1-mapeo-requisitos`
- Creado [docs/fase1-mapeo-requisitos.md](docs/fase1-mapeo-requisitos.md): qué requisitos entran en la Fase 1, riesgos y vacíos del SRS, arquitectura propuesta, esquema de BD, unidades canónicas, conectores, API, frontend, plan de 4 semanas y decisiones por aprobar.
- Hallazgos clave: la Fase 1 debe archivar pronósticos y observaciones desde el día 1 para que exista el ensemble de la Fase 2; el volumen de pronósticos excede la capa gratuita de Supabase si se archiva todo; la fuente Armada probablemente requiera scraping (sin API confirmada).

### 2026-10-01 — rama `feature/semana1-bases`
- Stack aprobado por el usuario. Código fuente en `ClimAppWeb/` (instrucción del usuario).
- Instalados Python 3.12.10 y Node.js 24.19.0 con winget.
- Spikes en [docs/spikes-semana1.md](docs/spikes-semana1.md): Open-Meteo confirmado; **observaciones Armada disponibles como API JSON** (`serviciosonline.directemar.cl/meteomapa/api/meteo`); avisos solo como imagen/PDF escaneado; boyas son del SHOA. Muestras reales en `ClimAppWeb/etl/tests/fixtures/`.
- Estructura `ClimAppWeb/{etl,db,web}` y proyecto Python `climapp-etl` (`pyproject.toml`, venv local).
- Catálogo: [build_catalog.py](ClimAppWeb/etl/scripts/build_catalog.py) genera `comunas.csv` (346 comunas, CUT oficial, coordenadas Wikidata/Open-Meteo) y `estaciones_armada.csv` (100 estaciones). Fuentes guardadas en `etl/data/sources/` para regenerar sin red. Correcciones manuales: comuna Antártica y la EMA Paso Timbales.
- Esquema de BD v1: [db/migrations/0001_init.sql](ClimAppWeb/db/migrations/0001_init.sql). Semilla generada por [export_seed.py](ClimAppWeb/etl/scripts/export_seed.py) en `db/seeds/0001_catalogo.sql`. Sintaxis validada con el parser de PostgreSQL (pglast); falta probarla en una base real.
- Pruebas de integridad del catálogo: 9/9 OK (`pytest`).
- Actualizado [docs/fase1-mapeo-requisitos.md](docs/fase1-mapeo-requisitos.md) con los resultados de los spikes.

### 2026-10-01 — rama `docs/frontend-template`
- Revisada la carpeta `Template/` aportada por el usuario (propuesta de frontend Gemini, logo e ícono SVG, script de PNG). Se incorpora al repositorio sin cambios como referencia.
- Creado [docs/frontend-template-analisis.md](docs/frontend-template-analisis.md): qué se adopta (paleta, logo, componentes, PWA, mobile-first) y 13 ajustes (ubicación en `ClimAppWeb/web`, rutas por ubicación, Server Components, variables faltantes, Tailwind v4, íconos maskable, SVG como fuente única, etc.).
- Nuevas variables para el ETL: estado del cielo, sensación térmica, índice UV. Agregadas como columnas a `forecast_current` en [0001_init.sql](ClimAppWeb/db/migrations/0001_init.sql) (migración aún no aplicada en ninguna base).

### 2026-10-01 — rama `feature/supabase-setup`
- Aplicador de migraciones [migrate.py](ClimAppWeb/etl/scripts/migrate.py): aplica `db/migrations/*.sql` pendientes (registro en `schema_migrations`) y con `--seed` las semillas idempotentes. Lee `DATABASE_URL` del entorno o de `ClimAppWeb/.env` (ignorado por git; plantilla en `.env.example`).
- Quitados `begin;`/`commit;` de los SQL: las transacciones las maneja el aplicador.
- [0002_rls.sql](ClimAppWeb/db/migrations/0002_rls.sql): RLS activado sin políticas en todas las tablas, para que la API REST pública de Supabase no exponga datos.
- Dependencia `psycopg[binary]` agregada al ETL.
- Conexión: usar el **Session pooler** de Supabase (IPv4); la conexión directa es solo IPv6.
- Instalado GitHub CLI 2.102.0; sesión `marcoantoniovale` (permisos `repo`, `workflow`). Creado el repositorio privado [marcoantoniovale/ClimApp](https://github.com/marcoantoniovale/ClimApp) y subidas todas las ramas. Revisado el historial antes de subir: sin secretos.

---

## 8. Pendientes

### Decisiones por tomar
Propuestas en [docs/fase1-mapeo-requisitos.md §6](docs/fase1-mapeo-requisitos.md).
- [x] Backend: ETL en Python; API como Route Handlers de Next.js leyendo Redis. (Aprobado 2026-10-01)
- [x] Cron: GitHub Actions programado (depende del repo remoto). (Aprobado 2026-10-01)
- [x] Estructura: monorepo en `ClimAppWeb/` (`web/`, `etl/`, `db/`); docs en `docs/`. (Aprobado 2026-10-01)
- [ ] Proveedor LLM: Gemini Flash vs. GPT-4o-mini (u otro). No bloquea la Fase 1.
- [ ] Retención del archivo histórico de pronósticos (propuesta: 12 meses, 3-horario).
- [ ] Pronóstico provisional de la Fase 1 = promedio simple de GFS/ECMWF/ICON.
- [ ] ¿Incluir la vista de dispersión entre modelos (RF05.3) en la Fase 1?
- [x] Repositorio remoto: https://github.com/marcoantoniovale/ClimApp (privado). (2026-10-01)
- [ ] Política de ramas/merge. Hoy las ramas están encadenadas (cada una sale de la anterior) y `main` solo tiene el SRS. Propuesta: fusionar a `main` con pull requests.
- [ ] Vincular el repo al proyecto de claude.ai "ClimApp" (https://claude.ai/project/01a0f79e-6e15-723a-a00e-5c252c791837) desde *Agregar contenido → GitHub* (usuario; resincronizar tras cada push).

### Investigación
- [x] Datos de la Armada: observaciones por API JSON; avisos imagen/PDF. Ver [docs/spikes-semana1.md](docs/spikes-semana1.md).
- [x] Boyas: son del SHOA → fuera de la Fase 1.
- [x] Open-Meteo: límites, modelos, API marina, licencia (no comercial, CC BY 4.0).
- [ ] Confirmar condiciones de capas gratuitas: Vercel Hobby (uso no comercial, cron), Supabase Free (500 MB, pausa por inactividad), Upstash, GitHub Actions.
- [ ] Armada: unidad del viento en capitanías (no declarada; ¿nudos?) y zona horaria de `fecha`.
- [ ] Armada: endpoint `/top` y pronósticos por zona (insumo del boletín, Fase 2).
- [ ] Open-Meteo: revisar comunas costeras cuyo punto de grilla cae en el mar.

### Fase 1 (MVP) — detalle y plan semanal en [docs/fase1-mapeo-requisitos.md §5](docs/fase1-mapeo-requisitos.md)
- [ ] Semana 1: spikes ✅, estructura del monorepo ✅, catálogo geográfico ✅, esquema de BD v1 ✅. **Falta:** crear proyecto Supabase (usuario) → poner `DATABASE_URL` en `ClimAppWeb/.env` → `python scripts/migrate.py --seed`. Repositorio remoto ✅.
- [ ] Catálogo, pendientes: marcar comunas costeras (`es_costera`); catálogo de puertos/sectores costeros y mapeo de zonas de avisos → comunas (semana 3); exportar JSON para el buscador (semana 4).
- [ ] Semana 2: conector Open-Meteo, unidades canónicas con pruebas, tablas `forecast_current` / `forecast_archive`, cron, `ingestion_runs`. Considerar adelantar el conector de observaciones Armada (API JSON). Incluir `weather_code`, `apparent_temperature` y `uv_index` (requeridos por la plantilla de frontend).
- [ ] Semana 3: conector Armada (avisos + observaciones si no se adelantó), precálculo a Redis, endpoints de API.
- [ ] Semana 4: buscador, panel 7 días, avisos marítimos, despliegue en Vercel, alertas de fallas de ingesta. Incluir atribución CC BY 4.0 a Open-Meteo. Implementar sobre la plantilla `Template/` con los 13 ajustes de [docs/frontend-template-analisis.md](docs/frontend-template-analisis.md) (Server Components, Tailwind v4, íconos PWA desde SVG con `sharp`, sin `radar/` hasta Fase 3).
