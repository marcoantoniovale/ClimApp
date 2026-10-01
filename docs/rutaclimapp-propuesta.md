# RutaClimApp — propuesta y mapeo

Fecha: 2026-10-01. Estado: **propuesta, pendiente de decisiones** (§8).

Funcionalidad para viajeros y transportistas: el usuario ingresa origen (lugar y hora de salida), destino y paradas opcionales; ClimApp estima dónde estará cada 15 minutos y entrega el pronóstico en ese punto y a esa hora.

---

## 1. Requisito nuevo (para agregar al SRS)

**RF06 — Pronóstico en ruta**
- RF06.1 Ingresar origen (comuna o ubicación actual) con fecha y hora de salida, destino y hasta 8 paradas intermedias, cada una con tiempo de detención.
- RF06.2 Calcular la ruta por carretera y la hora estimada de paso por cada punto; permitir ajustar la hora de llegada o salida en cada parada y recalcular lo que sigue.
- RF06.3 Entregar, cada 15 minutos de viaje, la ubicación estimada (comuna, ruta, km) y el pronóstico: temperatura, estado del cielo, lluvia, viento y ráfagas, visibilidad y riesgo de nieve o hielo.
- RF06.4 Destacar los tramos críticos (lluvia intensa, ráfagas fuertes, niebla, nieve o heladas) y los avisos de la Armada vigentes en comunas costeras de la ruta.
- RF06.5 Perfil auto o camión (velocidades y rutas aptas distintas).

## 2. Flujo de usuario

```
/ruta
┌───────────────────────────────────────────────┐
│ Salida   [Santiago ▾]  [mié 2 oct] [06:00]     │
│ + Agregar parada                               │
│   Parada 1 [Los Vilos ▾]  llegada ~08:45  ⏱ 30 min  (editable)
│ Destino  [La Serena ▾]  llegada estimada ~11:20│
│ Vehículo (•) Auto  ( ) Camión                  │
│                          [Ver clima en la ruta]│
└───────────────────────────────────────────────┘
Resultado
  Resumen: 5 h 20 min · 472 km · 2 tramos de atención
  ⚠ 09:30–10:15  Ruta 5, km 240–290 (Canela): niebla, visibilidad < 1 km
  Línea de tiempo (cada 15 min)
  06:00  Santiago            12°  ☁  0 %  viento 8 km/h
  06:15  Lampa · Ruta 5 km 25 12°  ☁  0 %  …
  …
  Gráfico: temperatura y probabilidad de lluvia a lo largo del viaje (eje: hora / km)
  [Compartir enlace]
```

- La hora de cada parada se calcula sola; el usuario puede **editar la llegada o la detención** y el resto del itinerario se recalcula (RF06.2).
- El enlace para compartir lleva los parámetros en la URL, sin cuentas ni almacenamiento.

## 3. Arquitectura

```
Navegador ──POST /api/ruta──▶ Vercel (gru1)
                               │ 1. Ruta: openrouteservice (geometría + tiempos)   ← caché Redis 24 h
                               │ 2. Muestreo: posición estimada cada 15 min (+ paradas)
                               │ 3. Clima por punto: corredor precalculado en Redis
                               │    (si el punto está lejos del corredor: comuna más cercana)
                               ▼
                          JSON: tramos, línea de tiempo, alertas
ETL (cada hora, ya existe) ──▶ job "corredor": Open-Meteo 15 min en ~350 puntos de rutas principales ──▶ Redis
```

Se mantiene el principio actual (RNF04): **las peticiones de usuarios no llaman a Open-Meteo**; el clima se precalcula. La única llamada externa por consulta es la de ruteo, con caché.

### 3.1 Ruteo — openrouteservice (recomendado)

| Opción | Costo / límites | Comentario |
|---|---|---|
| **openrouteservice** (HeiGIT, datos OSM) | Gratis: 2.000 rutas/día, 40/min | Perfil `driving-hgv` para camiones; devuelve geometría y duración por tramo. Requiere API key (cuenta gratuita). |
| OSRM demo público | Gratis | No apto para producción (política de uso). |
| OSRM propio | VM + mantenimiento | Control total; costo y operación. Opción para más adelante. |
| Mapbox / Google | Pago por uso | Mejor tráfico; costo y términos. |

Con caché de 24 h por combinación de puntos, 2.000 rutas/día alcanzan holgadamente para el MVP.

