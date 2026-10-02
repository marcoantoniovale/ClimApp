// Algoritmo ClimApp — temperatura actual minuto a minuto.
//
// 1. Curva: interpolación lineal del pronóstico horario (ya corregido con mediciones) entre la hora
//    anterior y la siguiente. A las 21:30, entre 14,9° (21:00) y 14,5° (22:00), da 14,7°.
// 2. Arranque desde la medición: si hay una medición cercana reciente (≤ 3 h), la diferencia entre lo
//    medido y la curva en ese instante se suma y se desvanece exponencialmente (τ = 3 h, la mitad en
//    ~2 h): la estimación parte de lo medido y converge a la tendencia del pronóstico.
// Se calcula en el navegador con la hora actual (la página puede venir de caché).

type Punto = { hora: string; temperatura: number | null; sensacion_termica?: number | null };
type Medicion = { hora: string; temperatura: number | null } | null | undefined;

const HORA_MS = 3_600_000;
const TAU_MS = 3 * HORA_MS;
const MAX_EDAD_MEDICION_MS = 3 * HORA_MS;

/** Valor de la curva horaria en el instante t (ms). Fuera del rango, el extremo más cercano. */
export function interpolar(horas: Punto[], campo: "temperatura" | "sensacion_termica", t: number): number | null {
  const pts = horas
    .map((h) => [Date.parse(h.hora), h[campo]] as const)
    .filter((p): p is readonly [number, number] => p[1] != null && !Number.isNaN(p[0]));
  if (pts.length === 0) return null;
  if (t <= pts[0][0]) return pts[0][1];
  for (let i = 0; i < pts.length - 1; i++) {
    const [t0, v0] = pts[i];
    const [t1, v1] = pts[i + 1];
    if (t >= t0 && t <= t1) return v0 + ((v1 - v0) * (t - t0)) / (t1 - t0);
  }
  return pts[pts.length - 1][1];
}

const redondear = (v: number) => Math.round(v * 10) / 10;

/**
 * Temperatura y sensación térmica estimadas para el instante t (ms).
 * `ajustada` indica si se partió de una medición reciente.
 */
export function estimacionActual(horas: Punto[], medicion: Medicion, t: number) {
  const curva = interpolar(horas, "temperatura", t);
  const sensacion = interpolar(horas, "sensacion_termica", t);
  if (curva == null) return null;

  let ajuste = 0;
  if (medicion?.temperatura != null) {
    const tm = Date.parse(medicion.hora);
    const edad = t - tm;
    const curvaEnMedicion = interpolar(horas, "temperatura", tm);
    if (edad >= 0 && edad <= MAX_EDAD_MEDICION_MS && curvaEnMedicion != null) {
      ajuste = (medicion.temperatura - curvaEnMedicion) * Math.exp(-edad / TAU_MS);
    }
  }
  return {
    temperatura: redondear(curva + ajuste),
    sensacion_termica: sensacion == null ? null : redondear(sensacion + ajuste),
    ajustada: ajuste !== 0,
  };
}

// ---------------------------------------------------------------------------
// Reloj por minuto para componentes cliente (sin desajustes de hidratación: en el servidor es null).

const suscriptores = new Set<() => void>();
let intervalo: ReturnType<typeof setInterval> | null = null;

function suscribir(cb: () => void) {
  suscriptores.add(cb);
  intervalo ??= setInterval(() => suscriptores.forEach((s) => s()), 15_000);
  return () => {
    suscriptores.delete(cb);
    if (suscriptores.size === 0 && intervalo) {
      clearInterval(intervalo);
      intervalo = null;
    }
  };
}

/** Minuto actual (ms al inicio del minuto) en el navegador; null durante el render en el servidor. */
export const minutoActual = () => Math.floor(Date.now() / 60_000) * 60_000;
export const minutoServidor = () => null;
export { suscribir as suscribirMinuto };
