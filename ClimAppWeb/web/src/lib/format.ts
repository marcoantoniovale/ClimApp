// Formato para la interfaz: horas de Chile, estado del cielo (códigos WMO), viento y UV.

const TZ = "America/Santiago";

const horaFmt = new Intl.DateTimeFormat("es-CL", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false });
const horaCortaFmt = new Intl.DateTimeFormat("es-CL", { timeZone: TZ, hour: "2-digit", hour12: false });
const diaFmt = new Intl.DateTimeFormat("es-CL", { timeZone: TZ, weekday: "short", day: "numeric" });
const diaLargoFmt = new Intl.DateTimeFormat("es-CL", { timeZone: TZ, weekday: "long", day: "numeric", month: "long" });
const fechaHoraFmt = new Intl.DateTimeFormat("es-CL", {
  timeZone: TZ, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
});
const isoDateFmt = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });

/** "17:00" */
export const hora = (iso: string) => horaFmt.format(new Date(iso));
/** "17" */
export const horaCorta = (iso: string) => horaCortaFmt.format(new Date(iso)).padStart(2, "0");
/** "1 oct, 17:15" */
export const fechaHora = (iso: string) => fechaHoraFmt.format(new Date(iso));

/** Fecha local "2026-10-02" como Date al mediodía de Chile (evita saltos de día). */
const mediodia = (fecha: string) => new Date(`${fecha}T12:00:00-03:00`);

/** "Hoy", "Mañana" o "vie 3". */
export function nombreDia(fecha: string, hoy: string = isoDateFmt.format(new Date())): string {
  const diff = Math.round((mediodia(fecha).getTime() - mediodia(hoy).getTime()) / 86_400_000);
  if (diff === 0) return "Hoy";
  if (diff === 1) return "Mañana";
  const texto = diaFmt.format(mediodia(fecha));
  return texto.charAt(0).toUpperCase() + texto.slice(1).replace(".", "");
}

/** "jueves 2 de octubre" */
export const diaLargo = (fecha: string) => diaLargoFmt.format(mediodia(fecha));

/** Fecha local (Chile) de un instante ISO: "2026-10-01". */
export const fechaLocal = (iso: string) => isoDateFmt.format(new Date(iso));

