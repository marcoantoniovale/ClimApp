# Propuesta: localidades y barrios con pronóstico propio (microclimas)

Fecha: 2026-10-03. Estado: **aprobada** (L0, L1 y L2 con cuota gratuita, todo Chile; OSM con atribución) e implementada el 2026-10-03 (ver §7).

## 1. Problema

ClimApp entrega un pronóstico por comuna, calculado en la cabecera comunal. Dentro de una comuna hay microclimas: costa e interior, quebradas, cerros, valles. El usuario vive en **Loncura** (comuna de Quintero) y percibe que su clima se parece más al de **Ventanas** (Puchuncaví) que al de Quintero centro. Lo mismo ocurre en el interior (p. ej. Valle Alegre frente a Quintero, o los sectores altos de las comunas cordilleranas).

Además, la base de datos debe crecer menos: hoy pesa 85 MB y, con la retención actual, superaría los 500 MB del plan gratuito en ~2 meses (ver §5).

## 2. Diagnóstico con datos (2026-10-03)

**Pocas estaciones en la zona.** En Quintero y Puchuncaví el algoritmo usa una sola estación (Quintero Climatológica, DMC). Loncura, Ventanas, Horcón y Maitencillo se corrigen todos con ella.

**Hay más estaciones disponibles.** La red CQP del Ministerio del Medio Ambiente (publicada en SINCA) tiene temperatura al día en 13 estaciones de Quintero, Puchuncaví y Concón que no estaban en el listado cuando se armó el catálogo (2026-10-01): Loncura MMA, Super Sitio Ventanas, Quintero Sur, Super Sitio Quintero, Valle Alegre, Mantagua, Maitencillo, Puchuncaví Centro, Escuela La Greda, Pucalán, Super Sitio Concón, Concón Oeste y Puente Colmo. El catálogo SINCA pasa de 61 a 74 estaciones.

**Cuánto difieren (112 horas, 29 sep – 3 oct, respecto de Loncura MMA):**

| Estación | Distancia | Diferencia media | Diferencia absoluta media | Tarde (12–18 h) |
|---|---|---|---|---|
| Quintero DMC | 3,7 km | −0,27 °C | 0,65 °C | −0,80 °C |
| Quintero Sur MMA | 3,6 km | +0,24 °C | 0,87 °C | −0,83 °C |
| Super Sitio Ventanas | 5,5 km | +0,48 °C | 0,83 °C | **−0,28 °C** |
| Valle Alegre MMA (interior) | 4,9 km | −0,71 °C | **1,40 °C** | +0,90 °C |
| Super Sitio Quintero | 5,4 km | +0,27 °C | 1,45 °C | −1,54 °C |
| Maitencillo MMA | 14,2 km | −0,51 °C | 0,78 °C | −1,38 °C |

- En la **tarde**, Loncura se parece más a Ventanas que a Quintero (coincide con la percepción del usuario). En el promedio del día, Quintero DMC está igual de cerca. Con solo 4 días, falta confirmarlo.
- Lugares a menos de 5 km difieren hasta 1,4 °C (Valle Alegre, interior). **El microclima existe y lo explican las estaciones cercanas, no la distancia a la cabecera.**
- Los modelos (ICON ~13 km, ECMWF ~9 km) ponen a Loncura y Quintero en la misma celda. La diferencia solo se puede capturar con mediciones locales, la altura y la zona (costa o interior).

## 3. Propuesta

### Etapa L0 — Más estaciones e historial más pequeño (½ día)

1. **Actualizar el catálogo SINCA** (61 → 74 estaciones, 13 nuevas en la zona de Quintero, Puchuncaví y Concón) y programar su renovación mensual automática.
2. **Historial más pequeño** (detalle en §5): observaciones 180 → 60 días; registro del error 45 → 35 días; archivo de pronósticos 1 vez al día, cada 6 h hasta 48 h, por 30 días; registro de corridas 90 → 30 días.

Con L0, Loncura ya mejora a nivel de comuna: el algoritmo de Quintero pasa a usar Loncura MMA, Quintero Sur y Super Sitio Quintero, además de la DMC.

