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
- VS Code (`.vscode/settings.json`, local, no versionado): inyecta `ClimAppWeb/.env` en las terminales (`python.terminal.useEnvFile`, `python.envFile`), usa el venv del ETL como intérprete y habilita pytest. Los scripts igual leen `ClimAppWeb/.env` por su cuenta.
- Al terminar cada sesión o cambio relevante:
  1. Agregar una entrada en **Bitácora de cambios** (fecha, rama, qué se hizo).
  2. Actualizar **Pendientes** (marcar lo completado, agregar lo nuevo).
  3. Hacer commit en la rama de trabajo.

## 6. Estado actual

- Stack **aprobado** (2026-10-01): ETL en Python, API como Route Handlers de Next.js en Vercel leyendo Redis, cron en GitHub Actions, monorepo en `ClimAppWeb/`.
- Fase 1, **semana 1 completa**: spikes ([docs/spikes-semana1.md](docs/spikes-semana1.md)), catálogo geográfico, esquema de BD v1 aplicado en Supabase con el catálogo cargado (346 comunas, 100 estaciones).
- **Semana 2**: ETL funcionando contra Supabase (pronóstico de 346 comunas × 3 modelos, archivo en 48 estaciones, retención). Cron horario en GitHub Actions ([.github/workflows/ingesta.yml](.github/workflows/ingesta.yml)) activo desde `main`. **Las observaciones de la Armada no se recolectan automáticamente**: su API bloquea las IP de nube (pendiente).
- **Semana 3 completa**: avisos de la Armada, comunas costeras (106), oleaje, precálculo de JSON por comuna publicado en Upstash Redis y API en Next.js 16 (`ClimAppWeb/web`), p95 140 ms.
- **Producción: https://climapp-chile.vercel.app** (Vercel, equipo `mlam`, proyecto `clim-app`, Root Directory `ClimAppWeb/web`, región `gru1`). Cada fusión a `main` se publica sola; los PR tienen dirección de prueba privada (protección de despliegues activa). Interfaz de la semana 4 en la rama `feature/semana4-frontend` (se publica al fusionar).
- Redis: Upstash `bold-garfish-225379` (São Paulo). Credenciales en `ClimAppWeb/.env` (ETL) y `ClimAppWeb/web/.env.local` (API), no versionados; en GitHub como secretos.
- Ramas: `main` es la rama estable; el trabajo nuevo sale de `main` en ramas `feature/…` o `docs/…` y entra por pull request.
- El flujo de GitHub Actions vive en `.github/` en la raíz (requisito de GitHub), aunque ejecuta código de `ClimAppWeb/`.
- Base de datos: Supabase, proyecto `drtgaltvmwbqffbsjaiw`, región São Paulo, PostgreSQL 17. Conexión por Session pooler en `ClimAppWeb/.env` (no versionado).
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
- Supabase conectado: `migrate.py --seed` aplicó 0001_init y 0002_rls y cargó el catálogo (346 comunas, 16 regiones, 100 estaciones, todas con comuna). Verificado: RLS activo en 10/10 tablas (incluida `schema_migrations`), re-ejecución idempotente, base de 11 MB.

### 2026-10-01 — rama `feature/semana2-ingesta`
- Verificaciones previas: los 3 modelos entregan las 11 variables salvo `uv_index` (solo GFS). Armada: viento de capitanías en nudos, horas en hora de Chile, campo `time` de las EMA erróneo (ver [docs/spikes-semana1.md](docs/spikes-semana1.md)).
- Paquete `climapp_etl`: `db.py` (conexión, `ingestion_runs`), `units.py`, `http.py` (reintentos), `open_meteo.py` (lotes de 50, cuota 500/min), `armada.py`, `jobs.py`, CLI `python -m climapp_etl {auto,observaciones,pronostico,archivo,mantencion}`. `migrate.py` usa la conexión del paquete. Dependencia nueva: `tzdata`.
- Prueba real en Supabase: `forecast_current` 174.384 filas (346 × 3 × 168) en 2 min 13 s; `forecast_archive` 3.456 filas (48 estaciones × 3 modelos × 24 horas); observaciones 40 estaciones vigentes de 45. Sin nulos salvo UV en ECMWF/ICON.
- Corregido: el archivo pedía 3 días y solo cubría 52 h; ahora 4 días.
- [0003_retencion.sql](ClimAppWeb/db/migrations/0003_retencion.sql) y job `mantencion`: retención provisional (ver Pendientes). Base actual: 39 MB.
- [.github/workflows/ingesta.yml](.github/workflows/ingesta.yml): `auto` cada hora (minuto 17); decide qué corre según la última corrida exitosa. Secreto `DATABASE_URL` cargado en el repositorio.
- Pruebas: 28/28 OK.
- **API de observaciones de la Armada bloqueada desde la nube**: `serviciosonline.directemar.cl` no acepta conexiones desde GitHub Actions (Azure, EE.UU.) ni desde Supabase (AWS São Paulo, probado con `pg_net` y luego desinstalado). `meteoarmada.directemar.cl` y Open-Meteo sí responden. El cron corre `auto --sin-observaciones`; agregada opción `--log` (para `pythonw`).
- Decisiones del usuario: retención aprobada; fusionar a `main` por pull request; recolección de observaciones queda pendiente.

