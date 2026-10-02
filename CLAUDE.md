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
- **Producción: https://climapp-chile.vercel.app** (Vercel, equipo `mlam`, proyecto `clim-app`, Root Directory `ClimAppWeb/web`, región `gru1`). Cada fusión a `main` se publica sola; los PR tienen dirección de prueba privada (protección de despliegues activa). **Interfaz de la Fase 1 publicada** (PR #5).
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
- Lint y build sin errores. Vercel compiló la vista previa del PR y luego producción sin errores.

### 2026-10-01 — Vercel (PR #3 y rama `docs/vercel-produccion`)
- Proyecto importado por el usuario; la dirección asignada exigía inicio de sesión (protección de despliegues) y `clim-app.vercel.app` no estaba disponible → dominio de producción `climapp-chile.vercel.app`.
- API en producción: todos los endpoints OK desde Chile, CDN y funciones en `gru1`. 100 comunas al azar, tiempo de servidor sin TLS: sin caché p50 91 ms / **p95 117 ms**; con caché de CDN p50 70 ms / **p95 93 ms**. Primera llamada tras un despliegue ~1 s (arranque en frío).
- API probada en local (`next start`): todos los endpoints OK, 404 para slugs inexistentes o inválidos; 200 peticiones a comunas al azar sin CDN: p50 72 ms, **p95 140 ms**, máx. 228 ms.

### 2026-10-01 — rama `feature/geolocalizacion`
- **"Usar mi ubicación"** en el buscador (botón dentro del campo). Privacidad: la posición no sale del dispositivo; el navegador descarga solo los polígonos de hasta 6 comunas cercanas y verifica en cuál cae el punto. Si no cae en ninguno (p. ej. en el mar), usa la cabecera más cercana; a más de 80 km de toda cabecera avisa que está fuera de Chile. Mensajes para permiso denegado, tiempo agotado y ubicación no disponible.
- Por qué polígonos: con solo la cabecera más cercana, el Costanera Center (Providencia) caía en Vitacura. Con polígonos, 13/13 casos correctos.
- ETL: el índice `climapp:v1:indice` incluye `lat`/`lon` de la cabecera (publicado; 48 KB). Nuevo [export_geo.py](ClimAppWeb/etl/scripts/export_geo.py): polígonos simplificados (~55 m; más gruesos si pasan de 60 KB, solo archipiélagos del sur) en `web/public/geo/<slug>.json` (345 archivos, 3,0 MB; Antártica no tiene polígono).
- Web: [geo.ts](ClimAppWeb/web/src/lib/geo.ts) (distancia, punto en polígono con huecos, `comunaEnPosicion`). Pruebas con `node --test` (`npm test`, 9/9) usando el catálogo y los polígonos del repo; `tests/` excluido del `tsconfig`.
- **Firma en el pie**: "Creador: Grupo MSinS" con logo pequeño (24 px). A pedido del usuario se modernizó el logo: [msins-mark.svg](ClimAppWeb/web/public/brand/msins-mark.svg) es una versión compacta (solo los lentes, sin texto, que a ese tamaño era ilegible y dependía de fuentes no disponibles). El original sigue en `Template/MSinS.svg`.

### 2026-10-01 — rama `feature/actualizacion-por-corrida`
- Diagnóstico (usuario veía datos de más de 1 h): **el cron de GitHub Actions no ejecutó ninguna corrida programada** desde que llegó a `main` (20:32 UTC); solo hubo corridas por push o manuales. Además, la corrida ICON 18Z ya estaba disponible y no se había descargado.
- **Actualización por corrida**: `open_meteo.latest_runs()` lee `https://api.open-meteo.com/data/<modelo>/static/meta.json` (inicio y disponibilidad de la última corrida). `auto` revisa cada hora y descarga **solo los modelos con corrida nueva** (o con más de 9 h sin renovar); respaldo por tiempo (6 h) si los metadatos fallan. Tabla `model_runs` (migración 0005). Oleaje como máximo cada 3 h.
- Cuota: ~380 llamadas por modelo (antes ~1.150 por los tres juntos); con ~12 corridas al día ≈ 4.600 llamadas/día.
- La web muestra la hora de corrida de cada modelo; "actualizado" = descarga más reciente.
- Prueba real: primera pasada descargó los 3 modelos (incluida ICON 18Z); segunda pasada: "sin corridas nuevas". Pruebas ETL 44/44.
- **Disparador confiable (no aplicado)**: se propuso que Supabase (`pg_cron` + `pg_net`) dispare el flujo de GitHub cada hora con un token fine-grained guardado en el Vault. El sistema de permisos bloqueó crear esa automatización; queda como decisión del usuario.