export const grados = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v)}°`);

// ---------------------------------------------------------------------------
// Estado del cielo (códigos WMO de Open-Meteo)

export type Cielo = "despejado" | "parcial" | "nublado" | "niebla" | "llovizna" | "lluvia" | "nieve" | "tormenta";

const WMO: Record<number, [string, Cielo]> = {
  0: ["Despejado", "despejado"],
  1: ["Mayormente despejado", "despejado"],
  2: ["Parcialmente nublado", "parcial"],
  3: ["Nublado", "nublado"],
  45: ["Niebla", "niebla"],
  48: ["Niebla con escarcha", "niebla"],
  51: ["Llovizna débil", "llovizna"],
  53: ["Llovizna", "llovizna"],
  55: ["Llovizna intensa", "llovizna"],
  56: ["Llovizna helada", "llovizna"],
  57: ["Llovizna helada intensa", "llovizna"],
  61: ["Lluvia débil", "lluvia"],
  63: ["Lluvia", "lluvia"],
  65: ["Lluvia fuerte", "lluvia"],
  66: ["Lluvia helada", "lluvia"],
  67: ["Lluvia helada fuerte", "lluvia"],
  71: ["Nieve débil", "nieve"],
  73: ["Nieve", "nieve"],
  75: ["Nieve intensa", "nieve"],
  77: ["Granos de nieve", "nieve"],
  80: ["Chubascos débiles", "lluvia"],
  81: ["Chubascos", "lluvia"],
  82: ["Chubascos fuertes", "lluvia"],
  85: ["Chubascos de nieve", "nieve"],
  86: ["Chubascos de nieve fuertes", "nieve"],
  95: ["Tormenta", "tormenta"],
  96: ["Tormenta con granizo", "tormenta"],
  99: ["Tormenta con granizo fuerte", "tormenta"],
};

export function cielo(code: number | null | undefined): { texto: string; tipo: Cielo } {
  const entry = code == null ? undefined : WMO[code];
  return entry ? { texto: entry[0], tipo: entry[1] } : { texto: "Sin dato", tipo: "nublado" };
}

/** Noche aproximada para elegir ícono (luna en vez de sol). */
export const esNoche = (iso: string) => {
  const h = Number(horaCorta(iso));
  return h < 7 || h >= 20;
};

// ---------------------------------------------------------------------------
// Viento, UV

const PUNTOS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"];

/** Dirección de donde viene el viento como punto cardinal ("SO"). */
export const cardinal = (deg: number | null | undefined) =>
  deg == null ? "" : PUNTOS[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];

export function categoriaUV(uv: number | null | undefined): string {
  if (uv == null) return "Sin dato";
  if (uv < 3) return "Bajo";
  if (uv < 6) return "Moderado";
  if (uv < 8) return "Alto";
  if (uv < 11) return "Muy alto";
  return "Extremo";
}

const TIPOS_AVISO: Record<string, string> = {
  marejadas: "Marejadas",
  mal_tiempo: "Mal tiempo",
  temporal: "Temporal",
  viento: "Viento",
  convectivas: "Nubes convectivas",
  niebla: "Niebla",
};

export const tipoAviso = (tipo: string) => TIPOS_AVISO[tipo] ?? "Aviso";

const CONECTORES = new Set(["a", "al", "de", "del", "e", "el", "en", "hasta", "la", "las", "los", "por", "y"]);

/** Nombre propio en formato título, con conectores en minúscula: "Golfo de Penas hasta Arica". */
export const titulo = (texto: string) =>
  texto.toLowerCase().replace(/\p{L}+/gu, (w, offset: number) =>
    offset > 0 && CONECTORES.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1));

/** Solo la primera letra en mayúscula: "Aviso de marejadas". */
export const oracion = (texto: string) => {
  const t = texto.toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
};

// La lista oficial de regiones viene sin tildes; nombre para mostrar.
const REGIONES: Record<string, string> = {
  "Tarapaca": "Tarapacá",
  "Valparaiso": "Valparaíso",
  "Libertador General Bernardo OHiggins": "O’Higgins",
  "Biobio": "Biobío",
  "La Araucania": "La Araucanía",
  "Los Rios": "Los Ríos",
  "Aysen del General Carlos Ibanez del Campo": "Aysén",
  "Magallanes y de la Antartica Chilena": "Magallanes",
  "Metropolitana de Santiago": "Metropolitana",
  "Nuble": "Ñuble",
};

export const region = (nombre: string) => `Región de ${REGIONES[nombre] ?? nombre}`.replace("Región de Metropolitana", "Región Metropolitana");

/** Recomendación de protección solar según el índice UV. */
export function proteccionUV(uv: number | null | undefined): string {
  if (uv == null || uv < 3) return "Sin protección necesaria";
  if (uv < 6) return "Usa protector FPS 30";
  if (uv < 8) return "Protector FPS 30–50, gorro y lentes";
  if (uv < 11) return "Protector FPS 50+, evita el sol al mediodía";
  return "Evita exponerte al sol";
}

/** Visibilidad en m → texto ("> 10 km", "3,5 km", "800 m"). */
export function visibilidad(m: number | null | undefined): string {
  if (m == null) return "–";
  if (m >= 10_000) return "> 10 km";
  if (m >= 1_000) return `${(m / 1000).toLocaleString("es-CL", { maximumFractionDigits: 1 })} km`;
  return `${Math.round(m / 100) * 100} m`;
}

/** Duración en minutos → "12 h 27 min". */
export const duracion = (min: number) => `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} min`;
