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
  // Desde la versión 2 del JSON:
  punto_rocio?: number | null;
  nubosidad?: number | null;
  visibilidad?: number | null;  // m (GFS)
  isoterma_0?: number | null;   // m
  nieve?: number | null;        // cm/h
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
  viento_dir?: number | null;
  nieve?: number | null;
  isoterma_0_min?: number | null;
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
  ubicacion: { slug: string; nombre: string; region: string; tipo: string; lat: number; lon: number; es_costera: boolean;
               altura_m?: number | null };
  generado: string;
  actualizado: string | null;
  provisional: boolean;
  modelos: string[];
  /** Inicio de la corrida de cada modelo (hora de Chile, ISO). Puede faltar en datos antiguos. */
  corridas?: Record<string, string>;
  unidades: Record<string, string>;
  horas: Hora[];
  dias: Dia[];
  marino: Marino | null;
  observacion: Observacion | null;
  fuentes: { nombre: string; licencia?: string; url: string }[];
  fuente?: { modelo: string; complementario: string };
  cercanas?: { slug: string; nombre: string; km: number }[];
  /** Algoritmo ClimApp: temperatura de ICON corregida con estaciones DMC cercanas. */
  correccion?: { aplicada: boolean; estaciones: { nombre: string; km: number }[]; franjas: Record<string, number> };
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

/**
 * El JSON se regenera con cada corrida: separa las horas ya pasadas (antes de la hora actual).
 * `horasPrevias` (hasta 3) no se muestran, pero la estimación minuto a minuto las usa para comparar
 * la última medición con la curva del pronóstico en ese instante.
 */
export function desdeAhora<T extends Pronostico>(p: T, ahora: Date = new Date()): T & { horasPrevias: Hora[] } {
  const inicio = new Date(ahora);
  inicio.setMinutes(0, 0, 0);
  const t = inicio.getTime();
  return {
    ...p,
    horas: p.horas.filter((h) => Date.parse(h.hora) >= t),
    horasPrevias: p.horas.filter((h) => Date.parse(h.hora) < t).slice(-3),
  };
}

// ---------------------------------------------------------------------------
// Pasos fronterizos

export type AlertaPaso = { fecha: string; nivel: "alerta" | "aviso"; tipo: string; texto: string };

export type PasoResumen = {
  slug: string;              // "paso-los-libertadores"
  nombre: string;
  region: string;
  altura_m: number | null;
  lat: number;
  lon: number;
  hoy: { estado_cielo: number | null; temperatura_max: number | null; temperatura_min: number | null;
         nieve: number | null; rafaga_max: number | null };
  alertas: AlertaPaso[];
};

export type PasoDmc = {
  emision: string | null;
  apreciacion: string | null;
  dias: { fecha: string | null; etiqueta: string | null; icono: string | null; texto: string | null; isoterma: string | null }[];
};

export const slugPaso = (ruta: string) => `paso-${ruta}`;
export const rutaPaso = (slug: string) => slug.replace(/^paso-/, "");

export async function getPasos(options?: ReadOptions) {
  const [pasos, dmc] = await getJson<[{ generado: string; pasos: PasoResumen[] }, { generado: string; pasos: Record<string, PasoDmc> }]>(
    ["pasos", "pasos_dmc"], options);
  return { pasos: pasos?.pasos ?? [], dmc: dmc?.pasos ?? {} };
}

/** Pronóstico ICON del paso (con sus alertas) y pronóstico oficial de la DMC. */
export async function getPaso(ruta: string, options?: ReadOptions) {
  const slug = slugPaso(ruta);
  const [pronostico, dmc] = await getJson<[Pronostico & { alertas?: AlertaPaso[] }, { pasos: Record<string, PasoDmc> }]>(
    [`loc:${slug}`, "pasos_dmc"], options);
  if (!pronostico || pronostico.ubicacion.tipo !== "paso") return null;
  return { p: { ...pronostico, avisos: [] as AvisoUbicacion[] }, alertas: pronostico.alertas ?? [], dmc: dmc?.pasos[slug] ?? null };
}
