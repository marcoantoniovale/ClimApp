# Fase 1 — Mapeo de requisitos e implementación

Fuente: [ReqClimApp.docx](../ReqClimApp.docx) (SRS v2.0). Elaborado: 2026-10-01.
Alcance de la Fase 1 según el SRS (semanas 1–4): **configuración de BD y ETL, ingesta Open-Meteo + Armada, UI básica de pronóstico**.

Los datos marcados con **(verificar)** son supuestos que deben confirmarse en los spikes de la semana 1 antes de construir sobre ellos.

> **Actualización 2026-10-01:** los spikes de la semana 1 están en [spikes-semana1.md](spikes-semana1.md). Cambios principales: las observaciones de la Armada tienen API JSON (no requieren scraping); los avisos son imagen/PDF escaneado (en Fase 1 solo metadatos); las boyas son del SHOA; Open-Meteo confirmado (no comercial, CC BY 4.0, ~3.300 llamadas/día estimadas).

---

## 1. Qué requisitos entran en la Fase 1

| Req. | Descripción corta | Fase 1 | Qué se implementa en Fase 1 | Diferido a |
|---|---|---|---|---|
| RF01.1 | Ingesta de modelos globales | **Sí** | GFS, ECMWF e ICON a través de Open-Meteo (una sola API entrega los tres modelos). NOAA y ECMWF Open Data directos no son necesarios aún. | — |
| RF01.2 | Ingesta red Armada de Chile | **Sí (parcial)** | Observaciones de estaciones costeras y avisos de mal tiempo / marejadas. Boletines marinos se guardan como texto crudo. | Boyas (si no están en la misma fuente) → Fase 2 |
| RF02.1 | Homogeneización de unidades | **Sí** | Conversión a unidades canónicas al ingerir (ver §4.3). | — |
| RF02.2 | Indexación espacial | **Sí (parcial)** | Catálogo de comunas, puertos y sectores costeros con coordenadas; asignación de estaciones Armada a sectores. | Microclimas → Fase 2/3 |
| RF03.1 | Ensemble con corrección de sesgo | No | **Preparación:** archivar pronósticos y observaciones desde el día 1 (ver §2). | Fase 2 |
| RF03.2 | Re-evaluación continua de pesos | No | — | Fase 2 |
| RF04.1 | Boletín vía LLM | No | Los avisos y boletines Armada se guardan ya estructurados para usarlos como entrada del LLM. | Fase 2 |
| RF05.1 | Búsqueda por comuna/ciudad/puerto | **Sí** | Buscador con autocompletado sobre el catálogo. | — |
| RF05.2 | Panel 7 días + alertas marítimas | **Sí (básico)** | Temperatura, prob. de precipitación, viento y humedad a 7 días; avisos Armada vigentes. Pronóstico provisional = promedio simple de los 3 modelos. | Pronóstico ensemble → Fase 2 |
| RF05.3 | Vista de fiabilidad | Opcional | Mostrar la dispersión entre modelos (mín./máx.) es barato porque los datos ya existen. Incluir si sobra tiempo. | Fase 2 |
| RF05.4 | Mapa interactivo de capas | No | — | Fase 3 |
| RNF01 | API < 300 ms en caché | **Sí** | Respuestas precalculadas por ubicación en Redis. | — |
| RNF02 | 99,5 % uptime frontend | **Sí** | Hosting en Vercel/CDN; el frontend no depende de un servidor propio encendido. | — |
| RNF03 | Escalar ante picos | **Sí** | La lectura no toca la BD: CDN + Redis. | Pruebas de carga → Fase 3 |
| RNF04 | Eficiencia / cron | **Sí** | Toda la ingesta corre en tareas programadas; ninguna petición de usuario llama a fuentes externas. | — |

---

## 2. Hallazgos del análisis (riesgos y vacíos del SRS)

1. **La Fase 2 depende de datos que debe generar la Fase 1.** La corrección de sesgo (RF03.1) necesita semanas de pronósticos pasados comparados con observaciones reales. Si la Fase 1 solo guarda el último pronóstico, la Fase 2 parte sin historia. → La Fase 1 debe **archivar** desde el primer día los pronósticos de cada modelo en los puntos donde hay estaciones Armada, junto con las observaciones.

2. **El volumen de datos choca con la capa gratuita de la BD.** Estimación: ~390 ubicaciones (346 comunas + ~40 puntos costeros) × 3 modelos × 168 horas ≈ 196 mil filas por corrida (~30 MB). Guardar 4 corridas diarias llenaría los 500 MB de Supabase Free en ~4 días. → Separar en:
   - **Pronóstico vigente**: una tabla que se sobrescribe en cada corrida (~30 MB fijos).
   - **Archivo de verificación**: solo puntos con estación Armada (~30–50), horizonte ≤ 72 h, resolución 3-horaria, 2 corridas/día ≈ 1 MB/día → ~330 MB/año. Definir retención (p. ej., 12 meses) o agregados diarios.

