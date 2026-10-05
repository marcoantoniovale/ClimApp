# Precisión del pronóstico — evaluación y plan

Fecha: 2026-10-01. Origen: el usuario detectó que ClimApp mostraba **20 °C en Quintero** mientras la estación oficial de la DMC ([320056](https://climatologia.meteochile.gob.cl/application/diariob/visorDeDatosEma/320056)) marcaba **16,1 °C** (19:30).

## 1. Qué muestra hoy ClimApp

- El número grande ("ahora") es el **pronóstico para la hora actual**: promedio simple de GFS, ECMWF e ICON. No es una medición.
- En Quintero, a las 19:00, los modelos iban de **17,4 a 23,9 °C** (6,5 °C de diferencia) y el promedio daba 19,8 °C.
- La medición que mostramos al lado venía de la capitanía de puerto, con 2 h de antigüedad: las observaciones de la Armada no se recolectan automáticamente.

## 2. Diagnóstico en Quintero (30-sep y 1-oct, 44 horas)

Error de cada modelo contra la estación DMC 320056:

| Modelo (Open-Meteo) | Sesgo | Error medio | Peor |
|---|---|---|---|
| GEM (Canadá) | +1,1 | 1,2 | +3,3 |
| best_match | +0,7 | 1,3 | +3,8 |
| Météo-France | +1,2 | 1,4 | +4,1 |
| ICON | +1,4 | 1,5 | +3,9 |
| UKMO 10 km | +1,3 | 1,8 | +6,2 |
| ECMWF AIFS | +2,0 | 2,0 | +4,8 |
| GFS | +2,5 | 2,9 | +6,8 |
| **ECMWF IFS 0,25°** | **+3,0** | **3,2** | **+7,9** |
| **Promedio ClimApp (GFS+ECMWF+ICON)** | **+2,3** | **2,4** | |

**Causa principal: la celda del modelo.** Open-Meteo elige por defecto una celda de **tierra** (`cell_selection=land`). Para Quintero tomó una a ~15 km tierra adentro (−32,743; −71,367), más cálida de día que la costa, que está bajo la influencia marina. Con `cell_selection=nearest` toma la celda costera (−32,743; −71,484):

| | land (actual) | nearest |
|---|---|---|
| GFS | +2,5 / 2,9 | +0,4 / 2,4 |
| ECMWF | +3,0 / 3,2 | +0,6 / 1,2 |
| ICON | +1,4 / 1,5 | +1,3 / 2,1 |
| **Promedio de los 3** | **+2,3 / 2,4** | **+0,8 / 1,7** |

(formato: sesgo / error medio, °C)

## 3. Validación en 13 estaciones DMC (norte a sur, 2 días)

Error medio del promedio de los 3 modelos, celda por defecto contra la más cercana:

| Estación | Tipo | land | nearest |
|---|---|---|---|
| 180005 Arica Chacalluta | costa | 1,0 | 1,0 |
| 220002 Calama | interior | 1,7 | 1,7 |
| 290004 La Serena | costa | 1,0 | 1,0 |
| **320056 Quintero** | costa | **2,4** | **1,7** |
| 330020 Santiago Quinta Normal | interior | 0,8 | 0,8 |
| 330021 Pudahuel | interior | 0,9 | 0,9 |
| 330031 Santo Domingo | costa | 1,6 | 1,6 |
| 360011 Concepción Carriel Sur | costa | 0,8 | 0,8 |
| 380013 Temuco | interior | 0,8 | 0,8 |
| 390006 Valdivia | interior | 0,8 | 0,8 |
| 410005 Puerto Montt | costa | 0,8 | 0,8 |
| 450005 Balmaceda | interior | 0,7 | 0,7 |
| 520006 Punta Arenas | costa | 0,7 | 0,6 |
| **Promedio costa (7)** | | **1,19** | **1,08** |
| **Promedio interior (6)** | | **0,95** | **0,95** |

Conclusiones:
- En la mayoría de las estaciones el promedio de ClimApp tiene un **error típico de ~1 °C**; Quintero es un caso extremo por la celda.
- `nearest` **mejora la costa y no empeora el interior** (en la mayoría de los puntos ambas opciones eligen la misma celda).
- Muestra pequeña (13 estaciones, 2 días): confirmar con más días.
- 200006 (Iquique) y 230001 (Antofagasta) no publicaron datos en el visor.

## 4. Fuentes de la DMC encontradas

| Fuente | Contenido | Uso posible |
|---|---|---|
| Visor de estaciones automáticas (`climatologia.meteochile.gob.cl/application/diariob/visorDeDatosEma/<código>`) | Observaciones minuto a minuto de hoy y ayer, por estación (~390 KB por página). El portal declara los datos de "acceso y uso público" y ofrece "Recursos Web JSON" para aplicaciones (requiere registro) | Observaciones para "ahora" medido y para la corrección de sesgo |
| `archivos.meteochile.gob.cl/portaldmc/appdata/condicionactual.js` | Condición actual de ~30 aeropuertos (METAR): temperatura, viento, humedad, nubosidad; 3,5 KB | Observaciones livianas en ciudades con aeropuerto |
| `archivos.meteochile.gob.cl/portaldmc/meteochile/js/pronostico.js` | **Pronóstico oficial** de 103 localidades: resto del día + 5 días, mínima/máxima, ícono y texto por período (madrugada, mañana, tarde, noche); redactado por pronosticadores de la DMC | Mostrar como referencia oficial y comparar nuestro pronóstico |
| Pronósticos de pasos fronterizos y Los Libertadores | Páginas específicas | Futuro (RutaClimApp) |

Pendiente: términos de uso de los productos de la DMC y si sus servidores responden desde la nube (la API de observaciones de la Armada no lo hace).

## 5. Plan propuesto

| # | Mejora | Efecto esperado | Esfuerzo |
|---|---|---|---|
| **P1** | `cell_selection=nearest` para las 106 comunas costeras | Quintero: error 2,4 → 1,7 °C; costa en general mejora levemente | ~1 h |
| **P2** | Ingerir observaciones de la DMC (estaciones automáticas, cada hora) y mostrar **"Ahora: 16,1 °C medido en Quintero (DMC, 19:30)"** cuando haya una estación a ≤ 15 km con dato de menos de 90 min; el pronóstico queda para las horas siguientes | Lo que el usuario compara con la estación coincide, porque es la medición | 1–2 días |
| **P3** | **Corrección de sesgo** (adelanta la Fase 2, RF03): por estación, modelo y hora del día, con ventana móvil de 14–30 días; aplicar a las comunas cercanas de la misma zona (costa, valle, cordillera) y **ponderar los modelos** según su error reciente | Elimina los errores sistemáticos como el +3 °C de ECMWF en la costa; error típico esperado < 1 °C el primer día | 1–2 semanas (requiere ≥ 2 semanas de datos) |
| **P4** | Mostrar el **pronóstico oficial de la DMC** de la localidad más cercana como referencia, y usarlo para comparar el nuestro | Confianza del usuario; referencia de calidad | 1 día |

La DMC resolvería además el bloqueo de la Fase 2: sus observaciones reemplazarían a las de la Armada, si sus servidores responden desde GitHub Actions.

---

## 6. Algoritmo ClimApp v1 (en producción desde el 2026-10-01)

Implementa P2 y el comienzo de P3. Código: `etl/src/climapp_etl/correccion.py` y `dmc_obs.py`.

**Mediciones:** mapa nacional de estaciones automáticas DMC (148 estaciones, una petición por hora) más carga inicial de 48 h por estación desde su visor. Las horas del visor se asignan por orden de serie: pasadas las 21:00 de Chile, la DMC rotula "hoy" con la fecha UTC (error encontrado y corregido el mismo día).

**Corrección (solo temperatura y sensación térmica de ICON):**
1. Sesgo por estación y franja del día (00–05, 06–11, 12–17, 18–23 h): promedio de ICON − medición en los últimos 14 días; atenuado con pocos datos (`n / (n + 12)`), limitado a ±5 °C; diferencias > 15 °C se descartan.
2. Cada comuna usa las estaciones de su misma zona (costa/interior) a ≤ 25 km, con peso `exp(−d / 10 km)` y atenuación hacia cero si están lejos. Sin estaciones cercanas no se corrige y la página lo indica.
3. Pasos fronterizos: sin corrección (las estaciones cercanas están a otra altura).

**Resultados al partir (2 días de datos, 134 estaciones, 209 de 346 comunas corregidas):**
- Validación cruzada (cada estación corregida solo con sus vecinas): error medio 1,20 → 1,17 °C (−2,2 %). La ganancia es modesta porque el sesgo es muy local y con 12 horas por franja la atenuación aplica ~50 %. Probadas variantes (K 3–12, radio 25–40 km): todas entre −1 % y −2,4 %.
- En el punto de la estación el efecto es mayor (Quintero: sesgo de +1,8 °C de noche y de mañana).

**Próximas mejoras:** usar `forecast_archive` (pronósticos reales a 24–72 h) en vez de los días pasados de Open-Meteo; considerar la diferencia de altura estación–comuna; sesgo según el horizonte; extender a viento y humedad; recalibrar con 2–3 semanas de datos.

## 7. Algoritmo ClimApp v2 (en producción desde el 2026-10-01)

Pedido del usuario: el algoritmo es la base de la plataforma; corregir la temperatura actual y el pronóstico con el historial inmediato, registrar el error de ICON contra las mediciones oficiales e irlo rectificando, y aplicar a las comunas sin medición un factor común de las estaciones cercanas (norte, sur, este, oeste). Código: [correccion.py](../ClimAppWeb/etl/src/climapp_etl/correccion.py), [jobs.py](../ClimAppWeb/etl/src/climapp_etl/jobs.py) (`residuals`, `corrections`, `_publicar_algoritmo`) y [lib/ahora.ts](../ClimAppWeb/web/src/lib/ahora.ts).

**Fuentes de medición**
| Red | Estaciones | Cómo se lee | Frecuencia |
|---|---|---|---|
| DMC, estaciones automáticas | ~136 con lectura | Mapa `menuTematicoEmas` (una página) | Cada hora (minuto 59) |
| SINCA (Ministerio del Medio Ambiente) | 61 con temperatura vigente (9 en la RM: Quilicura, Las Condes, Cerro Navia, Pudahuel, Parque O'Higgins, La Florida, El Bosque, Puente Alto, Talagante) | Exportación CSV de Airviro por estación; catálogo en `data/catalog/estaciones_sinca.csv` (`scripts/build_sinca.py`) | Cada hora; promedio horario |

SINCA rotula cada promedio al **inicio** de la hora en **UTC−4 fijo**. Verificado contra Quinta Normal (DMC) a 1,7 km de Parque O'Higgins: error 0,34 °C sin desfase, 0,70 °C con −1 h, 0,96 °C con +1 h. Cada promedio se fecha en el centro de su hora.

INIA (agrometeorologia.cl): 210 estaciones propias y 271 de otras redes; no se encontró un servicio de datos público (descarga por formulario). Queda pendiente revisar términos y acceso.

**Pasos**
1. **Registro del error** (`station_residuals`, cada hora): ICON − medido en el punto de la estación, con ICON interpolado al instante de la lectura. Una fila por estación y hora; no se reescribe con corridas posteriores. Retención 45 días (~0,7 MB/día).
2. **Control de calidad**: fuera de rango (−40…50 °C), error > 12 °C, salto > 8 °C/h, sensor pegado (6 lecturas idénticas) y discrepancia > 5 °C con la mediana de ≥ 3 vecinas de la misma zona a ≤ 50 km. Primera corrida: 84 de 10.175 horas descartadas (51 error, 31 vecinas, 2 saltos).
3. **Sesgo sistemático** por estación y franja de 6 h: promedio con olvido exponencial (vida media 7 días, ventana 30), atenuado n/(n+12), límite ±5 °C. Se recalcula cada 3 h; equivale a un filtro de Kalman de nivel local en régimen.
4. **Interpolación por cuadrantes** (sesgo y anomalía): estación más cercana al NE, NO, SE y SO; misma zona (costa/interior); ≤ 50 km; peso 1/(d+2)² · exp(−|Δaltura|/500 m); un peso fijo equivalente a una estación a 25 km tira hacia cero (lejos de todo, ICON puro). Se interpola el **error**, no la temperatura. Altura: modelo digital de Open-Meteo para estaciones y cabeceras.
5. **Anomalía del momento**: a = medido − (ICON − sesgo) en la última lectura válida (≤ 3 h) de cada estación, interpolada por comuna y publicada cada hora en Redis (`algoritmo`, ~90 KB). La web la suma a la curva y la desvanece con τ (temperatura actual, hora a hora, máximas y mínimas).
6. **Validación diaria** (`algoritmo_validacion`) y **τ automático** con la persistencia observada.
7. Estaciones ubicadas por **polígono comunal** (antes, por la cabecera más cercana: Pudahuel caía en Quilicura y Rodelillo en Viña del Mar).

**Primera validación** (2026-10-01, 196 estaciones, 10.091 horas de ~4 días):
| Escenario | Error medio |
|---|---|
| ICON sin corregir | 1,28 °C |
| Comuna **sin** estación (solo vecinas): sesgo | 1,20 °C |
| Comuna **sin** estación: sesgo + ajuste del momento, 1 h después | **1,08 °C** |
| Comuna **con** estación: sesgo | 0,95 °C (dentro de muestra, optimista) |
| Comuna **con** estación: sesgo + ajuste del momento, 1 h después | **0,57 °C** |

Persistencia de la anomalía (después de quitar el sesgo): 0,80 a 1 h, 0,59 a 2 h, 0,43 a 3 h, 0,23 a 6 h → **τ ≈ 4 h**. En v1 (sin separar el sesgo) la persistencia era 0,95 a 1 h (τ ≈ 20 h): la parte que dura días ahora la explica el sesgo.

Cobertura: ajuste del momento en 303 de 346 comunas (v1: 159); sesgo en 304 (v1: 209).

**Limitaciones y próximos pasos:** con solo ~4 días el sesgo se estima dentro de la muestra; recalibrar con 2–3 semanas. El sesgo usa ICON de la corrida más reciente (horizonte corto); evaluar con `forecast_archive` a 24–72 h. Mediciones cada 15 min requieren otro ejecutor (minutos de GitHub Actions). Sumar INIA si sus términos lo permiten.

## 8. Mezcla ICON + ECMWF IFS (desde el 2026-10-02)

El usuario consideró Yr (MET Norway) el pronóstico más exacto. Fuera de los países nórdicos Yr usa ECMWF IFS 9 km con ajuste por altura. Comparación con Open-Meteo en 197 estaciones DMC/SINCA, 13.322 horas (29 sep – 2 oct). "Con algoritmo": sesgo aprendido en la 1ª mitad del período, evaluado en la 2ª.

| Modelo | Crudo | Con algoritmo | Costa | Interior |
|---|---|---|---|---|
| ICON | 1,31 | 1,15 | 1,26 | 1,55 |
| ECMWF IFS 9 km | 1,38 | 1,23 | 1,46 | 1,53 |
| ECMWF IFS 0,25° | 1,51 | 1,26 | 1,57 | 1,58 |
| GFS | 1,82 | 1,31 | 1,72 | 1,75 |
| ECMWF AIFS | 1,62 | 1,38 | 1,47 | 1,97 |
| **Mezcla ICON + ECMWF IFS (50/50)** | **1,23** | **1,10** | 1,24 | **1,44** |

Decisión del usuario: mezcla. Temperatura y sensación térmica = promedio de ambos; máximas y mínimas = promedio de las de cada modelo (el rango entre modelos queda en `rango_max`/`rango_min`). Lluvia, viento, cielo, isoterma y nieve siguen de ICON. El registro del error y el sesgo se recalcularon con la mezcla (5 días).

Validación con la mezcla (14.876 h): base 1,24 °C → sin estación 1,04 °C; con estación 0,56 °C (1 h después de la medición). τ = 3,5 h.

**Comparación con Yr:** el pronóstico real de Yr (API Locationforecast de MET Norway, CC BY 4.0) se guarda dos veces al día en las estaciones (`forecast_archive`, modelo `yr`), junto con ICON y ECMWF, a 0–72 h. Con 2–3 semanas se compara temperatura, lluvia y viento.

Corregido además: la lluvia diaria promediaba como 0 mm los modelos que no la pronostican (GFS), y mostraba la mitad (Santiago, 2 oct: 2,3 en vez de 4,6 mm).

## 9. Lluvia: hora y consenso (2026-10-05)

- Open-Meteo entrega `precipitation`, `precipitation_probability`, `snowfall` y `weather_code` como valores de la **hora anterior** (la lluvia de 15 a 16 h viene rotulada 16:00). Yr (`next_1_hours`) y Meteored rotulan por la hora que empieza. Desde ahora el JSON usa la hora de inicio (`snapshot.a_hora_de_inicio`).
- La lluvia era solo de ICON. Ejemplo del 5 oct en Loncura (inicio ≥ 0,2 mm): ECMWF 17 h (aislado), Météo-France 19, GFS 20, ICON 22, JMA 22, GEM 23, UKMO 00; Yr: chubasco de 0,3 mm entre las 15–17 h y lluvia desde las 21 h. Ahora la lluvia es el promedio de ICON y ECMWF (probabilidad promedio; cielo: el código más severo).
- Pendiente: validar con lluvia medida (no hay mediciones de lluvia guardadas todavía).
