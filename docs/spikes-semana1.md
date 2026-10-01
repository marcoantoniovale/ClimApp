# Spikes de la semana 1 — fuentes de datos

Fecha: 2026-10-01. Objetivo: confirmar las fuentes de la Fase 1 antes de construir los conectores ([fase1-mapeo-requisitos.md §5](fase1-mapeo-requisitos.md)).
Respuestas reales capturadas en [ClimAppWeb/etl/tests/fixtures/](../ClimAppWeb/etl/tests/fixtures/).

## Resumen

| Fuente | Resultado | Decisión |
|---|---|---|
| Open-Meteo (GFS, ECMWF, ICON) | Funciona; 3 modelos en una llamada; sin vacíos en las variables requeridas | **Go** |
| Open-Meteo Marine | Funciona (altura, período, dirección de oleaje) | **Go** |
| Armada — observaciones | **API JSON** pública, no requiere scraping | **Go** |
| Armada — avisos | Lista de avisos vigentes extraíble del HTML; el contenido es imagen/PDF escaneado | **Go parcial**: metadatos en Fase 1, texto en Fase 2 |
| Armada — pronósticos por zona | Interfaz interactiva; no se evaluó a fondo | Fase 2 (entrada del boletín LLM) |
| Boyas | Son del **SHOA**, no de Servimet | Fuera de la Fase 1 |

## 1. Open-Meteo

**Pronóstico** — `GET https://api.open-meteo.com/v1/forecast`
- Parámetro `models=gfs_seamless,ecmwf_ifs025,icon_seamless` devuelve los tres modelos en una respuesta; cada variable llega con sufijo de modelo (`temperature_2m_ecmwf_ifs025`).
- Varias coordenadas por llamada (`latitude=a,b&longitude=c,d`) → respuesta en arreglo.
- `wind_speed_unit=ms` entrega el viento ya en m/s (unidad canónica).
- Variables probadas, sin nulos en 168 h para los 3 modelos: temperatura, humedad, probabilidad y cantidad de precipitación, viento (velocidad, dirección, ráfaga), presión al nivel del mar.
- Prueba: 2 puntos × 3 modelos × 8 variables × 7 días → 47 KB, 1,7 s.
- Ojo: el punto se ajusta a la grilla del modelo (Valparaíso −33,047 → −33,095). Para comunas costeras puede caer en una celda de mar; evaluar en la semana 2.

**Marino** — `GET https://marine-api.open-meteo.com/v1/marine`: `wave_height`, `wave_period`, `wave_direction`, `swell_wave_height`.

