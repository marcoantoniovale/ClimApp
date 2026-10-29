// Lectura de Upstash Redis por su API REST (sin dependencias). Lo publica el ETL
// (ClimAppWeb/etl/src/climapp_etl/redis.py) con el prefijo climapp:v1.
//
// Variables de entorno (servidor): UPSTASH_REDIS_REST_URL y UPSTASH_REDIS_REST_READONLY_TOKEN.
// La web solo lee: se usa el token de solo lectura de Upstash.
// Los valores grandes vienen comprimidos ("gz:" + gzip en base64) para no agotar el plan de Upstash.
//
// Respaldo: si Upstash falla (p. ej. plan agotado) o no está configurado, las mismas claves se leen de la
// etiqueta `datos` del repositorio en GitHub (la sube el ETL: etl/scripts/publicar_respaldo.sh), como
// JSON plano en <clave con ":" → "/">.json. CLIMAPP_RESPALDO_URL permite cambiar el origen.
//
// Claves por ubicación (loc:…, lugares:…): desde el 2026-10-29 solo están en GitHub (no en Upstash). Se
// leen con getPorUbicacion() en el commit exacto que indica la clave global `respaldo` (URL inmutable:
// siempre la versión correcta y en caché indefinida); si raw.githubusercontent.com falla, desde jsDelivr.

import { gunzipSync } from "node:zlib";

const PREFIX = "climapp:v1";

/** Etiqueta de la caché de datos de Next.js; /api/revalidate la expira cuando el ETL publica. */
export const CACHE_TAG = "climapp";

const REPO = "marcoantoniovale/ClimApp";
const RESPALDO_URL = (process.env.CLIMAPP_RESPALDO_URL ?? `https://raw.githubusercontent.com/${REPO}/datos`).replace(/\/$/, "");
const COMMIT = /^[0-9a-f]{40}$/;

export class RedisNotConfigured extends Error {}

/** Clave sin prefijo → archivo del respaldo (loc:quintero → loc/quintero.json); igual que el ETL. */
export const rutaRespaldo = (key: string) => `${key.replaceAll(":", "/")}.json`;

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

/** Valor guardado por el ETL → JSON (descomprime los que empiezan con "gz:"). */
export function decodificar(valor: string): unknown {
  const texto = valor.startsWith("gz:") ? gunzipSync(Buffer.from(valor.slice(3), "base64")).toString("utf8") : valor;
  return JSON.parse(texto);
}

type Resultado<T extends unknown[]> = { [K in keyof T]: T[K] | null };

function cacheDe(options: ReadOptions): RequestInit {
  return options.revalidate !== undefined
    ? { cache: "force-cache", next: { revalidate: options.revalidate, tags: [CACHE_TAG] } }
    : { cache: "no-store" };
}

export async function deRedis<T extends unknown[]>(keys: string[], options: ReadOptions): Promise<Resultado<T>> {
  const { url, token } = config();
  const response = await fetch(`${url}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(keys.map((key) => ["GET", `${PREFIX}:${key}`])),
    ...cacheDe(options),
  });
  if (!response.ok) throw new Error(`Upstash respondió ${response.status}`);
  const results = (await response.json()) as { result?: string | null; error?: string }[];
  return results.map((r) => {
    if (r.error) throw new Error(`Upstash: ${r.error}`);
    return r.result ? decodificar(r.result) : null;
  }) as Resultado<T>;
}

/** Las mismas claves desde el respaldo en GitHub (null si el archivo no existe). */
export async function deRespaldo<T extends unknown[]>(keys: string[], options: ReadOptions = {}): Promise<Resultado<T>> {
  return (await Promise.all(keys.map(async (key) => {
    const response = await fetch(`${RESPALDO_URL}/${rutaRespaldo(key)}`, cacheDe(options));
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Respaldo respondió ${response.status} (${key})`);
    return response.json();
  }))) as Resultado<T>;
}

/** Origen del respaldo en un commit (inmutable), en orden de preferencia. */
export const origenesCommit = (sha: string) =>
  [`https://raw.githubusercontent.com/${REPO}/${sha}`, `https://cdn.jsdelivr.net/gh/${REPO}@${sha}`];

async function leerArchivo(bases: string[], key: string, caching: RequestInit): Promise<unknown> {
  let ultimo: unknown;
  for (const base of bases) {
    try {
      const response = await fetch(`${base}/${rutaRespaldo(key)}`, caching);
      if (response.status === 404) return null;
      if (response.ok) return await response.json();
      ultimo = new Error(`${base} respondió ${response.status} (${key})`);
    } catch (error) {
      ultimo = error;
    }
  }
  throw ultimo;
}

/**
 * Claves por ubicación (loc:…, lugares:…) desde GitHub, en el commit que publica el ETL (clave global
 * `respaldo`). Sin esa clave (p. ej. Upstash caído), desde la etiqueta `datos`.
 */
export async function getPorUbicacion<T extends unknown[]>(keys: string[], options: ReadOptions = {}): Promise<Resultado<T>> {
  const [respaldo] = await getJson<[{ sha?: string }]>(["respaldo"], options).catch(() => [null]);
  const sha = respaldo?.sha && COMMIT.test(respaldo.sha) ? respaldo.sha : null;
  // Un commit no cambia: se guarda un día en la caché de datos (una versión nueva es otra URL).
  const caching: RequestInit = sha ? { cache: "force-cache", next: { revalidate: 86_400 } } : cacheDe(options);
  const bases = sha ? origenesCommit(sha) : [RESPALDO_URL];
  return (await Promise.all(keys.map((key) => leerArchivo(bases, key, caching)))) as Resultado<T>;
}

/**
 * GET de varias claves (sin prefijo) en una sola petición. Devuelve el JSON de cada una o null.
 * Si Upstash falla, las lee del respaldo en GitHub (salvo `respaldo: false`).
 */
export async function getJson<T extends unknown[]>(
  keys: string[],
  options: ReadOptions & { respaldo?: boolean } = {},
): Promise<Resultado<T>> {
  try {
    return await deRedis<T>(keys, options);
  } catch (error) {
    if (options.respaldo === false) throw error;
    console.warn(`Redis no disponible (${error instanceof Error ? error.message : error}); se usa el respaldo`);
    return deRespaldo<T>(keys, options);
  }
}
