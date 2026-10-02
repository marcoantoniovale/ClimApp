// Ubicación del usuario → comuna. Todo en el navegador: la posición no se envía al servidor.

import type { UbicacionIndice } from "./data";
import { comunaEnPosicion } from "./geo";

/** Más lejos que esto de cualquier cabecera comunal (y fuera de todo polígono), se asume fuera de Chile. */
const MAX_KM_UBICACION = 80;
const CLAVE_GUARDADA = "climapp:ubicacion";

export class ErrorUbicacion extends Error {}

const ERRORES_GPS: Record<number, string> = {
  1: "No diste permiso para usar tu ubicación. Puedes activarlo en la configuración del navegador.",
  2: "No pudimos determinar tu ubicación. Intenta de nuevo o busca tu comuna por nombre.",
  3: "Se agotó el tiempo para obtener tu ubicación. Intenta de nuevo.",
};

let indice: Promise<UbicacionIndice[]> | null = null;

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
 * comuna en que está. Lanza ErrorUbicacion con un mensaje para mostrar.
 */
export async function ubicarComuna(): Promise<UbicacionIndice> {
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
  guardarUbicacion(r.lugar.slug, r.lugar.nombre, "gps");
  return r.lugar;
}

export type UbicacionGuardada = { slug: string; nombre: string; origen?: "gps" | "busqueda" };

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

export function guardarUbicacion(slug: string, nombre: string, origen: "gps" | "busqueda") {
  try {
    localStorage.setItem(CLAVE_GUARDADA, JSON.stringify({ slug, nombre, origen }));
  } catch {
    // sin almacenamiento (modo privado): no es necesario
  }
}