### 2026-10-01 — rama `feature/disparador-supabase`
- Usuario eligió la opción A y la autorizó. [0006_disparador.sql](ClimAppWeb/db/migrations/0006_disparador.sql): `pg_cron` + `pg_net`; función `ops.disparar_ingesta()` (esquema `ops`, no expuesto por la API REST; `anon` sin permisos) que lee el token del Vault y llama a `POST /repos/marcoantoniovale/ClimApp/actions/workflows/ingesta.yml/dispatches` (`ref=main`, `comando=auto`). Tarea `climapp-ingesta`, `5 * * * *`. Sin token, solo registra una advertencia.
- Activado: el usuario guardó el token en el Vault; `ops.disparar_ingesta()` → GitHub respondió 204 y la corrida `workflow_dispatch` en `main` terminó bien.
- Verificar en Supabase: `select * from cron.job_run_details order by start_time desc limit 5;` y `select status_code, content from net._http_response order by created desc limit 5;` (204 = OK).

### 2026-10-01 — rama `docs/rutaclimapp`
- Propuesta de **RutaClimApp** (pronóstico en ruta cada 15 min para viajeros y transportistas) en [docs/rutaclimapp-propuesta.md](docs/rutaclimapp-propuesta.md): requisito RF06, flujo, arquitectura, contrato de API, etapas (R1 MVP ~2,5–3 semanas), riesgos y decisiones.
- Verificado: Open-Meteo entrega `minutely_15` en Chile (interpolado de modelos horarios) con visibilidad, y horario con isoterma 0 °C y nieve (prueba en Los Libertadores). openrouteservice gratuito: 2.000 rutas/día, 40/min, perfil camión (`driving-hgv`).
- Recomendación: ruteo con openrouteservice; clima desde un **corredor precalculado** (~350 puntos en rutas principales, ~1.700 llamadas/día), sin llamadas a Open-Meteo por consulta de usuario (RNF04).

### 2026-10-01 — rama `docs/precision`
- Reclamo del usuario: Quintero 20 °C en ClimApp vs 16,1 °C en la estación DMC 320056. Evaluación en [docs/precision-evaluacion.md](docs/precision-evaluacion.md).
- Causa principal: Open-Meteo usa por defecto una celda de **tierra** (~15 km tierra adentro en Quintero). Con `cell_selection=nearest` el error del promedio baja de 2,4 a 1,7 °C allí. En 13 estaciones DMC: costa 1,19 → 1,08 °C, interior sin cambio (~0,95 °C). ECMWF IFS 0,25° es el peor en la costa (+3 °C).
- Fuentes DMC encontradas: visor de estaciones automáticas (datos públicos; JSON con registro), `condicionactual.js` (METAR de ~30 aeropuertos) y `pronostico.js` (**pronóstico oficial de 103 localidades, 5 días**, mín/máx y texto por período).

