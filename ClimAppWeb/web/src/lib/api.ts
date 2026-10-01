// Respuestas comunes de la API. Los datos cambian como máximo cada hora (avisos) o cada 6 h
// (pronóstico): la CDN guarda las respuestas unos minutos y absorbe los picos de tráfico (RNF03).

import { RedisNotConfigured } from "./redis";

export const CACHE = {
  /** Pronóstico y avisos: 10 min en CDN, sirve la copia anterior hasta 1 h mientras revalida. */
  corto: "public, s-maxage=600, stale-while-revalidate=3600",
  /** Índice de ubicaciones: cambia solo con el catálogo. */
  largo: "public, s-maxage=86400, stale-while-revalidate=604800",
  ninguno: "no-store",
};

export function json(data: unknown, cache: string, status = 200) {
  return Response.json(data, { status, headers: { "Cache-Control": cache } });
}

export function notFound(message: string) {
  return json({ error: message }, CACHE.corto, 404);
}

export function serverError(error: unknown) {
  if (error instanceof RedisNotConfigured) {
    return json({ error: "Datos no disponibles: Redis no configurado" }, CACHE.ninguno, 503);
  }
  console.error(error);
  return json({ error: "Error al leer los datos" }, CACHE.ninguno, 502);
}