### Etapa L1 — Localidades como puntos de pronóstico (3–4 días)

**Qué es una localidad.** Un punto con nombre, comuna, coordenadas, altura (modelo digital del terreno) y zona (costa si está a ≤ 2 km del mar). Fuente: OpenStreetMap (ciudades, pueblos, aldeas, sectores y parajes), **2.629 localidades**. A eso se suman los barrios de comunas no urbanas, porque Horcón está en OSM como "barrio", y una lista corregida a mano para casos conocidos. Se validan contra las entidades pobladas del INE (Censo 2017).

**Cómo se calcula (sin descargar modelos de nuevo).** La localidad toma la curva de su comuna (mezcla ICON + ECMWF) y aplica tres ajustes propios:
1. **Algoritmo ClimApp en su punto:** sesgo por franja y anomalía del momento, interpolados por cuadrantes desde las estaciones más cercanas a la **localidad**, no a la cabecera. Loncura queda anclada a Loncura MMA (~2 km); Ventanas, a Super Sitio Ventanas.
2. **Altura:** diferencia de altura con la cabecera × 0,65 °C cada 100 m (el mismo ajuste que hace Open-Meteo dentro de una celda).
3. **Zona:** costa o interior según la propia localidad, para que use estaciones de su mismo tipo (Valle Alegre, interior, no se corrige con estaciones de playa).

**Costo.** El ETL calcula unos pocos números por localidad (sesgo por franja, anomalía y diferencia de altura) y publica una clave liviana por comuna con sus localidades: ~60 bytes por localidad, ~160 KB en total por hora. La web los suma a la curva de la comuna, como hoy hace con el ajuste del momento. **No agrega filas de pronóstico a la base ni llamadas a Open-Meteo.**

**En la web:**
- Página `/lugar/loncura`: "Loncura · comuna de Quintero", con la estación más cercana y su distancia.
- **GPS:** al ubicarte, busca la localidad más cercana dentro de tu comuna (≤ 3 km). El inicio muestra "Loncura" y no "Quintero", y queda guardada como hoy.
- **Buscador:** localidades y barrios, cargados solo al escribir (~20–110 KB comprimidos), con la comuna al lado para distinguir nombres repetidos ("Maitencillo · Puchuncaví").
- **Indicador de confianza:** "Medido a 2 km" o "Estimado; estación más cercana a 18 km".

### Etapa L2 — Modelo propio para localidades lejanas (2 días; depende del plan de Open-Meteo)

Cuando una localidad está lejos de su cabecera, probablemente cae en otra celda del modelo. Son ~1.750 de las 2.629 a más de 8 km; cerca de la mitad, a más de 20 km (comunas grandes del norte y del sur, Isla de Pascua). En esos casos conviene descargar su propia curva de temperatura.

- **Límite:** con el plan gratuito de Open-Meteo (10.000 llamadas/día) no alcanza para ~1.750 puntos en cada corrida. Opciones: (a) agrupar por celda del modelo y actualizar 2 veces al día; (b) priorizar pueblos y aldeas (~600 a más de 8 km); (c) el plan comercial de Open-Meteo, que también se necesita si hay publicidad.
- **Sin pasar por la base:** solo la diferencia de temperatura con la comuna, hora a hora (~1 KB por localidad), directo a Redis.

### Etapa L3 — Ajustes del algoritmo para microclimas (1 día, con datos)

- **Memoria del sesgo más corta** (vida media 7 → 3–5 días) si la validación muestra que reacciona mejor a los cambios locales. Se decide con la validación diaria, no a ojo.
- Validar el radio y la ponderación por cuadrantes con la red densa de Quintero, Puchuncaví y Concón: es un buen banco de pruebas.

## 4. Lo que no cambia

- La comuna sigue siendo la unidad base (avisos de la Armada, pasos, índice).
- El pronóstico de lluvia, viento y cielo de una localidad es el de su comuna (L1). La diferencia local se aplica a la temperatura y a la sensación térmica, que es donde está el microclima medido.