### 2026-10-01 — rama `feature/icon-ubicacion-dias`
- **Cambio de foco (decisión del usuario):** se mantienen los avisos de la Armada; se agregarán alertas de pasos fronterizos; **pronóstico con un único modelo: ICON**. Inicio = el tiempo de la ubicación del usuario; pronóstico hora a hora con selector de día (hoy + 5). Estructura de página inspirada en Meteored, con diseño propio.
- **Por qué ICON** (13 estaciones DMC, 2 días): error medio 0,97 °C (best_match 1,12; ECMWF 1,12; GFS 1,66); publica cada corrida a las 3,5 h (ECMWF 8,2 h). Para ICON la celda por defecto (`land`) es mejor en la costa (0,92 vs 1,01 °C con `nearest`): sin cambio de celda. ICON no entrega UV ni visibilidad → vienen de GFS como complemento.
- ETL: `MODEL_VARIABLES` por modelo (ICON: 14 variables, incluidas punto de rocío, nubosidad, nieve e isoterma 0 °C; GFS: UV y visibilidad), una petición por modelo; migración 0007 (columnas nuevas, ECMWF eliminado). JSON v2: 6 días, horas hasta el fin del sexto día (~124), `fuente`, `cercanas` (6 comunas más cercanas). Prueba real: 132.864 filas en 89 s; Quintero a las 20:00 = 16,1 °C (la estación DMC marcó 16,1 °C a las 19:30). JSON promedio ~49 KB (antes ~16 KB).
- Web: inicio `Inicio` (ubicación automática si ya hay permiso; si no, última comuna guardada en el dispositivo o botón "Ver el tiempo donde estoy"); vista común `Pronostico` (bloque Ahora, avisos, tarjetas de días, hora a hora desplegable con detalle, salida/puesta del sol calculada en el navegador, oleaje, comunas cercanas, fuente del modelo). `lib/ubicacion.ts` compartido con el buscador; `lib/sol.ts` con pruebas (±2 min vs Open-Meteo). Eliminados `CurrentWeather`, `HourlyForecast`, `WeeklyForecast`, `ClimateMetrics`.
- Pruebas: ETL 47/47, web 13/13; lint y build sin errores.

### 2026-10-01 — rama `feature/pasos-fronterizos`
- **Pasos fronterizos**: catálogo [pasos.csv](ClimAppWeb/etl/data/catalog/pasos.csv) con 37 pasos (nombre, región, coordenadas, altura y archivo/variable DMC; nombres de variables DMC irregulares, por eso el mapeo explícito). Futaleufú: la página DMC lo rotula "Río Encuentro" pero coordenadas y variable son de Futaleufú. Monte Aymond: coordenadas y altura aproximadas.
- Migración 0008: `locations.tipo` admite `paso` y columna `altura_m`. Los pasos se pronostican con ICON pasando `elevation` (altura real) a Open-Meteo, en peticiones separadas de las comunas.
- Alertas propias (`snapshot.alertas_paso`): nieve (≥1 cm aviso, ≥10 cm alerta), ventisca (nieve + ráfagas ≥50), viento (60/80 km/h; en altiplano ≥3.500 m: 75/95), frío extremo (≤ −10 °C), precipitación con isoterma bajo el paso. Umbrales iniciales, a calibrar.
- Pronóstico oficial DMC ([dmc_pasos.py](ClimAppWeb/etl/src/climapp_etl/dmc_pasos.py)): 5 días por paso, isoterma, situación y emisión; job `pasos_dmc` cada 3 h → Redis `pasos_dmc`. Los archivos DMC traen nombre e IP del redactor en la primera línea: no se leen ni se guardan (quitados de las muestras de prueba).
- Redis: `pasos` (resumen y alertas de los 37 pasos); el índice del buscador sigue solo con comunas (la ubicación GPS nunca devuelve un paso).
- Web: `/pasos` (por región, de norte a sur, alertas y texto DMC del día) y `/paso/[slug]` (alertas, pronóstico oficial DMC, hora a hora ICON); "Pasos" en la navegación y resumen en el inicio. Estado abierto/cerrado: enlace a la Unidad de Pasos Fronterizos (no publica datos estructurados).
- Prueba real: 37/37 pasos con pronóstico DMC; ICON y DMC coinciden en la tendencia de Los Libertadores (isoterma ~2.500–2.900 m, nieve desde el fin de semana). Pruebas ETL 56/56, web 13/13.
- Pie: "Creador: Marco" (pedido del usuario; antes "Grupo MSinS").

