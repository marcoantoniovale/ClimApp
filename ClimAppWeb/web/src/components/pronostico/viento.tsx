"use client";

// Unidad del viento: km/h en comunas y localidades; nudos en los puertos (lo habitual en el mar).
// Los datos vienen siempre en km/h; la vista de un puerto activa los nudos con <VientoEnNudos>.

import { createContext, useContext, type ReactNode } from "react";

import { nudos } from "@/lib/format";

const EnNudos = createContext(false);

export function VientoEnNudos({ activo, children }: { activo: boolean; children: ReactNode }) {
  return <EnNudos.Provider value={activo}>{children}</EnNudos.Provider>;
}

/** Valor de viento (km/h) en la unidad de la vista, sin unidad: "12" o "–". */
export function useViento() {
  const enNudos = useContext(EnNudos);
  const valor = (kmh: number | null | undefined) => (kmh == null ? "–" : enNudos ? nudos(kmh) : String(kmh));
  return { unidad: enNudos ? "kn" : "km/h", valor };
}
