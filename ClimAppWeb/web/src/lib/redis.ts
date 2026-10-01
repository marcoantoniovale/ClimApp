// Lectura de Upstash Redis por su API REST (sin dependencias). Lo publica el ETL
// (ClimAppWeb/etl/src/climapp_etl/redis.py) con el prefijo climapp:v1.
//
// Variables de entorno (servidor): UPSTASH_REDIS_REST_URL y UPSTASH_REDIS_REST_READONLY_TOKEN.
// La web solo lee: se usa el token de solo lectura de Upstash.

const PREFIX = "climapp:v1";

export class RedisNotConfigured extends Error {}

export type ReadOptions = {
  /** Segundos que Next.js guarda la respuesta (páginas ISR). Sin valor: siempre se lee de Redis. */
  revalidate?: number;
};

function config() {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_READONLY_TOKEN ?? process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new RedisNotConfigured("Faltan UPSTASH_REDIS_REST_URL / token");
  return { url: url.replace(/\/$/, ""), token };
}

/** GET de varias claves (sin prefijo) en una sola petición. Devuelve el JSON de cada una o null. */
export async function getJson<T extends unknown[]>(
  keys: string[],
  options: ReadOptions = {},
): Promise<{ [K in keyof T]: T[K] | null }> {
  const { url, token } = config();
  const caching: RequestInit =
    options.revalidate !== undefined
      ? { cache: "force-cache", next: { revalidate: options.revalidate } }
      : { cache: "no-store" };
  const response = await fetch(`${url}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(keys.map((key) => ["GET", `${PREFIX}:${key}`])),
    ...caching,
  });
  if (!response.ok) throw new Error(`Upstash respondió ${response.status}`);
  const results = (await response.json()) as { result?: string | null; error?: string }[];
  return results.map((r) => {
    if (r.error) throw new Error(`Upstash: ${r.error}`);
    return r.result ? JSON.parse(r.result) : null;
  }) as { [K in keyof T]: T[K] | null };
}