### 2026-10-01 — rama `feature/7dias-correccion`
- **7 días** (hoy + 6) en el JSON y en la web; las tarjetas de días ocupan todo el ancho (7 columnas iguales).
- **Mediciones DMC** ([dmc_obs.py](ClimAppWeb/etl/src/climapp_etl/dmc_obs.py)): mapa nacional `menuTematicoEmas` (148 EMA en una página: coordenadas, hora, temperatura, humedad, viento grados/nudos, presión) cada hora → `stations` (id `dmc-<código>`, red `dmc`) y `observations`. Carga inicial de 48 h con el visor por estación (`dmc_historial`). Bug encontrado y corregido: el visor rotula las series con fecha UTC después de las 21:00 de Chile → fechas por orden de serie (prueba incluida). Migración 0009 (red `dmc`, tabla `station_bias`).
- **Algoritmo ClimApp v1** ([correccion.py](ClimAppWeb/etl/src/climapp_etl/correccion.py), detalle en [docs/precision-evaluacion.md §6](docs/precision-evaluacion.md)): sesgo de ICON por estación y franja del día, atenuado según datos; aplicado a temperatura y sensación de comunas con estaciones de la misma zona a ≤ 25 km. Job `correccion` cada 3 h; el precálculo se rehace si hay corrección nueva. Validación cruzada inicial: 1,20 → 1,17 °C; 209/346 comunas corregidas.
- El bloque "Ahora" muestra la medición DMC cercana (p. ej. "Medido en Quintero, Climatológica a las 21:15").
- Texto de fuente (pedido del usuario): "Modelo ICON (DWD) · obtenida … · actualizado …. Índice UV y visibilidad: GFS. Pronóstico con corrección con mediciones (algoritmo ClimApp)." (se escribió "algoritmo" sin tilde). Sin estaciones cercanas: "Sin estaciones de medición cercanas: pronóstico sin corrección."
- Pie: logo + "Marco (sin S)" (literal pedido por el usuario).
- Pruebas: ETL 64/64, web 13/13.

### 2026-10-01 — rama `chore/actualizacion-minuto-59`
- Pedido del usuario: la actualización se dispara al **minuto 59 de cada hora** (21:59, 22:59…). Migración [0010](ClimAppWeb/db/migrations/0010_disparador_minuto_59.sql) reprograma `climapp-ingesta` a `59 * * * *` (aplicada y verificada en `cron.job`); el cron de respaldo de GitHub también pasa al minuto 59 (si ambos corren, el segundo no descarga nada). Chile tiene desfase entero con UTC, así que el minuto coincide en hora local.
- La corrida tarda ~30 s–2 min; la web toma los datos nuevos en ≤ 10 min (caché ISR/CDN).

### 2026-10-01 — renovación instantánea (PR #18) y tamaño de la base
- **Renovación instantánea**: al terminar una ingesta que publica (precálculo, avisos o pasos), el ETL deja una clave de un solo uso en Redis (`climapp:v1:revalidar`, 5 min) y llama a `POST /api/revalidate`; la web la valida y ejecuta `revalidateTag("climapp", { expire: 0 })` + `revalidatePath("/", "layout")`. Verificado en producción: clave falsa 401, sin cuerpo 400, página `REVALIDATED` ~2 s después del aviso. Caché CDN de la API: 10 → 1 min. Comando manual: `python -m climapp_etl revalidar`.
- **Tamaño de la base** (Supabase Free, 500 MB): 67 MB hoy (13 %). Con 123 estaciones DMC activas y 184 estaciones en el archivo: observaciones +0,63 MB/día, archivo +2,32 MB/día → 330 MB a 90 días (66 %), ~505 MB al año (101 %) con la retención actual (archivo 90 d, observaciones 365 d).

### 2026-10-01 — rama `feature/temperatura-decimal`
- Pedido del usuario: la **temperatura actual** (número grande y medición de la estación cercana) se muestra con **1 decimal** y coma decimal (`grados1`, p. ej. "14,8°"). Máximas, mínimas y horas siguen sin decimales. Prueba en `web/tests/format.test.mts`.

### 2026-10-01 — rama `chore/retencion-180-pie`
- Retención de `observations`: 365 → 180 días (job `mantencion`). Proyección estable ~387 MB (77 %).
- Pie de página: "Pronóstico del modelo ICON (Servicio Meteorológico Alemán, DWD), procesado por el algoritmo ClimApp con mediciones de la Dirección Meteorológica de Chile; índice UV y visibilidad del modelo GFS. …" (se agregó la DMC como fuente de las mediciones).

### 2026-10-01 — rama `feature/buscador-pasos`
- Pedido del usuario: **buscador de pasos fronterizos** en `/pasos` ([ListaPasos.tsx](ClimAppWeb/web/src/components/pasos/ListaPasos.tsx)): filtra por nombre o región sin importar tildes, opción "Solo pasos con alertas" y contador de resultados.

