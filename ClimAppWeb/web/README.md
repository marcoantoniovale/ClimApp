# web

Frontend (semana 4) y API de ClimApp. Next.js 16 (App Router) + Tailwind v4.

> Next.js 16 trae cambios respecto de versiones anteriores: antes de escribir código, revisar la guía correspondiente en `node_modules/next/dist/docs/` (ver [AGENTS.md](AGENTS.md)).

## Desarrollo

```powershell
copy .env.example .env.local     # completar URL y token de solo lectura de Upstash
npm install
npm run dev                      # http://localhost:3000
npm run lint
npm run build
```

## API

Los datos los precalcula el ETL (`ClimAppWeb/etl`) y los publica en Upstash Redis. La API solo los lee; las respuestas llevan `Cache-Control` con `s-maxage` para que la CDN absorba los picos.

| Ruta | Contenido | Caché CDN |
|---|---|---|
| `GET /api/forecast/:slug` | Pronóstico de la ubicación (48 h, 7 días, oleaje si es costera, última observación) + avisos vigentes | 10 min |
| `GET /api/warnings` | Avisos vigentes de la Armada con las ubicaciones que cubren | 10 min |
| `GET /api/warnings/:slug` | Avisos vigentes de una ubicación | 10 min |
| `GET /api/locations` | Catálogo para el buscador (slug, nombre, alias, región, costera) | 1 día |
| `GET /api/health` | Antigüedad de los datos; 503 si tienen más de 8 h | sin caché |

Errores: `404` ubicación inexistente, `503` Redis no configurado o datos desactualizados, `502` error al leer Redis.

El formato del pronóstico está documentado en `ClimAppWeb/etl/src/climapp_etl/snapshot.py` (versión de esquema en el campo `version`).
