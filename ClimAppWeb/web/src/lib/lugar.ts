// Localidades y barrios (docs/localidades-propuesta.md). El ETL publica, por comuna, el ajuste de cada
// localidad (clave `lugares:<comuna>`, ver etl/src/climapp_etl/localidades.py). Aquí se aplica a la curva
// de la comuna:  T_localidad(h) = T_comuna(h) + franjas[franja(h)] + perfil[hora_local(h)]  (o + por_altura).

type Est = { nombre: string; km: number; peso: number };

export type Lugar = {
  nombre: string;
  tipo: string;
  lat: number;
  lon: number;
  altura: number | null;
  /** °C a sumar por franja de 6 h ("0" = 00–05 h …): sesgo de la comuna − sesgo en la localidad. */
  franjas: Record<string, number>;
  /** °C a sumar por hora local (localidades lejanas a la cabecera: otra celda del modelo). */
  perfil?: number[];
  /** °C a sumar por la diferencia de altura con la cabecera (localidades cercanas). */
  por_altura?: number;
  anomalia?: number;
  hora?: string;
  estaciones?: Est[];
  medicion?: { estacion: string; red?: string; hora: string; temperatura: number | null; viento?: number | null; km?: number };
};

export type LugaresPayload = { generado: string; tau_h: number; lugares: Record<string, Lugar> };

type HoraT = { hora: string; temperatura: number | null; sensacion_termica: number | null };
type DiaT = { fecha: string; temperatura_max: number | null; temperatura_min: number | null;
              rango_max: [number, number] | null; rango_min: [number, number] | null };

const r1 = (v: number) => Math.round(v * 10) / 10;
/** Hora local de un instante ISO con su desfase ("2026-10-03T15:00-03:00" → 15). */
const horaLocal = (iso: string) => Number(iso.slice(11, 13));

/** °C a sumar a la curva de la comuna a la hora `iso` en esta localidad. */
export function desfase(l: Lugar, iso: string): number {
  const h = horaLocal(iso);
  const sesgo = l.franjas[String(Math.floor(h / 6))] ?? 0;
  return sesgo + (l.perfil ? (l.perfil[h] ?? 0) : (l.por_altura ?? 0));
}

const mover = (v: number | null, d: number) => (v == null ? null : r1(v + d));
const moverRango = (r: [number, number] | null, d: number): [number, number] | null => (r ? [r1(r[0] + d), r1(r[1] + d)] : null);

/** Horas de la comuna llevadas a la localidad (temperatura y sensación térmica). */
export function horasDe<H extends HoraT>(horas: H[], l: Lugar): H[] {
  return horas.map((h) => {
    const d = desfase(l, h.hora);
    return { ...h, temperatura: mover(h.temperatura, d), sensacion_termica: mover(h.sensacion_termica, d) };
  });
}

/** Máximas y mínimas: se suma el desfase de la hora en que la comuna tiene su máxima (o mínima) del día. */
export function diasDe<D extends DiaT>(dias: D[], horas: HoraT[], l: Lugar): D[] {
  return dias.map((dia) => {
    const delDia = horas.filter((h) => h.temperatura != null && h.hora.slice(0, 10) === dia.fecha);
    if (delDia.length === 0) return dia;
    const hMax = delDia.reduce((a, b) => (b.temperatura! > a.temperatura! ? b : a));
    const hMin = delDia.reduce((a, b) => (b.temperatura! < a.temperatura! ? b : a));
    const dMax = desfase(l, hMax.hora);
    const dMin = desfase(l, hMin.hora);
    return { ...dia, temperatura_max: mover(dia.temperatura_max, dMax), temperatura_min: mover(dia.temperatura_min, dMin),
             rango_max: moverRango(dia.rango_max, dMax), rango_min: moverRango(dia.rango_min, dMin) };
  });
}