### 2026-10-01 — rama `feature/semana3-avisos-api`
- **Comunas costeras**: [build_coast.py](ClimAppWeb/etl/scripts/build_coast.py) mide la distancia de cada polígono comunal (chilemapas) a la costa de Natural Earth; costera si ≤ 1,5 km → 106 comunas, 28/28 casos de control correctos. La API marina de Open-Meteo no servía para esto (Quilpué cae en la misma celda que Valparaíso). Descargas en `etl/data/cache/` (no versionado).
- **Avisos** ([avisos.py](ClimAppWeb/etl/src/climapp_etl/avisos.py)): lee las tarjetas de la portada de meteoarmada (zona, tipo, fecha en hora de Chile, enlace) y el PDF/imagen del detalle. Asigna comunas: tramo "A a B" por latitud entre ambos extremos; lugar único → comuna costera más cercana; región → sus comunas costeras. Nomenclátor `LANDMARKS` + nombres de comunas. Las 12 zonas vigentes se resuelven. Cierra los avisos que desaparecen de la portada (`vigente_hasta`).
- **Migración 0004**: tabla `forecast_marine` (oleaje sale de `forecast_current`) y `location_snapshots`.
- **Oleaje**: `fetch_marine` en el conector Open-Meteo; 13.608 filas para 106 costeras.
- **Precálculo** ([snapshot.py](ClimAppWeb/etl/src/climapp_etl/snapshot.py)): JSON por comuna (~16 KB) con 48 h y 7 días (promedio de modelos + rango, día en hora de Chile, estado del cielo de consenso), oleaje y última observación cercana. Pronóstico pedido con `past_days=1` para que "hoy" esté completo.
- **Redis** ([redis.py](ClimAppWeb/etl/src/climapp_etl/redis.py)): publicación por la API REST de Upstash; claves `climapp:v1:{loc:<slug>, avisos, indice, meta}`. Sin credenciales no publica (queda en `location_snapshots`).
- `auto` ahora: pronóstico (6 h), archivo (12 h), avisos (cada hora), precálculo (tras cada pronóstico), mantención (24 h).
- Robustez: `get_json` reintenta respuestas vacías/no JSON (Open-Meteo devolvió un 200 vacío).
- **Web** (`ClimAppWeb/web`): Next.js 16.3.8 + Tailwind v4 creado con create-next-app. API de solo lectura sobre Redis con `Cache-Control: s-maxage` (ver [web/README.md](ClimAppWeb/web/README.md)). Compila y pasa lint. Next.js 16 incluye `AGENTS.md`: leer `node_modules/next/dist/docs/` antes de escribir código.
- Pruebas ETL: 41/41. Base: 66 MB.
- Upstash conectado (credenciales del usuario): 349 claves publicadas (346 comunas + avisos, índice, meta; JSON de ~16 KB). Secretos `UPSTASH_REDIS_REST_URL` y `UPSTASH_REDIS_REST_TOKEN` en GitHub; corrida de `avisos` desde Actions publicó en Redis.
- `ClimAppWeb/web/vercel.json`: funciones en la región `gru1` (São Paulo), junto a Upstash y Supabase.