### 3.2 Clima en la ruta — tres opciones

| Opción | Precisión en ruta | Costo Open-Meteo | Recomendación |
|---|---|---|---|
| A. Pronóstico de la comuna más cercana (ya existe) | Baja en comunas grandes: Antofagasta, Calama o Aysén tienen cientos de km de ruta lejos de la cabecera; no ve pasos cordilleranos | 0 | Solo como respaldo |
| B. Open-Meteo en cada punto, por consulta | Alta | ~40 llamadas por ruta; no escala; contradice RNF04 | No |
| **C. Corredor precalculado** | Alta en rutas principales | ~1.700 llamadas/día (§3.3) | **Sí** |

**Corredor (opción C):** puntos cada ~20 km sobre las rutas principales, con el pronóstico cada 15 min precalculado por el ETL:
- Ruta 5 (Arica–Quellón), 68 (Santiago–Valparaíso), 60 CH (Los Libertadores), 78 (Santiago–San Antonio), Ruta 1 costera, transversales a las capitales regionales, Carretera Austral (Ruta 7) y Ruta 9 (Magallanes).
- Cada punto lleva precalculadas su comuna (por polígono), la ruta y el km.
- Tamaño estimado: **~350 puntos** (a medir al generar la geometría).
- Los puntos de una ruta a más de 15 km del corredor usan los datos de la comuna (opción A) y se marcan como "estimación por comuna".

### 3.3 Variables y costo

Por punto del corredor, un modelo (`best_match`), 2 días a 15 min y 5 días horarios:
- 15 min: temperatura, precipitación, estado del cielo, viento, ráfagas, visibilidad.
- Horario: probabilidad de lluvia, nieve, altura de la isoterma 0 °C (para pasos cordilleranos).

Verificado en el paso Los Libertadores: Open-Meteo entrega `minutely_15` sin vacíos para Chile, con visibilidad. En Chile esos datos son **interpolados de modelos horarios**; la interfaz debe decirlo ("estimación cada 15 min").

Costo: ~350 puntos × ~1,2 llamadas × 4 actualizaciones/día ≈ **1.700 llamadas/día**. Total del proyecto ≈ 6.300/día, bajo el límite gratuito de 10.000. Queda menos margen para crecer (ver riesgos).

### 3.4 Muestreo cada 15 minutos

1. openrouteservice devuelve la polilínea y, por tramo, distancia y duración.
2. Se reparte la duración de cada tramo a lo largo de sus segmentos según la distancia, obteniendo el "tiempo acumulado" en cada vértice.
3. Se insertan las detenciones de las paradas (horas ajustadas por el usuario).
4. Para t = salida, salida + 15 min, … llegada: posición por interpolación sobre la polilínea, km recorrido y corredor más cercano.
5. Clima en (punto, t): interpolación lineal entre los pasos de 15 min del punto del corredor (temperatura, viento); el más cercano para valores por categoría (estado del cielo).
6. Reglas de **tramo crítico** (umbrales a validar): precipitación > 2 mm/h, ráfagas > 60 km/h, visibilidad < 1.000 m, temperatura ≤ 0 °C con precipitación, isoterma 0 °C por debajo de la altura del punto (pasos).

Camión: perfil `driving-hgv` de openrouteservice y, opcionalmente, un factor de velocidad ajustable.

### 3.5 Contrato de la API (borrador)

```http
POST /api/ruta
{
  "perfil": "auto" | "camion",
  "salida": "2026-10-02T06:00:00-03:00",
  "puntos": [
    { "slug": "santiago" },
    { "slug": "los-vilos", "detencion_min": 30, "llegada": "2026-10-02T08:45:00-03:00" },
    { "slug": "la-serena" }
  ]
}
→ 200
{
  "resumen": { "distancia_km": 472, "duracion_min": 320, "llegada": "…", "alertas": 2 },
  "paradas": [ { "slug": "los-vilos", "llegada": "…", "salida": "…" } ],
  "linea_tiempo": [
    { "hora": "…06:00", "lat": -33.44, "lon": -70.65, "km": 0, "comuna": "santiago", "ruta": "Ruta 5",
      "fuente": "corredor" | "comuna",
      "temperatura": 12.1, "estado_cielo": 3, "precipitacion": 0, "precip_prob": 5,
      "viento": 8, "rafaga": 15, "visibilidad": 10000, "alerta": null }
  ],
  "tramos_criticos": [ { "desde": "…", "hasta": "…", "km": [240, 290], "motivo": "niebla" } ],
  "avisos": [ … avisos de la Armada en comunas costeras de la ruta … ]
}
```

