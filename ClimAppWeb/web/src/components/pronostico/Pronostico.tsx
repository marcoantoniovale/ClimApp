"use client";

import Link from "next/link";
import { useId, useState, useSyncExternalStore } from "react";

import type { Hora, PronosticoConAvisos } from "@/lib/data";
import { diaLargo, duracion, fechaLocal, grados, hora, oracion } from "@/lib/format";
import { ajustarDias, ajustarHoras, minutoActual, minutoServidor, suscribirMinuto } from "@/lib/ahora";
import { salidaPuesta } from "@/lib/sol";

import MarineForecast from "../weather/MarineForecast";
import WarningList from "../weather/WarningList";
import Ahora from "./Ahora";
import Dias from "./Dias";
import Horas from "./Horas";

/**
 * Vista completa del pronóstico de una ubicación: ahora, avisos, selector de días (hoy + 5) con su
 * pronóstico hora a hora, sol, oleaje y comunas cercanas. La usan el inicio (ubicación del usuario) y
 * la página de cada comuna. `p.horas` debe venir desde la hora actual.
 */
export default function Pronostico({ p, etiqueta }: { p: PronosticoConAvisos & { horasPrevias?: Hora[] }; etiqueta?: string }) {
  const [dia, setDia] = useState(0);
  const panelId = useId();
  // Algoritmo ClimApp: horas, máximas y mínimas parten de las mediciones del momento (lib/ahora.ts).
  const minuto = useSyncExternalStore(suscribirMinuto, minutoActual, minutoServidor);
  const base = [...(p.horasPrevias ?? []), ...p.horas];
  const horas = minuto != null ? ajustarHoras(p.horas, p.ancla, minuto) : p.horas;
  const dias = (minuto != null ? ajustarDias(p.dias, p.horas, p.ancla, minuto, fechaLocal) : p.dias).slice(0, 7);
  const elegido = dias[dia];
  const horasDelDia = elegido ? horas.filter((h) => fechaLocal(h.hora) === elegido.fecha) : [];
  const sol = elegido ? salidaPuesta(new Date(`${elegido.fecha}T12:00:00-03:00`), p.ubicacion.lat, p.ubicacion.lon) : null;
  const ahora = p.horas[0];
  const hoy = dias.find((d) => ahora && d.fecha === fechaLocal(ahora.hora)) ?? dias[0];

  return (
    <div className="space-y-4">
      <Ahora nombre={p.ubicacion.nombre} region={p.ubicacion.region} etiqueta={etiqueta}
        ahora={ahora} horas={base} hoy={hoy} observacion={p.observacion} ancla={p.ancla} />

      <WarningList avisos={p.avisos} />

      <section aria-labelledby="pronostico-dias" className="space-y-3">
        <h2 id="pronostico-dias" className="text-sm font-semibold uppercase tracking-wide text-slate-400">Pronóstico por día</h2>
        <Dias dias={dias} seleccionado={dia} onSeleccionar={setDia} panelId={panelId} />

        {elegido && (
          <div className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-4 sm:p-5">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 className="text-base font-semibold text-slate-100">{oracion(diaLargo(elegido.fecha))}</h3>
              <p className="text-sm text-slate-300">
                Máx. <strong className="text-white">{grados(elegido.temperatura_max)}</strong> · Mín.{" "}
                <strong className="text-white">{grados(elegido.temperatura_min)}</strong>
              </p>
            </div>
            {sol && (
              <p className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                <span>☀ Salida {hora(sol.salida.toISOString())}</span>
                <span>Puesta {hora(sol.puesta.toISOString())}</span>
                <span>{duracion(sol.duracionMin)} de luz</span>
              </p>
            )}
            <p className="mb-1 grid grid-cols-[3.25rem_2.25rem_3rem_1fr_auto] gap-2 text-[11px] uppercase tracking-wide text-slate-500">
              <span>Hora</span><span /><span>Temp.</span><span>Lluvia</span><span>Viento</span>
            </p>
            <Horas horas={horasDelDia} id={panelId} etiquetaId={`dia-${elegido.fecha}`} />
          </div>
        )}
      </section>

      {p.ubicacion.es_costera && <MarineForecast marino={p.marino} />}

      {p.cercanas && p.cercanas.length > 0 && (
        <section aria-labelledby="cercanas">
          <h2 id="cercanas" className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">Comunas cercanas</h2>
          <ul className="flex flex-wrap gap-2">
            {p.cercanas.map((c) => (
              <li key={c.slug}>
                <Link href={`/comuna/${c.slug}`}
                  className="block rounded-full border border-climapp-line bg-climapp-card/70 px-3 py-1.5 text-sm hover:border-climapp-teal hover:text-white">
                  {c.nombre} <span className="text-xs text-slate-400">{c.km} km</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

    </div>
  );
}