### 2026-10-01 — rama `feature/temperatura-actual-continua`
- Pedido del usuario: la temperatura actual debe seguir la curva del pronóstico, no quedar fija en el valor de la hora. [lib/ahora.ts](ClimAppWeb/web/src/lib/ahora.ts) (algoritmo ClimApp, en el navegador, cada minuto): interpolación lineal del pronóstico horario corregido + ajuste desde la última medición cercana (≤ 3 h) que se desvanece con τ = 3 h. Reloj con `useSyncExternalStore` (en el servidor muestra el valor horario; sin desajuste de hidratación).
- `desdeAhora` conserva hasta 3 `horasPrevias` (no se muestran) para comparar la medición con la curva en su instante.
- Verificado: Quintero 22:15 → 14,5° "desde la última medición" (medido 14,8° a las 21:15; curva 14,8° a las 22:00 y 14,4° a las 23:00). Pruebas web 18/18.

### 2026-10-01 — rama `chore/quitar-nota-fuente`
- Pedido del usuario: se quitó la nota bajo el pronóstico ("Modelo ICON (DWD) · obtenida … · actualizado …. Índice UV y visibilidad: GFS. Pronóstico con corrección…") por redundante con el pie de página. Los datos `fuente`, `corridas` y `correccion` siguen en el JSON.

### 2026-10-01 — rama `feature/ubicacion-guardada`
- Inicio más rápido: muestra al instante la última comuna guardada en el dispositivo (localStorage `climapp:ubicacion`, con `origen` gps/busqueda) sin pedir el GPS. Solo si no hay nada guardado se ubica automáticamente al abrir.
- La comuna elegida en el buscador también se guarda; queda como inicio hasta que se cambie (buscador o botón "Mi ubicación"). Se eliminó `permisoConcedido` (ya no se ubica en cada visita).

### 2026-10-01 — evaluación: búsqueda por localidades (sin cambios de código)
- Pedido del usuario: buscar "Loncura" → Quintero, "Horcón" → Puchuncaví (solo búsqueda, sin datos nuevos). OSM tiene 27.858 lugares con nombre en Chile; asignados a comuna con los polígonos de `public/geo` (27.710; 148 en el mar/frontera). Loncura (suburb) → Quintero, Ritoque → Quintero, Horcón (neighbourhood) → Puchuncaví, Maitencillo/Ventanas (town) → Puchuncaví.
- Tamaño del índice: pueblos 1.093 (9 KB gzip); + sectores 2.620 (21 KB); + caseríos 16.951 (114 KB); + barrios 25.534 (176 KB). Base de datos: ~4–6 MB (≈1 %), o nada si se publica como archivo estático. Problemas: nombres repetidos (~1.500–2.300), Horcón es "barrio" en OSM, licencia ODbL (atribución y misma licencia para el índice). Alternativa oficial: entidades pobladas del Censo 2017 (INE).

### 2026-10-01 — rama `feature/ancla-mediciones`
- Reclamo del usuario: Santiago 18,5° en ClimApp vs 16,6° de la DMC a las 22:30. Causas: (1) la medición solo se asociaba a la comuna donde está la estación (Quinta Normal no es la comuna de Santiago) → Santiago sin medición; (2) el JSON solo se regenera con pronóstico/corrección nuevos, no con cada medición; (3) ICON va 1–2 °C sobre Quinta Normal en la tarde/noche y la corrección por franjas aún tiene pocos datos.
- Medido en 134 estaciones DMC (30 h): el error de ICON persiste (factor 0,95 a 1 h, 0,86 a 3 h, 0,73 a 6 h ≈ τ 20 h). Error a 1 h: 1,84 °C sin medición, 0,83 con τ = 3 h, ~0,7 con τ = 20 h.
- ETL: `correccion.medicion_cercana` (estación más cercana de la misma zona, ≤ 15 km) usada en los JSON; nueva clave Redis `mediciones` ({slug: medición, km}) publicada en cada `dmc_obs` (cada hora) y `dmc_obs` renueva la web. 159 comunas con medición cercana (Santiago → Quinta Normal, 1,6 km).
- Web: `getPronostico` usa la medición más nueva (JSON o `mediciones`); `lib/ahora.ts` τ 3 → 20 h, medición válida hasta 6 h; `ajustarHoras` aplica el mismo ajuste al hora a hora; "Medido en … (a X km)". Pruebas: ETL 68, web 20.

