// Algoritmo ClimApp — temperatura actual minuto a minuto.
//
// 1. Curva: interpolación lineal del pronóstico horario (ya corregido con mediciones) entre la hora
//    anterior y la siguiente. A las 21:30, entre 14,9° (21:00) y 14,5° (22:00), da 14,7°.
// 2. Arranque desde la medición: si hay una medición cercana reciente (≤ 6 h), la diferencia entre lo
//    medido y la curva en ese instante se suma y se desvanece exponencialmente (τ = 20 h): la estimación
//    parte de lo medido y sigue la tendencia del pronóstico. τ medido en 134 estaciones DMC: el error de
//    ICON persiste (factor 0,95 a 1 h, 0,86 a 3 h, 0,73 a 6 h); con τ = 20 h el error a 1 h baja de
//    1,84 °C (solo la curva) a ~0,7 °C. Con τ = 3 h quedaba en 0,83 °C a 1 h y 1,45 °C a 3 h.
// 3. El mismo ajuste se aplica a las próximas horas del pronóstico hora a hora (ajustarHoras).
// Se calcula en el navegador con la hora actual (la página puede venir de caché).

type Punto = { hora: string; temperatura: number | null; sensacion_termica?: number | null };
type Medicion = { hora: string; temperatura: number | null } | null | undefined;

const HORA_MS = 3_600_000;
const TAU_MS = 20 * HORA_MS;
const MAX_EDAD_MEDICION_MS = 6 * HORA_MS;

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

/** Diferencia medición − curva en el instante t (ms), ya desvanecida; 0 si no hay medición útil. */
function ajusteEn(horas: Punto[], medicion: Medicion, t: number): number {
  if (medicion?.temperatura == null) return 0;
  const tm = Date.parse(medicion.hora);
  const edad = t - tm;
  const curvaEnMedicion = interpolar(horas, "temperatura", tm);
  if (Number.isNaN(tm) || edad < 0 || curvaEnMedicion == null) return 0;
  return (medicion.temperatura - curvaEnMedicion) * Math.exp(-edad / TAU_MS);
}

/**
 * Temperatura y sensación térmica estimadas para el instante t (ms).
 * `ajustada` indica si se partió de una medición reciente.
 */
export function estimacionActual(horas: Punto[], medicion: Medicion, t: number) {
  const curva = interpolar(horas, "temperatura", t);
  const sensacion = interpolar(horas, "sensacion_termica", t);
  if (curva == null) return null;
  const ajuste = medicionVigente(medicion, t) ? ajusteEn(horas, medicion, t) : 0;
  return {
    temperatura: redondear(curva + ajuste),
    sensacion_termica: sensacion == null ? null : redondear(sensacion + ajuste),
    ajustada: ajuste !== 0,
  };
}

/** ¿La medición sirve de ancla en el instante t? (no es futura ni tiene más de 6 h). */
function medicionVigente(medicion: Medicion, t: number): boolean {
  if (medicion?.temperatura == null) return false;
  const edad = t - Date.parse(medicion.hora);
  return edad >= 0 && edad <= MAX_EDAD_MEDICION_MS;
}

/**
 * Horas del pronóstico con el ajuste de la medición (para que la tabla hora a hora no contradiga la
 * temperatura actual). `ahora` decide si la medición sigue vigente; `base` son las horas usadas para
 * la curva (incluye las previas a la medición).
 */
export function ajustarHoras<T extends Punto>(horas: T[], base: Punto[], medicion: Medicion, ahora: number): T[] {
  if (!medicionVigente(medicion, ahora)) return horas;
  return horas.map((h) => {
    const ajuste = ajusteEn(base, medicion, Date.parse(h.hora));
    if (ajuste === 0) return h;
    return {
      ...h,
      temperatura: h.temperatura == null ? null : redondear(h.temperatura + ajuste),
      sensacion_termica: h.sensacion_termica == null ? h.sensacion_termica : redondear(h.sensacion_termica + ajuste),
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