**Condiciones del plan gratuito** ([términos](https://open-meteo.com/en/terms), [precios](https://open-meteo.com/en/pricing)):
- < 10.000 llamadas/día, 5.000/hora, 600/minuto, 300.000/mes.
- **Solo uso no comercial.** Sitios con publicidad o suscripciones requieren plan pagado (Standard: 1M llamadas/mes).
- Licencia de datos **CC BY 4.0**: hay que mostrar atribución en la web.
- Peso: más de 10 variables o más de 2 semanas cuentan como llamadas fraccionales adicionales (15 variables = 1,5 llamadas). No documentan el peso de varios modelos ni varias ubicaciones; asumimos 1 llamada por ubicación × (variables × modelos / 10).
- Estimación Fase 1: 8 variables × 3 modelos = 24 → 2,4 llamadas por ubicación; 346 comunas × 2,4 × 4 corridas/día ≈ **3.300 llamadas/día** (≈ 100.000/mes). Cabe en el límite mensual con margen ~3×.

## 2. Armada de Chile (Servimet / Directemar)

### Observaciones — API JSON (hallazgo principal)

El mapa de estaciones `https://serviciosonline.directemar.cl/meteomapa/` es una app Angular que consume una API JSON sin autenticación. Base: `https://serviciosonline.directemar.cl/meteomapa/api/meteo`.

| Endpoint | Contenido | Tamaño / tiempo |
|---|---|---|
| `/mapa` | 57 estaciones automáticas (EMA): id, nombre, lat, lon | 7 KB, 0,07 s |
| `/observaciones` | Última observación detallada de 5 EMA: 20 parámetros codificados (`cdparam`/`nmparam`) | 14 KB, 1,2 s |
| `/observaciones/directemar` | Última observación de 43 capitanías de puerto: temperatura, presión, humedad, punto de rocío, viento (dir. y vel.) | 24 KB, 0,4 s |
| `/top` | No probado | — |

Problemas de calidad que el conector debe manejar:
- **Lecturas antiguas**: 8 de 43 capitanías no estaban al día (la más antigua de 2025-09-29) y 3 traen `"fecha": "Fecha inválida"`. → Descartar observaciones repetidas o con fecha inválida; marcar estaciones inactivas.
- **Unidades no declaradas** en capitanías (`unidadViento: null`). En las EMA el parámetro 6 indica la unidad (1 = nudos; las 5 venían en nudos). → Confirmar la unidad del viento de capitanías comparando con Open-Meteo antes de convertir.
- **Coordenadas corruptas**: la EMA "Paso Timbales" publica longitud `-7029193.0`. → Validar rangos; corregido en el catálogo.
- **Hora**: las EMA traen `time` (UTC) y `timeLocal`; las capitanías solo `fecha` (aparentemente hora local). → Confirmar zona horaria.
- Es una API interna de la web, sin documentación ni compromiso de estabilidad. → Validar estructura en cada lectura y alertar si cambia.

### Avisos (marejadas, mal tiempo, temporal)

- La portada `https://meteoarmada.directemar.cl/` lista los avisos vigentes con título, zona, fecha/hora de emisión y enlace (`/meteo/<zona>`). Se puede extraer del HTML.
- Cada aviso es una página con una **imagen** (`AV44_VERTICAL.jpg`) y un **PDF escaneado** (`combinado.pdf`) sin capa de texto.
- Fase 1: guardar tipo, zona, emisión y enlaces; mostrar el aviso en la UI con enlace al original.
- Fase 2: extraer el texto con OCR o con el LLM multimodal (también sirve como entrada del boletín).
- Las zonas de los avisos son tramos de costa ("Golfo de Penas hasta Arica y Arch. Juan Fernández", "Corral a Golfo de Penas"): hay que mapearlas a comunas costeras (semana 3).

### Acceso técnico
- `robots.txt` de meteoarmada permite todo (`Disallow:` vacío).
- `curl` de Windows (Schannel) **no** logra el handshake TLS con `meteoarmada.directemar.cl`; Python (OpenSSL) sí. Sin impacto: el ETL corre en Python/Linux.

### Otras fuentes enlazadas por la Armada
- Boyas, mareas y temperatura del mar: **SHOA** (`shoa.cl`).
- Red de sensores antárticos (INACH) y red amateur (redmeteo.cl): no evaluadas.

## 3. Catálogo geográfico

- **Comunas**: lista oficial SUBDERE (346 comunas, 16 regiones, código CUT) desde el paquete chilemapas (Apache-2.0).
- **Coordenadas**: Wikidata por código CUT (343), Open-Meteo Geocoding (2: Rengo, Marchihue) y 1 corrección manual (Antártica → Villa Las Estrellas).
- **Nombres**: se usa el nombre de Wikidata (con tildes, p. ej. "Coyhaique", "O'Higgins") y se guarda el de SUBDERE como alias para la búsqueda.
- **Estaciones**: 100 (57 EMA + 43 capitanías), cada una asociada a la comuna más cercana.
- Wikidata limita a 1 consulta/minuto (había una caída en curso); por eso las respuestas quedan guardadas en `etl/data/sources/`.

## 4. Impacto en el plan

1. El conector Armada es **más simple y robusto** de lo previsto para observaciones (JSON en vez de scraping). Puede adelantarse a la semana 2 junto con Open-Meteo.
2. Los avisos llegan solo como imagen/PDF: en la Fase 1 la UI muestra título, zona, hora y enlace, no el texto.
3. Atribución CC BY 4.0 a Open-Meteo obligatoria en la web.
4. Pendiente: definir qué comunas son costeras (pronóstico marino) y mapear zonas de avisos a comunas.
