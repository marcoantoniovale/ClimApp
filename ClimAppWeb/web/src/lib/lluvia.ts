// Lluvia medida en estaciones DMC (clave `lluvia`, job dmc_lluvia del ETL, cada hora).
// El cielo de "Ahora" es pronóstico de modelos; si la estación cercana midió lluvia en la última
// hora, manda la medición. Sin dependencias, para probarlo con node --test.

export type LluviaEstacion = {
  id: string;
  nombre: string;
  lat: number;
  lon: number;
  /** Fin de los períodos (hora de Chile, ISO); la DMC los renueva cada ~15 min. */
  hasta: string;
  mm_1h: number | null;
  mm_3h: number | null;
  mm_6h?: number | null;
  mm_24h?: number | null;
  /** Último minuto con lluvia según el pluviógrafo (o null). */
  ultima: string | null;
};

export type LluviaPayload = { generado: string; estaciones: LluviaEstacion[] };

/** Lluvia medida en la estación más cercana a una ubicación. */
export type LluviaMedida = LluviaEstacion & { km: number };

export const LLUVIA_MAX_KM = 15;      // la lluvia cambia mucho en pocos km: solo estaciones cercanas
export const LLUVIA_MAX_MIN = 120;    // una medición más antigua no describe el momento

/** Distancia en km (semiverseno; igual que lib/geo.ts). */
function distanciaKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(a));
}

/** La estación con lluvia medida más cercana a (lat, lon), hasta LLUVIA_MAX_KM, o null. */
export function lluviaCercana(payload: LluviaPayload | null | undefined, lat: number, lon: number): LluviaMedida | null {
  let mejor: LluviaMedida | null = null;
  for (const e of payload?.estaciones ?? []) {
    const km = distanciaKm(lat, lon, e.lat, e.lon);
    if (km <= LLUVIA_MAX_KM && (!mejor || km < mejor.km)) mejor = { ...e, km: Math.round(km * 10) / 10 };
  }
  return mejor;
}

export type EstadoLluvia = {
  /** Llovió en la última hora medida: el cielo de "Ahora" pasa a lluvia. */
  lloviendo: boolean;
  /** Código WMO equivalente a la intensidad medida (61 débil, 63 moderada, 65 fuerte), si llueve. */
  codigo: number | null;
  medida: LluviaMedida;
};

/**
 * Estado de la lluvia medida en el instante `ahoraMs`, o null si no hay medición vigente
 * (más de LLUVIA_MAX_MIN desde el fin del período) o si no hay nada que contar (sin lluvia en 3 h).
 */
export function estadoLluvia(medida: LluviaMedida | null | undefined, ahoraMs: number): EstadoLluvia | null {
  if (!medida) return null;
  const edad = (ahoraMs - Date.parse(medida.hasta)) / 60_000;
  if (!(edad <= LLUVIA_MAX_MIN && edad >= -30)) return null;
  const mm1 = medida.mm_1h ?? 0;
  if (mm1 > 0) return { lloviendo: true, codigo: mm1 >= 4 ? 65 : mm1 >= 0.5 ? 63 : 61, medida };
  if ((medida.mm_3h ?? 0) > 0) return { lloviendo: false, codigo: null, medida };
  return null;
}

/** "0,1 mm" (con espacio duro: el número no queda separado de su unidad). */
export const mm = (v: number | null | undefined) =>
  `${(v ?? 0).toLocaleString("es-CL", { maximumFractionDigits: 1 })}\u00a0mm`;
