// Tipos y acceso a los datos precalculados por el ETL (ver ClimAppWeb/etl/src/climapp_etl/snapshot.py).

import { getJson } from "./redis";

export type Aviso = {
  id: string;
  tipo: string;
  titulo: string;
  zona: string;
  emitido: string;
  url: string;
  documento: string | null;
  ubicaciones: string[];
};

export type AvisosPayload = { generado: string; avisos: Aviso[] };

export type UbicacionIndice = {
  slug: string;
  nombre: string;
  alias: string | null;
  region: string;
  costera: boolean;
};

export type Pronostico = {
  version: number;
  ubicacion: { slug: string; nombre: string; region: string; tipo: string; lat: number; lon: number; es_costera: boolean };
  generado: string;
  actualizado: string | null;
  provisional: boolean;
  modelos: string[];
  unidades: Record<string, string>;
  horas: Record<string, unknown>[];
  dias: Record<string, unknown>[];
  marino: { horas: Record<string, unknown>[]; dias: Record<string, unknown>[] } | null;
  observacion: Record<string, unknown> | null;
  fuentes: { nombre: string; licencia?: string; url: string }[];
};

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function isValidSlug(slug: string): boolean {
  return slug.length <= 60 && SLUG.test(slug);
}

/** Avisos vigentes sin la lista de ubicaciones (para incluirlos en una ubicación). */
function avisosDe(avisos: AvisosPayload | null, slug: string) {
  return (avisos?.avisos ?? [])
    .filter((a) => a.ubicaciones.includes(slug))
    .map((a) => ({ id: a.id, tipo: a.tipo, titulo: a.titulo, zona: a.zona, emitido: a.emitido,
                   url: a.url, documento: a.documento }));
}

/** Pronóstico de una ubicación con sus avisos vigentes, o null si no existe. */
export async function getPronostico(slug: string) {
  const [pronostico, avisos] = await getJson<[Pronostico, AvisosPayload]>(`loc:${slug}`, "avisos");
  if (!pronostico) return null;
  return { ...pronostico, avisos: avisosDe(avisos, slug) };
}

export async function getAvisos(slug?: string) {
  const [avisos] = await getJson<[AvisosPayload]>("avisos");
  if (!slug) return avisos;
  return { generado: avisos?.generado ?? null, avisos: avisosDe(avisos, slug) };
}

export async function getIndice() {
  const [indice] = await getJson<[UbicacionIndice[]]>("indice");
  return indice;
}

export async function getMeta() {
  const [meta] = await getJson<[{ generado: string; ubicaciones: number }]>("meta");
  return meta;
}