### 2026-10-01 — rama `feature/semana4-frontend`
- Leídas las guías de Next.js 16 en `node_modules/next/dist/docs/` (Route Handlers, caché sin Cache Components, ISR, `generateStaticParams`, metadata, viewport, manifest, íconos), como exige `web/AGENTS.md`.
- Páginas: `/` (buscador, avisos vigentes, ciudades), `/comuna/[slug]` (ISR: se genera en la primera visita y se renueva cada 10 min), `/avisos`, 404 y error. Lectura de Redis con `force-cache` + `revalidate` en páginas; la API sigue sin caché de servidor.
- Componentes (`web/src/components/`): `Search` (combobox accesible, sin tildes, alias SUBDERE), `WeatherIcon` (estilo del logo, códigos WMO), `CurrentWeather`, `HourlyForecast` (48 h, curva de temperatura y barras de prob. de lluvia en bandas separadas, detalle de la hora seleccionada con mouse/toque/teclado), `ClimateMetrics`, `WeeklyForecast` (barras mín.–máx. en escala común y rango entre modelos = fiabilidad), `MarineForecast`, `WarningList`, `Header`, `BottomNav`, `Footer` (atribución CC BY 4.0).
- Colores de gráficos validados con el validador de la guía de visualización: `#EA580C` (temperatura) y `#0284C7` (lluvia/oleaje) pasan banda de luminosidad, daltonismo y contraste sobre `#1E293B`; los de marca (`#F97316`, `#0EA5E9`) quedan para acentos.
- PWA: `app/manifest.ts`; íconos generados desde el SVG con `npm run icons` (`scripts/generate-icons.mjs`, `sharp`): 192/512, maskable a sangre completa y `apple-icon.png`.
- Correcciones tras revisar capturas (Chrome headless): horas pasadas se descartan al mostrar (el JSON se regenera cada 6 h); regiones con tildes y "Región de …"; conectores en minúscula en zonas de aviso; sin barras de lluvia bajo 5 %; contraste de botones (sky-700).
- Lint y build sin errores.

### 2026-10-01 — Vercel (PR #3 y rama `docs/vercel-produccion`)
- Proyecto importado por el usuario; la dirección asignada exigía inicio de sesión (protección de despliegues) y `clim-app.vercel.app` no estaba disponible → dominio de producción `climapp-chile.vercel.app`.
- API en producción: todos los endpoints OK desde Chile, CDN y funciones en `gru1`. 100 comunas al azar, tiempo de servidor sin TLS: sin caché p50 91 ms / **p95 117 ms**; con caché de CDN p50 70 ms / **p95 93 ms**. Primera llamada tras un despliegue ~1 s (arranque en frío).
- API probada en local (`next start`): todos los endpoints OK, 404 para slugs inexistentes o inválidos; 200 peticiones a comunas al azar sin CDN: p50 72 ms, **p95 140 ms**, máx. 228 ms.

---

## 8. Pendientes