### 2026-10-01 — rama `feature/algoritmo-v2`
- Pedido del usuario: el algoritmo ClimApp es la base de la plataforma; aplicar de una vez el plan de mejoras. Detalle y resultados en [docs/precision-evaluacion.md §7](docs/precision-evaluacion.md).
- Diagnóstico previo: la DMC publica en `estaciones.js` qué estación usa para la temperatura actual de cada sector (Santiago Centro → Quinta Normal, Oriente → Tobalaba, Poniente → Pudahuel), pero no los límites ni las comunas de cada sector.
- **SINCA** como segunda red de mediciones ([sinca.py](ClimAppWeb/etl/src/climapp_etl/sinca.py), [build_sinca.py](ClimAppWeb/etl/scripts/build_sinca.py), catálogo `estaciones_sinca.csv`): 61 estaciones con temperatura (9 en la RM). Hora verificada: inicio de la hora en UTC−4 fijo. Job `sinca_obs` cada hora.
- Migración [0011](ClimAppWeb/db/migrations/0011_algoritmo_v2.sql): red `sinca`, `stations.altura_m`, `locations.elevacion_m`, `station_residuals` (error hora a hora con control de calidad, retención 45 días) y `algoritmo_validacion`.
- [correccion.py](ClimAppWeb/etl/src/climapp_etl/correccion.py) v2: control de calidad (rango, error, salto, pegado, vecinas), sesgo con olvido exponencial (vida media 7 días), interpolación por cuadrantes NE/NO/SE/SO con altura y retorno a ICON con la distancia, ajuste automático de τ, validación dejando cada estación fuera.
- Jobs: `residuos` (cada hora: registro + publica la clave `algoritmo` con la anomalía por comuna) y `correccion` v2 (sesgo desde el registro cada 3 h; validación diaria). Estaciones ubicadas por polígono comunal ([geo.py](ClimAppWeb/etl/src/climapp_etl/geo.py)); alturas con la API de elevación de Open-Meteo. La clave `mediciones` deja de publicarse.
- Web: `getPronostico` agrega `ancla` (anomalía, hora, τ, estaciones); [lib/ahora.ts](ClimAppWeb/web/src/lib/ahora.ts) aplica el ajuste a la temperatura actual, al hora a hora y a máximas y mínimas; API de pronóstico con caché de 60 s; crédito a SINCA en el pie.
- Primera validación (196 estaciones, ~10 mil horas): ICON 1,28 °C → sin estación 1,08 °C y con estación 0,57 °C (1 h después de la medición). τ ajustado = 4 h. Ajuste del momento en 303/346 comunas (antes 159) y sesgo en 304 (antes 209).
- INIA evaluada: 210 estaciones propias; sin servicio de datos público identificado (pendiente).
- Corrección a un diagnóstico anterior: según sus coordenadas, la estación "Quinta Normal" está en la comuna de Estación Central y Torquemada en Concón (estaban bien); los errores reales eran Pudahuel (en Quilicura) y Rodelillo (en Viña del Mar).
- Pruebas: ETL 84, web 20.
- Ajuste posterior (rama `fix/residuo-lectura-reciente`): si llega una lectura más reciente dentro de una hora ya registrada, reemplaza a la anterior (el ancla usaba hasta ~1 h de atraso). Verificado en producción: SINCA responde desde GitHub Actions (61 estaciones, 0 errores).

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

- [x] **Disparador de la ingesta** activo (2026-10-01): token guardado por el usuario en el Vault; prueba manual → GitHub 204 y corrida `workflow_dispatch` exitosa. Desde 2026-10-01 corre al **minuto 59 de cada hora** (migración 0010; p. ej. 21:59); el cron de GitHub, de respaldo, también al 59.
- [ ] **Renovar el token fine-grained `climapp-supabase-cron`** antes de su vencimiento (fecha elegida por el usuario al crearlo); luego `select vault.update_secret(...)` o borrar y volver a crear `github_actions_token`.

