"use client";

import type { Dia } from "@/lib/data";
import { cardinal, cielo, diaLargo, grados, nombreDia } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";
import Flecha from "./Flecha";

/** Selector de días (hoy + 5): cada tarjeta resume el día y al elegirla se ve su pronóstico por hora. */
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
    <div role="tablist" aria-label="Días" className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
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
            className={`flex w-[6.5rem] shrink-0 flex-col items-center rounded-2xl border px-2 py-3 text-center transition-colors focus-visible:outline-2 focus-visible:outline-climapp-teal ${
              activo ? "border-climapp-teal bg-climapp-teal/15" : "border-climapp-line bg-climapp-card/70 hover:border-slate-500"
            }`}
          >
            <span className="text-sm font-semibold text-slate-100">{nombreDia(d.fecha)}</span>
            <WeatherIcon code={d.estado_cielo} size={36} className="my-1" />
            <span className="text-sm">
              <strong className="font-semibold text-white">{grados(d.temperatura_max)}</strong>{" "}
              <span className="text-slate-400">{grados(d.temperatura_min)}</span>
            </span>
            <span className={`mt-1 text-xs ${d.precip_prob && d.precip_prob >= 30 ? "text-sky-300" : "text-slate-400"}`}>
              {d.precip_prob ?? 0} %{d.precipitacion ? ` · ${d.precipitacion} mm` : ""}
            </span>
            <span className="mt-0.5 flex items-center gap-1 text-xs text-slate-400">
              <Flecha desde={d.viento_dir} size={12} />
              {d.viento_max ?? "–"} km/h {cardinal(d.viento_dir)}
            </span>
          </button>
        );
      })}
    </div>
  );
}
