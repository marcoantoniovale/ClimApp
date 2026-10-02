"use client";

import type { Dia } from "@/lib/data";
import { cardinal, cielo, diaLargo, grados, nombreDia } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";
import Flecha from "./Flecha";

/** Nombre corto para tarjetas angostas: "Hoy", "Mañ", "Sáb 3". */
function nombreCorto(fecha: string) {
  const n = nombreDia(fecha);
  return n === "Mañana" ? "Mañ." : n;
}

/**
 * Selector de días (hoy + 6) que ocupa todo el ancho: 7 columnas iguales. Cada tarjeta resume el día y
 * al elegirla se ve su pronóstico por hora. En pantallas angostas se muestra lo esencial.
 */
export default function Dias({
  dias,
  seleccionado,
  onSeleccionar,
  panelId,
}: {
  dias: Dia[];
  seleccionado: number;
  onSeleccionar: (i: number) => void;
  panelId: string;
}) {
  return (
    <div role="tablist" aria-label="Días" className="grid gap-1 sm:gap-2" style={{ gridTemplateColumns: `repeat(${dias.length}, minmax(0, 1fr))` }}>
      {dias.map((d, i) => {
        const activo = i === seleccionado;
        return (
          <button
            key={d.fecha}
            type="button"
            role="tab"
            id={`dia-${d.fecha}`}
            aria-selected={activo}
            aria-controls={panelId}
            aria-label={`${diaLargo(d.fecha)}: ${cielo(d.estado_cielo).texto}, máxima ${grados(d.temperatura_max)}, mínima ${grados(d.temperatura_min)}, lluvia ${d.precip_prob ?? 0} %`}
            onClick={() => onSeleccionar(i)}
            className={`flex min-w-0 flex-col items-center rounded-2xl border px-0.5 py-2 text-center transition-colors focus-visible:outline-2 focus-visible:outline-climapp-teal sm:px-2 sm:py-3 ${
              activo ? "border-climapp-teal bg-climapp-teal/15" : "border-climapp-line bg-climapp-card/70 hover:border-slate-500"
            }`}
          >
            <span className="w-full truncate text-xs font-semibold text-slate-100 sm:text-sm">
              <span className="sm:hidden">{nombreCorto(d.fecha)}</span>
              <span className="hidden sm:inline">{nombreDia(d.fecha)}</span>
            </span>
            <WeatherIcon code={d.estado_cielo} size={30} className="my-1 sm:h-9 sm:w-9" />
            <span className="text-xs font-semibold text-white sm:text-sm">{grados(d.temperatura_max)}</span>
            <span className="text-xs text-slate-400">{grados(d.temperatura_min)}</span>
            <span className={`mt-1 text-[11px] sm:text-xs ${d.precip_prob && d.precip_prob >= 30 ? "text-sky-300" : "text-slate-400"}`}>
              {d.precip_prob ?? 0}%
            </span>
            {d.precipitacion ? <span className="hidden text-xs text-sky-300 sm:block">{d.precipitacion} mm</span> : null}
            <span className="mt-0.5 hidden items-center gap-1 text-xs text-slate-400 sm:flex">
              <Flecha desde={d.viento_dir} size={12} />
              {d.viento_max ?? "–"} {cardinal(d.viento_dir)}
            </span>
          </button>
        );
      })}
    </div>
  );
}