## 5. Tamaño de la base de datos

Medido el 2026-10-03 (85 MB en total).

| Tabla | Crecimiento | Retención actual → a 2 meses | Propuesta → estable |
|---|---|---|---|
| `forecast_archive` (ICON, ECMWF y Yr desde el 2 oct) | **~6 MB/día** | 90 días → **~545 MB** | 1/día, cada 6 h, 0–48 h, 30 días → **~34 MB** |
| `observations` (DMC + SINCA) | ~0,8 MB/día | 180 días → ~138 MB | 60 días → ~46 MB |
| `station_residuals` | ~0,8 MB/día | 45 días → ~37 MB | 35 días → ~29 MB |
| `forecast_current` | fijo | 46 MB | 46 MB |
| `location_snapshots`, oleaje y otros | fijo | ~20 MB | ~20 MB |
| **Total** | | **~790 MB (158 % del plan)** | **~175 MB (35 %)** |

El archivo de pronósticos se triplicó al sumar ECMWF y Yr el 2 de octubre. **Hay que corregirlo aunque no se apruebe el resto** (L0).

Las localidades de L1 casi no ocupan espacio en la base: el catálogo de ~3.000 filas pesa < 1 MB. L2, sin pasar por la base, tampoco.

## 6. Decisiones

1. ¿Aprobar L0 de inmediato (más estaciones SINCA e historial más pequeño)? Recomendado: sí.
2. Alcance de L1: ¿2.629 localidades más barrios de comunas no urbanas, o empezar por la Región de Valparaíso como piloto?
3. L2: esperar a decidir el plan comercial de Open-Meteo (ligado a la publicidad) o hacerlo con la cuota gratuita (2 veces al día, solo pueblos).
4. Licencia: OSM es ODbL → atribución "© colaboradores de OpenStreetMap" en el pie, y el catálogo derivado queda bajo la misma licencia.

## 7. Implementación (2026-10-03)

- **L0:** catálogo SINCA renovado cada semana en la base (74 estaciones); retención menor con limpieza cada hora.
- **Catálogo:** [build_localidades.py](../ClimAppWeb/etl/scripts/build_localidades.py) → `data/catalog/localidades.csv`, **3.584 localidades** (1.405 parajes, 1.249 barrios, 779 aldeas, 98 sectores, 51 pueblos y 2 ciudades) en 335 comunas, todas con altura. A mano: Valle Alegre (Quintero). Índice de búsqueda `web/public/localidades.json` (305 KB; 75 KB comprimido, se carga al escribir).
- **Zona costa/interior:** se probó ponderar por distancia al mar (línea de costa Natural Earth 1:10M) y no mejoró la validación (1,040 vs 1,026 °C); se mantiene la zona de la comuna. Lo que captura el microclima es la estación más cercana, que domina el peso.
- **L1:** job `localidades` (cada hora) → clave `lugares:<comuna>` con la diferencia de sesgo por franja, la altura o el perfil, la anomalía del momento y la medición más cercana. Web: `/lugar/<comuna>/<localidad>`, `/api/lugar/<comuna>/<localidad>`, buscador con localidades, GPS a la localidad más cercana dentro de la comuna (si está más cerca que la cabecera y a ≤ 3 km), localidades de cada comuna enlazadas.
- **L2:** job `localidades_perfil` (1 vez al día): 1.897 localidades a > 8 km de su cabecera, en ~1.100 celdas de 0,1°; perfil por hora local en `localidad_perfil`.
- **Cuota de Open-Meteo:** el error de las estaciones pedía su pronóstico cada hora (~10.000 llamadas/día, sobre el límite gratuito). Ahora se guarda en `station_forecast` y se renueva solo con corridas nuevas (~1.800/día). GFS pasa a 2 veces al día. Total estimado ~9.000/día con L2.
- Ejemplo (3 oct): Valle Alegre (interior) queda 2,2 °C más frío de madrugada que Quintero, con su propia estación (Valle Alegre MMA, a 0,3 km); Ventanas se corrige con Super Sitio Ventanas.