3. **Armada de Chile: la fuente más incierta.** El SRS asume datos estructurados de estaciones, boyas, avisos y boletines, pero no indica si existe API. Lo más probable es que haya que hacer scraping de páginas HTML/PDF de Servimet/Directemar **(verificar)**. Riesgos: cambios de formato que rompen el scraper, términos de uso y frecuencia de publicación. → Spike en la semana 1; diseñar el conector aislado y con validación, y que una falla de la Armada no detenga la ingesta de modelos.

4. **Boyas.** Los datos de boyas podrían venir de otra institución (p. ej., SHOA) y no de Servimet **(verificar)**. Si es así, quedan fuera de la Fase 1.

5. **Licencias de capas gratuitas.** La API gratuita de Open-Meteo y el plan Hobby de Vercel son para **uso no comercial** **(verificar)**. Sirve para el MVP, pero hay que cambiar de plan antes de monetizar. Agregar al análisis de costos de la Fase 3.

6. **Límites de Open-Meteo.** Plan gratuito ~10.000 llamadas/día **(verificar)**. 390 ubicaciones × 3 modelos × 4 corridas ≈ 4.700 llamadas/día, más la API marina para puntos costeros. Cabe, pero con poco margen. → Usar peticiones con varias coordenadas a la vez y 2–4 corridas diarias, alineadas con la publicación de los modelos.

7. **"UI básica de pronóstico" no define qué pronóstico mostrar** antes de que exista el ensemble. → Mostrar el promedio simple de los 3 modelos, etiquetado como provisional.

8. **Tareas programadas.** El cron del plan Hobby de Vercel es muy limitado y los servicios gratuitos de Render se suspenden por inactividad (los arranques en frío incumplirían RNF01) **(verificar)**. → Ver la propuesta de §3.

9. **Supabase Free pausa proyectos inactivos** **(verificar)**. La ingesta periódica lo mantiene activo, pero conviene monitorearlo.

---

## 3. Arquitectura propuesta para la Fase 1

Resuelve varias decisiones pendientes del CLAUDE.md. Es una **propuesta**: requiere aprobación.

```
 GitHub Actions (cron 2–4×/día)            Vercel
 ┌──────────────────────────────┐          ┌──────────────────────────────┐
 │ ETL Python                   │          │ Next.js + Tailwind           │
 │  ├─ conector Open-Meteo      │          │  ├─ buscador (catálogo JSON) │
 │  ├─ conector Armada          │          │  ├─ panel 7 días             │
 │  ├─ normalización unidades   │          │  └─ API: Route Handlers      │
 │  └─ precálculo por ubicación │          │        lee Redis (< 300 ms)  │
 └──────┬──────────────┬────────┘          └──────────────┬───────────────┘
        │              │                                  │
        v              v                                  │
 Supabase (Postgres)   Upstash Redis  <───────────────────┘
 fuente de verdad      JSON listo por ubicación
 + archivo histórico   + avisos vigentes
```

| Decisión | Propuesta | Motivo |
|---|---|---|
| Lenguaje del ETL | **Python** | Mejor ecosistema para scraping (httpx, BeautifulSoup, pdfplumber) y datos numéricos (pandas); es lo que se usará en el ensemble de la Fase 2. |
| Backend / API | **Route Handlers de Next.js en Vercel** (sin servidor aparte) | Solo leen JSON precalculado desde Redis; evita un servicio siempre encendido y los arranques en frío. FastAPI queda para cuando haya lógica de servidor real. |
| Ejecución del cron | **GitHub Actions** (workflow programado) | Gratis dentro de la cuota (~2.000 min/mes en repos privados; uso estimado ~250 min/mes) **(verificar)**. Requiere el repositorio remoto (pendiente). |
| Estructura del repo | **Monorepo**: código en `ClimAppWeb/` (`web/`, `etl/`, `db/`); documentación en `docs/` | Un solo lugar para el esquema, la ingesta y el frontend. |
| Búsqueda | Catálogo estático (~400 entradas) enviado al cliente | Búsqueda instantánea sin llamadas a la API. |

---

## 4. Diseño de componentes

### 4.1 Catálogo geográfico (RF02.2, RF05.1)
- **Comunas**: 346, con región y coordenadas del centroide o de la cabecera comunal. Fuente candidata: división político-administrativa oficial (INE/SUBDERE/BCN) **(verificar)**.
- **Puertos y sectores costeros**: según jurisdicción de capitanías de puerto / zonas usadas en los avisos de la Armada, para poder asociar cada aviso a ubicaciones.
- **Estaciones Armada**: id, nombre, coordenadas, tipo (costera/boya), sector asignado.
- Se guarda en la BD y se exporta como JSON estático para el buscador.

### 4.2 Esquema de base de datos (borrador)

