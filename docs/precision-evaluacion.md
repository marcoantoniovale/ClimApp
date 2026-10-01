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
