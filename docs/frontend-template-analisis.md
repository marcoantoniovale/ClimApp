# Análisis de la plantilla de frontend (`Template/`)

Fecha: 2026-10-01. Material aportado por el usuario, generado con Gemini. Se adopta como **referencia de diseño** para la semana 4 de la Fase 1, con los ajustes indicados abajo.

## Contenido

| Archivo | Qué es |
|---|---|
| [ClimApp_frontend.docx](../Template/ClimApp_frontend.docx) | Propuesta de frontend: estructura de carpetas, `globals.css`, `layout.tsx`, `page.tsx`, `CurrentWeather.tsx`, `manifest.json` |
| [gemini-code-…txt](../Template/gemini-code-1790866648237.txt) | Solo el árbol de carpetas (igual al del .docx) |
| [climapp_logo.svg](../Template/climapp_logo.svg) | Logo 1024×1024: sol, nube y trazo de viento |
| [climapp_icon.svg](../Template/climapp_icon.svg) | Ícono 512×512 con esquinas redondeadas |
| [gemini-code-…py](../Template/gemini-code-1790867123964.py) | Genera `climapp_logo.png` y `climapp_icon.png` con Pillow |

## Lo que se adopta

- **Identidad visual**: fondo `#0F172A` (slate-900), acento turquesa `#0EA5E9` (sky-500), acento naranja `#F97316` (orange-500), texto `#F8FAFC`. Estilo oscuro, minimalista, tarjetas con borde sutil y desenfoque.
- **Logo e ícono** en SVG.
- **Diseño mobile-first** con navegación inferior en móvil (coherente con el uso en zonas costeras).
- **Instalable como PWA** (manifest + íconos).
- **Componentes**, que calzan con los requisitos:

| Componente de la plantilla | Requisito | Fase |
|---|---|---|
| `Header` (buscador + ubicación) | RF05.1 | 1 |
| `CurrentWeather` | RF05.2 | 1 (ajustado, ver abajo) |
| `HourlyForecast` (scroll horizontal) | RF05.2 | 1 |
| `WeeklyForecast` (7 días) | RF05.2 | 1 |
| `ClimateMetrics` (UV, humedad, viento, presión) | RF05.2 | 1 |
| `alerts/page.tsx` | RF05.2 (alertas marítimas) | 1 |
| `BottomNav` | — | 1 |
| `radar/page.tsx` (mapas) | RF05.4 | **3** — no se construye ahora |

## Ajustes necesarios

### Ubicación y estructura
1. El código va en `ClimAppWeb/web/` (no en `climapp-frontend/`), según la convención del proyecto.
2. Rutas por ubicación en vez de un dashboard fijo: `/` (inicio + buscador) y `/[tipo]/[slug]` (p. ej. `/comuna/valparaiso`), usando los slugs del catálogo.
3. Se agrega `app/api/` para los Route Handlers (`/api/forecast/[slug]`, `/api/warnings`).

### Datos y renderizado
4. La plantilla marca toda la página como `'use client'` con datos fijos ("Santiago, 22°"). Se cambia a **Server Components** que leen el JSON precalculado, con caché en CDN (RNF01, RNF03). Solo el buscador y los gráficos son componentes cliente.
5. **"Clima actual"**: no tenemos observación en cada comuna. Se muestra el pronóstico de la hora actual (promedio de modelos) y, si hay una estación Armada cercana con dato reciente, su observación aparte, indicando la fuente.
6. **Variables que la plantilla usa y el ETL aún no pide**: estado del cielo (`weather_code`), sensación térmica (`apparent_temperature`) e índice UV (`uv_index`). Se agregan al conector Open-Meteo de la semana 2. Impacto en la cuota: 11 variables × 3 modelos ≈ 3,3 llamadas por ubicación → ~4.600 llamadas/día (~137.000/mes, bajo el límite de 300.000).
7. **Elementos que faltan en la plantilla** y exige el diseño de la Fase 1:
   - Etiqueta "pronóstico provisional" y hora de la última actualización.
   - Banner de avisos marítimos vigentes en la página de la ubicación (no solo en `/alerts`).
   - Unidades de viento según la ubicación: km/h en tierra, nudos en la costa.
   - Atribución "Datos: Open-Meteo (CC BY 4.0)" y Armada de Chile en el pie de página.
   - Opcional: rango entre modelos (mín./máx.) para la vista de fiabilidad (RF05.3).

### Detalles técnicos
8. `globals.css` usa la sintaxis de **Tailwind v3** (`@tailwind base;`). Next.js crea hoy proyectos con **Tailwind v4** (`@import "tailwindcss";` y colores en `@theme`). Se adapta.
9. `themeColor` dentro de `metadata` está obsoleto en Next.js 14+; va en `export const viewport`.
10. Los colores están repetidos como valores fijos (`bg-[#0F172A]`); se definen una vez como colores del tema (`bg-climapp-bg`, `text-climapp-teal`, `text-climapp-sun`).
11. **Íconos PWA**: el manifest usa un solo PNG 512×512 con `"purpose": "any maskable"`. El ícono tiene esquinas transparentes, que Android recorta mal como *maskable*. Se generan: 192 y 512 normales y una versión *maskable* a sangre completa (sin esquinas redondeadas, con margen de seguridad). También `app/icon.svg` y `apple-icon.png`.
12. **Generación de PNG**: el script de Pillow redibuja las figuras en lugar de convertir el SVG, y el trazo de viento del logo no coincide con el SVG (el arco va de (238, 412) a (786, 412) en vez de (280, 400) a (720, 280)). Se toma el **SVG como fuente única** y los PNG se generan desde él con `sharp` (dependencia de Node, disponible en el proyecto web).
13. Accesibilidad: el texto gris (`slate-400`) sobre el fondo oscuro tiene contraste suficiente para texto normal; evitar `slate-500` o más oscuro para texto. Respetar `prefers-reduced-motion` en animaciones.

## Decisión

- `Template/` queda en el repositorio sin cambios, como material de referencia.
- Al crear `ClimAppWeb/web/` (semana 4) se copian los SVG a `web/public/brand/` y se implementan los componentes con los ajustes de este documento.
