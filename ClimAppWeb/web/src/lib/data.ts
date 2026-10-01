// Tipos y acceso a los datos precalculados por el ETL (ver ClimAppWeb/etl/src/climapp_etl/snapshot.py).

import { getJson, type ReadOptions } from "./redis";

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

export type AvisoUbicacion = Omit<Aviso, "ubicaciones">;

export type AvisosPayload = { generado: string; avisos: Aviso[] };

export type UbicacionIndice = {
  slug: string;
  nombre: string;
  alias: string | null;
  region: string;
  costera: boolean;
  /** Cabecera comunal (para "Usar mi ubicación"); puede faltar en índices antiguos. */
  lat?: number;
  lon?: number;
};

export type Hora = {
  hora: string;
  temperatura: number | null;
  rango: [number | null, number | null];
  sensacion_termica: number | null;
  estado_cielo: number | null;
  indice_uv: number | null;
  humedad: number | null;
  precip_prob: number | null;
  precipitacion: number | null;
  viento: number | null;
  viento_dir: number | null;
  rafaga: number | null;
  presion: number | null;
};

export type Dia = {
  fecha: string;
  temperatura_max: number | null;
  temperatura_min: number | null;
  rango_max: [number, number] | null;
  rango_min: [number, number] | null;
  estado_cielo: number | null;
  precip_prob: number | null;
  precipitacion: number | null;
  viento_max: number | null;
  rafaga_max: number | null;
  indice_uv_max: number | null;
  horas: number;
};

export type Marino = {
  horas: { hora: string; altura: number | null; periodo: number | null; direccion: number | null; marejada: number | null }[];
  dias: { fecha: string; altura_max: number | null; periodo_max: number | null; direccion: number | null }[];
};

export type Observacion = {
  estacion: string;
  red: string;
  hora: string;
  temperatura: number | null;
  humedad: number | null;
  presion: number | null;
  viento: number | null;
  viento_dir: number | null;
};

export type Pronostico = {
  version: number;
  ubicacion: { slug: string; nombre: string; region: string; tipo: string; lat: number; lon: number; es_costera: boolean };
  generado: string;
  actualizado: string | null;
  provisional: boolean;
  modelos: string[];
  unidades: Record<string, string>;
  horas: Hora[];
  dias: Dia[];
  marino: Marino | null;
  observacion: Observacion | null;
  fuentes: { nombre: string; licencia?: string; url: string }[];
};

export type PronosticoConAvisos = Pronostico & { avisos: AvisoUbicacion[] };

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function isValidSlug(slug: string): boolean {
  return slug.length <= 60 && SLUG.test(slug);
}

/** Avisos vigentes sin la lista de ubicaciones (para incluirlos en una ubicación). */
function avisosDe(avisos: AvisosPayload | null, slug: string): AvisoUbicacion[] {
  return (avisos?.avisos ?? [])
    .filter((a) => a.ubicaciones.includes(slug))
    .map((a) => ({ id: a.id, tipo: a.tipo, titulo: a.titulo, zona: a.zona, emitido: a.emitido,
                   url: a.url, documento: a.documento }));
}

/** Pronóstico de una ubicación con sus avisos vigentes, o null si no existe. */
export async function getPronostico(slug: string, options?: ReadOptions): Promise<PronosticoConAvisos | null> {
  const [pronostico, avisos] = await getJson<[Pronostico, AvisosPayload]>([`loc:${slug}`, "avisos"], options);
  if (!pronostico) return null;
  return { ...pronostico, avisos: avisosDe(avisos, slug) };
}

/** Todos los avisos vigentes, con las ubicaciones que cubre cada uno. */
export async function getAvisos(options?: ReadOptions) {
  const [avisos] = await getJson<[AvisosPayload]>(["avisos"], options);
  return avisos;
}

/** Avisos vigentes que cubren una ubicación. */
export async function getAvisosDe(slug: string, options?: ReadOptions) {
  const avisos = await getAvisos(options);
  return { generado: avisos?.generado ?? null, avisos: avisosDe(avisos, slug) };
}

export async function getIndice(options?: ReadOptions) {
  const [indice] = await getJson<[UbicacionIndice[]]>(["indice"], options);
  return indice;
}

export async function getMeta(options?: ReadOptions) {
  const [meta] = await getJson<[{ generado: string; ubicaciones: number }]>(["meta"], options);
  return meta;
}