Validaciones: máximo 10 puntos; salida entre ahora y +7 días (resolución de 15 min solo en las primeras 48 h; después, horaria y marcada como menos confiable).

## 4. Componentes a construir

| Pieza | Dónde | Reutiliza |
|---|---|---|
| Geometría del corredor (una vez, script) | `etl/scripts/build_corredor.py` | openrouteservice, polígonos de `build_coast.py` |
| Job `corredor` (cada corrida nueva o cada 6 h) | `etl/src/climapp_etl/jobs.py` | `open_meteo`, `redis`, `auto` |
| Cliente de ruteo + caché | `web/src/lib/ruteo.ts` | `redis.ts` |
| Muestreo y reglas de alerta | `web/src/lib/ruta.ts` (+ pruebas `node --test`) | `geo.ts` |
| `POST /api/ruta` | `web/src/app/api/ruta/route.ts` | `api.ts` |
| Página `/ruta` | `web/src/app/ruta/page.tsx` + componentes | `Search`, `WeatherIcon`, colores validados |
| Navegación | `Header`, `BottomNav` (nueva entrada "Ruta") | — |

## 5. Plan por etapas

| Etapa | Alcance | Estimación |
|---|---|---|
| **R1 — MVP** | Cuenta openrouteservice; corredor de Ruta 5 + 68 + 60 CH; job ETL; `/api/ruta`; página con formulario, paradas con hora editable, línea de tiempo cada 15 min, tramos críticos, perfil auto/camión, enlace para compartir | ~2,5–3 semanas |
| R2 — Cobertura y mapa | Resto del corredor (transversales, Ruta 1, Carretera Austral, Ruta 9); mapa de la ruta con tramos coloreados (adelanta parte de RF05.4); rutas guardadas en el dispositivo | ~1,5 semanas |
| R3 — Condiciones de ruta | Estado de pasos fronterizos y cortes (fuentes oficiales a investigar), barcazas de la Carretera Austral, rutas que cruzan Argentina hacia Magallanes | a evaluar |

## 6. Riesgos y limitaciones

- **No es tráfico en tiempo real:** las horas son estimaciones de openrouteservice; no incluye congestión, obras ni controles. El usuario corrige con las horas editables.
- **15 minutos interpolados:** en Chile los modelos son horarios; la resolución de 15 min es una estimación y así se informa.
- **Rutas fuera de Chile:** para llegar por tierra a Magallanes hay que pasar por Argentina, donde no tenemos corredor (los puntos se marcan "sin cobertura" en R1). Las barcazas (Chacao, Carretera Austral) no se modelan.
- **Cuota de Open-Meteo:** el corredor sube el uso a ~63 % del límite gratuito. Si crece el corredor o el tráfico, evaluar el plan pagado; también obligatorio si hay monetización (uso comercial).
- **Seguridad vial:** el pronóstico no reemplaza a Vialidad, Carabineros ni la Unidad de Pasos Fronterizos. Aviso visible en la página.
- **Privacidad:** origen y destino se envían a openrouteservice para calcular la ruta; indicarlo en la página. No se guardan en nuestros servidores (solo la ruta calculada en caché, sin datos del usuario).

## 7. Relación con el plan actual

- La Fase 2 (ensemble con corrección de sesgo) está **bloqueada por la recolección de observaciones de la Armada**. RutaClimApp no depende de eso y puede avanzar en paralelo.
- Usa la misma infraestructura (ETL horario, Redis, Vercel); no requiere servicios nuevos salvo la cuenta de openrouteservice.

## 8. Decisiones pendientes

1. **¿Se aprueba RutaClimApp y su prioridad** frente a la Fase 2?
2. **Ruteo:** openrouteservice (recomendado). Requiere crear una cuenta gratuita y una API key.
3. **Clima:** corredor precalculado (opción C) con respaldo por comuna.
4. **Perfil camión** en el MVP (recomendado: sí, lo da openrouteservice sin costo extra).
5. **Mapa** en R1 o en R2 (recomendado: R2, para salir antes).
6. **Horizonte:** hasta 7 días, con 15 min solo en las primeras 48 h.
