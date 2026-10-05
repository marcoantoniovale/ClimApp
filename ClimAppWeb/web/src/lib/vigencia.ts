// Separa lo ya pasado de un pronóstico precalculado (sin dependencias: se usa en el servidor, en el
// navegador y en las pruebas).

type Vigente = { horas: { hora: string }[]; dias: { fecha: string }[] };

const fechaChile = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit" });

/**
 * El JSON se regenera con cada corrida: separa las horas ya pasadas (antes de la hora actual) y quita
 * los días que ya terminaron (después de medianoche el JSON aún puede empezar en el día anterior).
 * `horasPrevias` (hasta 3) no se muestran, pero la estimación minuto a minuto las usa para comparar
 * la última medición con la curva del pronóstico en ese instante.
 */
export function desdeAhora<T extends Vigente>(p: T & { horasPrevias?: T["horas"] }, ahora: Date = new Date()): T & { horasPrevias: T["horas"] } {
  const inicio = new Date(ahora);
  inicio.setMinutes(0, 0, 0);
  const t = inicio.getTime();
  const hoy = fechaChile.format(inicio);   // AAAA-MM-DD en hora de Chile
  const todas = [...(p.horasPrevias ?? []), ...p.horas];
  return {
    ...p,
    horas: todas.filter((h) => Date.parse(h.hora) >= t),
    horasPrevias: todas.filter((h) => Date.parse(h.hora) < t).slice(-3),
    dias: p.dias.filter((d) => d.fecha >= hoy),
  };
}
