// "Usar mi ubicación": encontrar la comuna de una posición. Todo se calcula en el navegador;
// la ubicación del usuario no se envía al servidor (solo se piden los polígonos de unas pocas
// comunas cercanas, como archivos estáticos).

type Punto = { slug: string; lat?: number | null; lon?: number | null };
type Anillo = [number, number][]; // [lon, lat]
type Geometria = { type: "Polygon"; coordinates: Anillo[] } | { type: "MultiPolygon"; coordinates: Anillo[][] };

const CANDIDATOS = 6;        // comunas cuyos polígonos se revisan
const RADIO_CANDIDATOS = 60; // km desde la posición

/** Distancia en km entre dos puntos (fórmula del semiverseno). */
export function distanciaKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(a));
}

/** Lugares con coordenadas ordenados por distancia de su cabecera a (lat, lon). */
export function porDistancia<T extends Punto>(lugares: T[], lat: number, lon: number): { lugar: T; km: number }[] {
  return lugares
    .filter((l) => l.lat != null && l.lon != null)
    .map((lugar) => ({ lugar, km: distanciaKm(lat, lon, lugar.lat!, lugar.lon!) }))
    .sort((a, b) => a.km - b.km);
}

/** La cabecera más cercana y su distancia, o null si ningún lugar tiene coordenadas. */
export function masCercana<T extends Punto>(lugares: T[], lat: number, lon: number) {
  return porDistancia(lugares, lat, lon)[0] ?? null;
}

/** Punto dentro de un anillo (algoritmo del rayo). */
function enAnillo(lon: number, lat: number, anillo: Anillo): boolean {
  let dentro = false;
  for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    const [xi, yi] = anillo[i];
    const [xj, yj] = anillo[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) dentro = !dentro;
  }
  return dentro;
}

/** Punto dentro de un polígono (primer anillo = borde exterior, el resto = huecos) o multipolígono. */
export function enGeometria(lon: number, lat: number, geo: Geometria): boolean {
  const poligonos = geo.type === "Polygon" ? [geo.coordinates] : geo.coordinates;
  return poligonos.some(([exterior, ...huecos]) =>
    enAnillo(lon, lat, exterior) && !huecos.some((h) => enAnillo(lon, lat, h)));
}

/**
 * Comuna de la posición: revisa los polígonos de las comunas con cabecera más cercana; si el punto no
 * cae en ninguno (por ejemplo, en el mar frente a la costa), usa la cabecera más cercana.
 */
export async function comunaEnPosicion<T extends Punto>(
  lugares: T[],
  lat: number,
  lon: number,
  cargarGeo: (slug: string) => Promise<Geometria> = async (slug) => {
    const res = await fetch(`/geo/${slug}.json`);
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  },
): Promise<{ lugar: T; km: number; exacta: boolean } | null> {
  const orden = porDistancia(lugares, lat, lon);
  if (orden.length === 0) return null;
  const candidatos = orden.filter((c, i) => i === 0 || (i < CANDIDATOS && c.km <= RADIO_CANDIDATOS));
  const geos = await Promise.allSettled(candidatos.map((c) => cargarGeo(c.lugar.slug)));
  const i = geos.findIndex((g) => g.status === "fulfilled" && enGeometria(lon, lat, g.value));
  return i >= 0 ? { ...candidatos[i], exacta: true } : { ...orden[0], exacta: false };
}