- [ ] **RutaClimApp** — **en pausa por decisión del usuario (2026-10-01)**; retomar desde la propuesta (ver [§8 de la propuesta](docs/rutaclimapp-propuesta.md)): aprobación y prioridad frente a la Fase 2; cuenta y API key de openrouteservice; perfil camión en MVP; mapa en R1 o R2; horizonte.

- [x] Precisión: P1 descartado para ICON (la celda por defecto es mejor); P2 y P3 v1 implementados (algoritmo ClimApp). Pendiente: términos de uso de la DMC.

- [x] Alertas de pasos fronterizos (2026-10-01). Pendiente: estado abierto/cerrado estructurado y calibrar umbrales. Detalle original: pronóstico oficial DMC por paso (archivos `datos_pasos_fronterizos_*.js`; ignorar el encabezado con nombre e IP del autor) + alertas propias con ICON en cada paso (nieve, rachas, isoterma bajo la cota del paso). Estado abierto/cerrado: el sitio de la UPF solo publica noticias → enlace al sitio oficial e investigar.
- [ ] Probar en un teléfono real el inicio por ubicación (permiso, ubicación automática, última comuna guardada).
- [ ] Tamaño del JSON v2 (~49 KB × 346 por cada publicación): revisar consumo de ancho de banda de Upstash (plan gratuito) y, si hace falta, compactar (claves cortas, quitar `rango`).
- [x] Ingerir observaciones DMC (2026-10-01).
- [ ] Recalibrar el algoritmo ClimApp con 2–3 semanas de datos; pasar a `forecast_archive` (pronósticos reales) y considerar altura estación–comuna.
- [x] Algoritmo ClimApp v2 (2026-10-01): altura, varias estaciones por cuadrante, τ automático, control de calidad, validación diaria.
- [ ] Algoritmo ClimApp: revisar la validación diaria (`select fecha, metricas from algoritmo_validacion order by fecha desc`) y recalibrar con 2–3 semanas (el sesgo inicial es dentro de muestra); probar el sesgo con `forecast_archive` a 24–72 h.
- [ ] Verificar que SINCA responde desde GitHub Actions (job `sinca_obs` en `ingestion_runs`).
- [ ] INIA (agrometeorologia.cl, 210 estaciones): revisar términos y acceso a datos; sumarla si es posible.
- [ ] SINCA: volver a correr `scripts/build_sinca.py` cada algunos meses (series nuevas o dadas de baja).
- [ ] Mediciones cada 15 min (hoy cada hora, al minuto 59): GitHub Actions privado tiene 2.000 min/mes y ya se usan ~720–1.400; evaluar otro ejecutor (repo público, Supabase Edge Function, Cloudflare Worker).
- [ ] **Búsqueda por localidades** (evaluada 2026-10-01, ver bitácora): índice estático de localidades OSM → comuna (nivel caseríos + barrios de comunas no urbanas, ~114–176 KB gzip, carga diferida al escribir), mostrar "Loncura · pronóstico de Quintero", desambiguar nombres repetidos, atribución ODbL. Validar contra entidades pobladas INE 2017.

- [x] Retención de observaciones: **180 días** (decisión del usuario, 2026-10-01). Con el archivo de pronósticos 2 veces al día por 90 días, la base se estabiliza en ~387 MB (77 % de 500 MB).
- [ ] Opcional: archivo de pronósticos 1 vez al día → ~283 MB (57 %), si hace falta más margen.

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
- [x] Semana 4: fusionada (PR #5) y verificada en producción: todas las páginas 200, comuna inexistente 404, páginas de comuna servidas desde caché de CDN tras la primera visita (~1,4 s la primera vez por ISR). (2026-10-01)
- [ ] Alertas de fallas de ingesta (hoy: correo de GitHub cuando falla el cron + `/api/health` devuelve 503 si los datos tienen más de 8 h; falta un monitor externo que lo consulte).
- [x] Atribución CC BY 4.0 y ajustes de la plantilla aplicados sobre `Template/` con los 13 ajustes de [docs/frontend-template-analisis.md](docs/frontend-template-analisis.md) (Server Components, Tailwind v4, íconos PWA desde SVG con `sharp`, sin `radar/` hasta Fase 3).
