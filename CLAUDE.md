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
- Control de versiones con git. El trabajo se hace en **ramas**, no directamente en `main`.
- Al terminar cada sesión o cambio relevante:
  1. Agregar una entrada en **Bitácora de cambios** (fecha, rama, qué se hizo).
  2. Actualizar **Pendientes** (marcar lo completado, agregar lo nuevo).
  3. Hacer commit en la rama de trabajo.

## 6. Estado actual

- Repositorio inicializado. Solo existe el documento de requisitos y este archivo.
- No hay código aún. Stack aún no confirmado (ver Pendientes).

---

## 7. Bitácora de cambios

### 2026-10-01 — rama `docs/claude-md-contexto`
- Inicializado repositorio git (`main` con el SRS como commit inicial).
- Creado `CLAUDE.md` con contexto del proyecto (resumen del SRS v2.0), arquitectura, requisitos, hoja de ruta, convenciones, bitácora y pendientes.
- Agregado `.gitignore` base.
- Intento de crear repositorio remoto: no realizado por falta de `gh` y credenciales; queda en Pendientes con los pasos.

---

## 8. Pendientes

### Decisiones por tomar
- [ ] Backend: **Node.js vs. Python (FastAPI)** — Python facilita el procesamiento numérico (GRIB/NetCDF, ensemble).
- [ ] Hosting backend: Render vs. Cloudflare Workers.
- [ ] Proveedor LLM: Gemini Flash vs. GPT-4o-mini (u otro).
- [ ] Estructura del repositorio (monorepo frontend + backend o repos separados).
- [ ] Repositorio remoto (GitHub u otro) y política de ramas/merge.
  - Bloqueo (2026-10-01): GitHub CLI (`gh`) no instalado y sin credenciales de GitHub en git. Pasos: `winget install --id GitHub.cli` → `gh auth login` → `gh repo create ClimApp --private --source . --remote origin` → push de `main` y `docs/claude-md-contexto`.
  - Luego vincular el repo al proyecto de claude.ai "ClimApp" (https://claude.ai/project/01a0f79e-6e15-723a-a00e-5c252c791837) desde *Agregar contenido → GitHub* (requiere resincronizar tras cada push).

### Investigación
- [ ] Revisar qué datos publica la Armada de Chile (Servimet/Directemar): formatos, frecuencia, si hay API o requiere scraping, términos de uso.
- [ ] Confirmar límites y cobertura de Open-Meteo / NOAA GFS / ECMWF Open Data para Chile.
- [ ] Definir catálogo geográfico: comunas, puertos y sectores costeros con coordenadas.

### Fase 1 (MVP)
- [ ] Esquema de base de datos (Supabase/PostgreSQL).
- [ ] ETL de ingesta Open-Meteo.
- [ ] Conector Armada de Chile.
- [ ] Normalización de unidades e indexación espacial.
- [ ] API REST básica con caché (Upstash Redis).
- [ ] UI básica de pronóstico (Next.js + Tailwind) con búsqueda por comuna.
