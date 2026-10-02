// Algoritmo ClimApp v2 en el navegador (el detalle del cálculo está en etl/src/climapp_etl/correccion.py).
//
// 1. Curva: interpolación lineal del pronóstico horario, que ya viene corregido con el sesgo aprendido de
//    las estaciones cercanas (DMC y SINCA). A las 21:30, entre 14,9° (21:00) y 14,5° (22:00), da 14,7°.
// 2. Ancla: la anomalía del momento (lo medido menos la curva corregida, interpolado desde las estaciones
//    por cuadrantes) se suma y se desvanece exponencialmente con τ, que el ETL ajusta cada día con la
//    persistencia observada. Así la temperatura parte de lo medido y vuelve a la curva.
// 3. El mismo ajuste se aplica al hora a hora (ajustarHoras) y a las máximas y mínimas (ajustarDias),
//    para que todo cuente la misma historia.
// Se calcula con la hora del navegador (la página puede venir de caché).

type Punto = { hora: string; temperatura: number | null; sensacion_termica?: number | null };
type DiaTemp = { fecha: string; temperatura_max: number | null; temperatura_min: number | null };

/** Anomalía del momento en la comuna (clave `algoritmo` de Redis). */
export type Ancla = { anomalia: number; hora: string; tau_h: number } | null | undefined;

const HORA_MS = 3_600_000;
const MAX_EDAD_ANCLA_MS = 6 * HORA_MS;
const ADELANTO_MS = 15 * 60_000;   // tolera relojes algo adelantados respecto del ETL

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

/** ¿El ancla sirve en el instante `ahora`? (no más de 6 h de antigüedad). */
function anclaVigente(ancla: Ancla, ahora: number): ancla is NonNullable<Ancla> {
  if (!ancla || !Number.isFinite(ancla.anomalia)) return false;
  const edad = ahora - Date.parse(ancla.hora);
  return edad >= -ADELANTO_MS && edad <= MAX_EDAD_ANCLA_MS;
}

/** °C a sumar a la curva en el instante t: la anomalía desvanecida desde la hora del ancla. */
function ajusteEn(ancla: NonNullable<Ancla>, t: number): number {
  const edad = Math.max(0, t - Date.parse(ancla.hora));
  return ancla.anomalia * Math.exp(-edad / (Math.max(ancla.tau_h, 1) * HORA_MS));
}

/**
 * Temperatura y sensación térmica estimadas para el instante t (ms).
 * `ajustada` indica si se partió de las mediciones del momento.
 */
export function estimacionActual(horas: Punto[], ancla: Ancla, t: number) {
  const curva = interpolar(horas, "temperatura", t);
  const sensacion = interpolar(horas, "sensacion_termica", t);
  if (curva == null) return null;
  const ajuste = anclaVigente(ancla, t) ? ajusteEn(ancla, t) : 0;
  return {
    temperatura: redondear(curva + ajuste),
    sensacion_termica: sensacion == null ? null : redondear(sensacion + ajuste),
    ajustada: ajuste !== 0,
  };
}

/** Horas del pronóstico con el ajuste del momento (para que no contradigan la temperatura actual). */
export function ajustarHoras<T extends Punto>(horas: T[], ancla: Ancla, ahora: number): T[] {
  if (!anclaVigente(ancla, ahora)) return horas;
  return horas.map((h) => {
    const ajuste = ajusteEn(ancla, Date.parse(h.hora));
    if (Math.abs(ajuste) < 0.05) return h;
    return {
      ...h,
      temperatura: h.temperatura == null ? null : redondear(h.temperatura + ajuste),
      sensacion_termica: h.sensacion_termica == null ? h.sensacion_termica : redondear(h.sensacion_termica + ajuste),
    };
  });
}

/**
 * Máximas y mínimas con el mismo ajuste: se suma el ajuste de la hora en que el pronóstico pone la
 * máxima (o la mínima) del día, si esa hora aún no pasa. Si ya pasó, queda como estaba.
 */
export function ajustarDias<D extends DiaTemp>(dias: D[], horas: Punto[], ancla: Ancla, ahora: number,
                                               fechaDe: (iso: string) => string): D[] {
  if (!anclaVigente(ancla, ahora)) return dias;
  return dias.map((d) => {
    const delDia = horas.filter((h) => h.temperatura != null && fechaDe(h.hora) === d.fecha);
    if (delDia.length === 0) return d;
    const ajusteDe = (h: Punto, extremo: number | null) =>
      extremo != null && Math.abs(h.temperatura! - extremo) <= 1 ? ajusteEn(ancla, Date.parse(h.hora)) : 0;
    const hMax = delDia.reduce((a, b) => (b.temperatura! > a.temperatura! ? b : a));
    const hMin = delDia.reduce((a, b) => (b.temperatura! < a.temperatura! ? b : a));
    const aMax = ajusteDe(hMax, d.temperatura_max);
    const aMin = ajusteDe(hMin, d.temperatura_min);
    if (Math.abs(aMax) < 0.05 && Math.abs(aMin) < 0.05) return d;
    return {
      ...d,
      temperatura_max: d.temperatura_max == null ? null : redondear(d.temperatura_max + aMax),
      temperatura_min: d.temperatura_min == null ? null : redondear(d.temperatura_min + aMin),
    };
  });
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
