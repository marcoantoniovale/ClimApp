// Salida y puesta del sol calculadas en el navegador (fórmulas astronómicas estándar de posición
// solar; error típico < 2 min). Sin llamadas a servicios externos.

const RAD = Math.PI / 180;
const DIA_MS = 86_400_000;
const J1970 = 2440588;
const J2000 = 2451545;
const OBLICUIDAD = RAD * 23.4397;
const J0 = 0.0009;
const ALTURA_SOL = -0.833 * RAD; // centro del sol bajo el horizonte, con refracción

const aJuliano = (fecha: Date) => fecha.getTime() / DIA_MS - 0.5 + J1970;
const deJuliano = (j: number) => new Date((j + 0.5 - J1970) * DIA_MS);
const anomaliaMedia = (d: number) => RAD * (357.5291 + 0.98560028 * d);
const longitudEcliptica = (M: number) =>
  M + RAD * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M)) + RAD * 102.9372 + Math.PI;
const declinacion = (L: number) => Math.asin(Math.sin(OBLICUIDAD) * Math.sin(L));
const transito = (ds: number, M: number, L: number) => J2000 + ds + 0.0053 * Math.sin(M) - 0.0069 * Math.sin(2 * L);

export type Sol = { salida: Date; puesta: Date; duracionMin: number } | null;

/**
 * Salida y puesta del sol para el día que contiene `dia` (se usa el mediodía de ese día) en (lat, lon).
 * Devuelve null si ese día el sol no sale o no se pone (latitudes polares, p. ej. la Antártica).
 */
export function salidaPuesta(dia: Date, lat: number, lon: number): Sol {
  const lw = RAD * -lon;
  const phi = RAD * lat;
  const d = aJuliano(dia) - J2000;
  const n = Math.round(d - J0 - lw / (2 * Math.PI));
  const ds = J0 + lw / (2 * Math.PI) + n;
  const M = anomaliaMedia(ds);
  const L = longitudEcliptica(M);
  const dec = declinacion(L);
  const mediodia = transito(ds, M, L);
  const cosH = (Math.sin(ALTURA_SOL) - Math.sin(phi) * Math.sin(dec)) / (Math.cos(phi) * Math.cos(dec));
  if (cosH < -1 || cosH > 1) return null;
  const w = Math.acos(cosH);
  const puesta = transito(J0 + (w + lw) / (2 * Math.PI) + n, M, L);
  const salida = mediodia - (puesta - mediodia);
  return {
    salida: deJuliano(salida),
    puesta: deJuliano(puesta),
    duracionMin: Math.round((puesta - salida) * 24 * 60),
  };
}