| Tabla | Contenido | Notas |
|---|---|---|
| `locations` | id, tipo (comuna/puerto/sector), nombre, región, lat, lon, slug | Catálogo. |
| `stations` | id, fuente, nombre, tipo, lat, lon, location_id | Estaciones Armada. |
| `forecast_current` | location_id, modelo, hora_valida, variables… | Formato ancho (una columna por variable). Se sobrescribe en cada corrida. |
| `forecast_archive` | station_id, modelo, hora_emisión, hora_valida, variables… | Solo puntos con estación, ≤ 72 h, 3-horario. Base para RF03. |
| `observations` | station_id, hora_observación, variables… | Observaciones Armada. |
| `marine_warnings` | id, tipo (marejada/mal tiempo…), sectores, emitido, vigente_desde/hasta, texto, url_fuente | Avisos estructurados + texto original. |
| `bulletins_raw` | id, fuente, emitido, contenido, url | Texto crudo; entrada del LLM en Fase 2. |
| `ingestion_runs` | id, conector, inicio, fin, estado, filas, error | Monitoreo y depuración. |

Variables mínimas: temperatura, sensación térmica, estado del cielo (`weather_code`), índice UV, probabilidad y cantidad de precipitación, velocidad/dirección/ráfaga de viento, humedad relativa, presión; en puntos costeros, altura/período/dirección de oleaje (API marina de Open-Meteo, confirmada). Sensación térmica, estado del cielo e índice UV se agregaron por la plantilla de frontend.

### 4.3 Unidades canónicas (RF02.1)
| Variable | Se almacena en | Se muestra en |
|---|---|---|
| Temperatura | °C | °C |
| Presión | hPa | hPa |
| Precipitación | mm | mm |
| Viento | **m/s** (canónica interna) | km/h en tierra, nudos en sectores costeros |
| Oleaje | m (altura), s (período), ° (dirección) | igual |
| Tiempo | UTC | hora de Chile (`America/Santiago`) |

La conversión se hace en un único módulo con pruebas unitarias; la UI elige la unidad de despliegue según el tipo de ubicación.

### 4.4 Conector Open-Meteo (RF01.1)
- Peticiones con varias coordenadas por llamada, un parámetro de modelos para GFS/ECMWF/ICON.
- Corridas alineadas con la publicación de los modelos (2–4×/día).
- Reintentos con espera creciente; si un modelo falla, se publican los otros dos.

### 4.5 Conector Armada (RF01.2)
- Módulo aislado por tipo de dato: observaciones, avisos, boletines.
- Validación de la estructura extraída: si la página cambió, se registra el error en `ingestion_runs` y **no** se sobrescriben datos buenos con datos vacíos.
- Se guarda siempre la URL y el texto original para trazabilidad.

### 4.6 Precálculo y API (RNF01, RNF04)
- Al final de cada corrida, el ETL genera por ubicación un JSON con: pronóstico horario 48 h, diario 7 días (promedio de modelos + mín./máx. entre modelos) y avisos vigentes. Se escribe en Redis.
- Endpoints:
  - `GET /api/forecast/{slug}` → JSON precalculado.
  - `GET /api/warnings?sector=` → avisos vigentes.
- Encabezados de caché HTTP para que el CDN absorba los picos (RNF03).

### 4.7 Frontend (RF05.1, RF05.2)
Referencia visual y de componentes: plantilla `Template/`, con los ajustes de [frontend-template-analisis.md](frontend-template-analisis.md).

- Página de inicio con buscador de comuna/ciudad/puerto.
- Página por ubicación: tarjetas diarias a 7 días, gráfico horario (temperatura, precipitación, viento, humedad), banner de avisos marítimos vigentes, hora de la última actualización y aviso de "pronóstico provisional".
- Diseño responsivo (uso móvil en zonas costeras).

---

## 5. Plan de trabajo (4 semanas)

| Semana | Entregables | Criterio de cierre |
|---|---|---|
| **1 — Spikes y bases** | Spike Armada (fuentes, formato, frecuencia, términos de uso); spike Open-Meteo (modelos, variables, límites, API marina); aprobación del stack; repo remoto; estructura del monorepo; catálogo geográfico; esquema de BD v1 | Documento de spikes con decisión go/no-go del scraping; catálogo con ≥ 346 comunas cargado |
| **2 — Ingesta de modelos** | Conector Open-Meteo, normalización de unidades con pruebas, escritura en `forecast_current` y `forecast_archive`, workflow cron, registro en `ingestion_runs` | 3 días seguidos de corridas automáticas sin intervención |
| **3 — Armada y API** | Conector Armada (observaciones + avisos), precálculo a Redis, endpoints de la API | Avisos vigentes visibles por API; p95 < 300 ms en endpoints |
| **4 — UI y despliegue** | Buscador, panel 7 días, banner de avisos, despliegue en Vercel, alerta si falla una corrida | Usuario busca una comuna o puerto y ve pronóstico y avisos en móvil y escritorio |

---

## 6. Decisiones que requieren aprobación

1. Stack propuesto en §3 (Python ETL + Next.js API en Vercel + GitHub Actions).
2. Política de retención del archivo histórico (propuesta: 12 meses, 3-horario).
3. Pronóstico provisional = promedio simple de modelos hasta la Fase 2.
4. Incluir o no la vista de dispersión (RF05.3) en la Fase 1.
5. Go/no-go del scraping de la Armada tras el spike (y plan B si no es viable: Fase 1 solo con modelos + avisos ingresados manualmente).