### Decisiones por tomar
Propuestas en [docs/fase1-mapeo-requisitos.md §6](docs/fase1-mapeo-requisitos.md).
- [x] Backend: ETL en Python; API como Route Handlers de Next.js leyendo Redis. (Aprobado 2026-10-01)
- [x] Cron: GitHub Actions programado (depende del repo remoto). (Aprobado 2026-10-01)
- [x] Estructura: monorepo en `ClimAppWeb/` (`web/`, `etl/`, `db/`); docs en `docs/`. (Aprobado 2026-10-01)
- [ ] Proveedor LLM: Gemini Flash vs. GPT-4o-mini (u otro). No bloquea la Fase 1.
- [x] Retención (aprobada 2026-10-01): archivo de pronósticos 90 días, observaciones 1 año (JSON original 14 días), corridas 90 días → ~210 MB estables. En `RETENTION` de [jobs.py](ClimAppWeb/etl/src/climapp_etl/jobs.py). 12 meses de archivo no cabía en 500 MB.
- [ ] **Recolección de observaciones de la Armada** (decidir): la API solo responde desde Chile. Opciones: (a) tarea programada de Windows en el PC del usuario (`pythonw -m climapp_etl observaciones --log …`), gratis pero con huecos si el PC está apagado; (b) VM gratuita de Oracle Cloud en la región Santiago (requiere cuenta; no garantizado que no esté bloqueada); (c) ambas. Sin esto, `forecast_archive` se llena pero no hay observaciones contra qué compararlo (bloquea la Fase 2).
- [ ] Pronóstico provisional de la Fase 1 = promedio simple de GFS/ECMWF/ICON.
- [ ] ¿Incluir la vista de dispersión entre modelos (RF05.3) en la Fase 1?
- [x] Repositorio remoto: https://github.com/marcoantoniovale/ClimApp (privado). (2026-10-01)
- [x] Política de ramas: trabajo en ramas desde `main` y fusión por pull request. (Aprobado 2026-10-01)
- [ ] Vincular el repo al proyecto de claude.ai "ClimApp" (https://claude.ai/project/01a0f79e-6e15-723a-a00e-5c252c791837) desde *Agregar contenido → GitHub* (usuario; resincronizar tras cada push).

### Investigación
- [x] Datos de la Armada: observaciones por API JSON; avisos imagen/PDF. Ver [docs/spikes-semana1.md](docs/spikes-semana1.md).
- [x] Boyas: son del SHOA → fuera de la Fase 1.
- [x] Open-Meteo: límites, modelos, API marina, licencia (no comercial, CC BY 4.0).
- [ ] Confirmar condiciones de capas gratuitas: Vercel Hobby (uso no comercial, cron), Supabase Free (500 MB, pausa por inactividad), Upstash, GitHub Actions.
- [x] Armada: viento de capitanías en **nudos** (razón 1,87 vs. Open-Meteo); `fecha` en hora de Chile; en EMA usar `timeLocal` (`time` viene mal en la fuente). (2026-10-01)
- [ ] Armada: endpoint `/top` y pronósticos por zona (insumo del boletín, Fase 2).
- [ ] Open-Meteo: revisar comunas costeras cuyo punto de grilla cae en el mar.
- [ ] Avisos: en Magallanes/Aysén los tramos por latitud incluyen comunas del otro lado (p. ej. "Faro San Pedro a Faro Evangelistas" incluye San Gregorio). Mejorar con filtro por longitud o polígonos de zona.
- [ ] Avisos: ampliar `LANDMARKS` en [avisos.py](ClimAppWeb/etl/src/climapp_etl/avisos.py) cuando una corrida de `armada_avisos` informe zonas sin resolver.

### Fase 1 (MVP) — detalle y plan semanal en [docs/fase1-mapeo-requisitos.md §5](docs/fase1-mapeo-requisitos.md)
- [x] Semana 1: spikes, estructura del monorepo, catálogo geográfico, esquema de BD v1 aplicado en Supabase, repositorio remoto. (2026-10-01)
- [ ] Seguridad: cambiar la contraseña de la base de datos de Supabase y rotar el token de Upstash (ambos se compartieron en el chat); actualizar `ClimAppWeb/.env`, `web/.env.local` y los secretos de GitHub.
- [x] Comunas costeras marcadas (106) con geometría; zonas de avisos → comunas con nomenclátor. (2026-10-01)
- [ ] Catálogo de puertos/sectores costeros como ubicaciones propias (`tipo = 'puerto'`), con viento en nudos. Por ahora solo comunas.
- [x] Semana 2 (código): conector Open-Meteo (11 variables, 3 modelos), unidades canónicas con pruebas, `forecast_current` / `forecast_archive`, conector de observaciones Armada (adelantado de la semana 3), `ingestion_runs`, retención, flujo de GitHub Actions. (2026-10-01)
- [ ] Semana 2 (cierre): verificar 3 días seguidos de corridas automáticas del cron (criterio de cierre; revisar `ingestion_runs` o la pestaña Actions). Fusionado a `main` el 2026-10-01.
- [x] Oleaje (API marina de Open-Meteo) para las 106 comunas costeras en `forecast_marine`. (2026-10-01)
- [x] Semana 3 (código): avisos Armada, precálculo (`location_snapshots`), publicación en Redis, API (`/api/forecast/:slug`, `/api/warnings[/:slug]`, `/api/locations`, `/api/health`). (2026-10-01)
- [x] Semana 3 (cierre): Upstash conectado, secretos en GitHub, API probada (p95 140 ms < 300 ms). (2026-10-01)
- [ ] Antes de publicar en Vercel (semana 4): usar el **token de solo lectura** de Upstash en la web (hoy `web/.env.local` usa el token completo, provisorio).
- [x] Vercel: proyecto importado, dominio público `climapp-chile.vercel.app` (`clim-app.vercel.app` estaba ocupado), API verificada en producción. (2026-10-01)
- [ ] Confirmar que la variable `UPSTASH_REDIS_REST_READONLY_TOKEN` de Vercel tiene el token de **solo lectura**.
- [x] Semana 4 (interfaz): buscador, página por comuna (actual, 48 h, métricas, 7 días, oleaje, avisos), página de avisos, PWA, atribución. (2026-10-01)
- [ ] Semana 4 (cierre): fusionar y verificar en producción; alertas de fallas de ingesta (hoy: correo de GitHub cuando falla el cron + `/api/health` devuelve 503 si los datos tienen más de 8 h; falta un monitor externo que lo consulte).
- [x] Atribución CC BY 4.0 y ajustes de la plantilla aplicados sobre `Template/` con los 13 ajustes de [docs/frontend-template-analisis.md](docs/frontend-template-analisis.md) (Server Components, Tailwind v4, íconos PWA desde SVG con `sharp`, sin `radar/` hasta Fase 3).
