// Ubicación del usuario → comuna. Todo en el navegador: la posición no se envía al servidor.

import type { UbicacionIndice } from "./data";
import { comunaEnPosicion, distanciaKm } from "./geo";

/** Más lejos que esto de cualquier cabecera comunal (y fuera de todo polígono), se asume fuera de Chile. */
const MAX_KM_UBICACION = 80;
const CLAVE_GUARDADA = "climapp:ubicacion";
const MAX_KM_LOCALIDAD = 3;

export class ErrorUbicacion extends Error {}

const ERRORES_GPS: Record<number, string> = {
  1: "No diste permiso para usar tu ubicación. Puedes activarlo en la configuración del navegador.",
  2: "No pudimos determinar tu ubicación. Intenta de nuevo o busca tu comuna por nombre.",
  3: "Se agotó el tiempo para obtener tu ubicación. Intenta de nuevo.",
};

let indice: Promise<UbicacionIndice[]> | null = null;
let localidades: Promise<LocalidadIndice[]> | null = null;

/** Localidad o barrio en el índice estático /localidades.json (lo genera etl/scripts/build_localidades.py). */
export type LocalidadIndice = { s: string; n: string; c: string; la: number; lo: number };

/** A dónde lleva una búsqueda o la ubicación: una comuna o una localidad de una comuna. */
export type Destino = { slug: string; nombre: string; comuna?: { slug: string; nombre: string }; puerto?: boolean };

export const rutaDe = (d: Destino) =>
  d.puerto ? `/puerto/${d.slug}` : d.comuna ? `/lugar/${d.comuna.slug}/${d.slug}` : `/comuna/${d.slug}`;
export const apiDe = (d: Destino) =>
  d.puerto ? `/api/forecast/puerto-${d.slug}` : d.comuna ? `/api/lugar/${d.comuna.slug}/${d.slug}` : `/api/forecast/${d.slug}`;

/** Puerto en el índice estático /puertos.json (lo genera etl/scripts/build_puertos.py). */
export type PuertoIndice = { s: string; n: string; c: string };
let puertos: Promise<PuertoIndice[]> | null = null;

export function cargarPuertos(): Promise<PuertoIndice[]> {
  puertos ??= fetch("/puertos.json")
    .then((res) => {
      if (!res.ok) throw new Error(String(res.status));
      return res.json() as Promise<PuertoIndice[]>;
    })
    .catch((e) => {
      puertos = null;
      throw e;
    });
  return puertos;
}

/** Localidades y barrios (~75 KB comprimido), cargados una sola vez y solo cuando se necesitan. */
export function cargarLocalidades(): Promise<LocalidadIndice[]> {
  localidades ??= fetch("/localidades.json")
    .then((res) => {
      if (!res.ok) throw new Error(String(res.status));
      return res.json() as Promise<LocalidadIndice[]>;
    })
    .catch((e) => {
      localidades = null;
      throw e;
    });
  return localidades;
}

/** Catálogo de comunas (con coordenadas), cargado una sola vez. */
export function cargarIndice(): Promise<UbicacionIndice[]> {
  indice ??= fetch("/api/locations")
    .then((res) => {
      if (!res.ok) throw new Error(String(res.status));
      return res.json() as Promise<UbicacionIndice[]>;
    })
    .catch((e) => {
      indice = null;
      throw e;
    });
  return indice;
}

function posicion(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new ErrorUbicacion("Tu navegador no permite obtener la ubicación."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      resolve,
      (err) => reject(new ErrorUbicacion(ERRORES_GPS[err.code] ?? ERRORES_GPS[2])),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 5 * 60_000 },
    );
  });
}

/**
 * Pide la posición (llamar desde un gesto del usuario la primera vez: lo exige Safari) y devuelve la
 * comuna en que está o, si hay una localidad de esa comuna más cerca que la cabecera (≤ 3 km), esa
 * localidad. Lanza ErrorUbicacion con un mensaje para mostrar.
 */
export async function ubicar(): Promise<Destino> {
  const catalogo = cargarIndice();
  const pos = await posicion();
  let lista: UbicacionIndice[];
  try {
    lista = await catalogo;
  } catch {
    throw new ErrorUbicacion("No se pudo cargar el listado de comunas. Intenta de nuevo.");
  }
  const r = await comunaEnPosicion(lista, pos.coords.latitude, pos.coords.longitude);
  if (!r || (!r.exacta && r.km > MAX_KM_UBICACION)) {
    throw new ErrorUbicacion("Tu ubicación parece estar fuera de Chile. Busca la comuna por nombre.");
  }
  const { latitude: lat, longitude: lon } = pos.coords;
  const comuna = { slug: r.lugar.slug, nombre: r.lugar.nombre };
  let destino: Destino = comuna;
  try {
    const aCabecera = r.lugar.lat != null && r.lugar.lon != null ? distanciaKm(lat, lon, r.lugar.lat, r.lugar.lon) : Infinity;
    const cerca = (await cargarLocalidades())
      .filter((l) => l.c === comuna.slug)
      .map((l) => ({ l, km: distanciaKm(lat, lon, l.la, l.lo) }))
      .sort((a, b) => a.km - b.km)[0];
    if (cerca && cerca.km <= MAX_KM_LOCALIDAD && cerca.km < aCabecera) destino = { slug: cerca.l.s, nombre: cerca.l.n, comuna };
  } catch {
    // sin índice de localidades: queda la comuna
  }
  guardarUbicacion(destino, "gps");
  return destino;
}

export type UbicacionGuardada = Destino & { origen?: "gps" | "busqueda" };

/** Última comuna ubicada o buscada, guardada solo en este dispositivo (el inicio la muestra sin pedir el GPS). */
export function ubicacionGuardada(): UbicacionGuardada | null {
  try {
    const raw = localStorage.getItem(CLAVE_GUARDADA);
    const u = raw ? (JSON.parse(raw) as UbicacionGuardada) : null;
    return u?.slug && u.nombre ? u : null;
  } catch {
    return null;
  }
}

export function guardarUbicacion(destino: Destino, origen: "gps" | "busqueda") {
  try {
    localStorage.setItem(CLAVE_GUARDADA, JSON.stringify({ ...destino, origen }));
  } catch {
    // sin almacenamiento (modo privado): no es necesario
  }
}
