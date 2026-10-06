// Próxima lluvia (vista de fiabilidad, RF05.3): cuándo empieza la lluvia de consenso y en qué rango de horas
// la empiezan los modelos. La calcula el ETL (snapshot.proxima_lluvia); aquí solo se arma el texto con la
// hora real del navegador (el JSON puede tener algunas horas). Sin dependencias: se prueba con node --test.

export type ProximaLluvia = {
  /** Primer tramo de horas con lluvia de consenso (lo que muestra el hora a hora). */
  inicio?: string;
  fin?: string;
  /** Hora más temprana y más tardía en que algún modelo empieza la lluvia. */
  desde?: string;
  hasta?: string;
  modelos: number;
  modelos_con_lluvia: number;
} | null | undefined;

const horaFmt = new Intl.DateTimeFormat("es-CL", { timeZone: "America/Santiago", hour: "2-digit", minute: "2-digit", hour12: false });
const fechaFmt = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit" });
const diaFmt = new Intl.DateTimeFormat("es-CL", { timeZone: "America/Santiago", weekday: "long" });

const hh = (ms: number) => horaFmt.format(ms);

/** "", " de mañana" o " del jueves", según el día de Chile de `ms` respecto de `ahora`. */
function delDia(ms: number, ahora: number): string {
  const dif = Math.round((Date.parse(`${fechaFmt.format(ms)}T12:00:00Z`) - Date.parse(`${fechaFmt.format(ahora)}T12:00:00Z`)) / 86_400_000);
  return dif <= 0 ? "" : dif === 1 ? " de mañana" : ` del ${diaFmt.format(ms)}`;
}

/** "las 19:00", "las 03:00 de mañana", "las 15:00 del jueves". */
const lasHoras = (ms: number, ahora: number) => `las ${hh(ms)}${delDia(ms, ahora)}`;

/** Texto de la próxima lluvia para el instante `ahora` (ms), o null si no hay nada que avisar. */
export function textoProximaLluvia(p: ProximaLluvia, ahora: number): string | null {
  if (!p) return null;
  const n = `${p.modelos_con_lluvia} de ${p.modelos} modelos`;
  if (p.inicio && p.fin) {
    const ini = Date.parse(p.inicio);
    const fin = Date.parse(p.fin);
    if (fin <= ahora) return null;
    if (ini <= ahora) return `Lluvia hasta cerca de ${lasHoras(fin, ahora)}`;
    let texto = `Lluvia probable desde ${lasHoras(ini, ahora)}`;
    if (p.desde && p.hasta && p.modelos_con_lluvia >= 2) {
      const a = Date.parse(p.desde);
      const b = Date.parse(p.hasta);
      if (b - a >= 2 * 3_600_000) texto += ` · los modelos la empiezan entre ${lasHoras(Math.max(a, ahora), ahora)} y ${lasHoras(b, ahora)}`;
    }
    return `${texto} (${n})`;
  }
  if (p.desde && p.hasta && Date.parse(p.hasta) > ahora) {
    const a = Math.max(Date.parse(p.desde), ahora);
    return `Posible lluvia desde ${lasHoras(a, ahora)} (solo ${n})`;
  }
  return null;
}
