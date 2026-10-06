"use client";

import Link from "next/link";
import { useId, useState, useSyncExternalStore } from "react";

import { desdeAhora, type Hora, type PronosticoConAvisos } from "@/lib/data";
import { diaLargo, duracion, fechaLocal, grados, hora, oracion } from "@/lib/format";
import { ajustarDias, ajustarHoras, minutoActual, minutoServidor, suscribirMinuto } from "@/lib/ahora";
import { salidaPuesta } from "@/lib/sol";

import MarineForecast from "../weather/MarineForecast";
import WarningList from "../weather/WarningList";
import Ahora from "./Ahora";
import Dias from "./Dias";
import Horas from "./Horas";
import MarHoras from "./MarHoras";
import { VientoEnNudos } from "./viento";

/**
 * Vista completa del pronóstico de una ubicación: ahora, avisos, selector de días (hoy + 5) con su
 * pronóstico hora a hora, sol, oleaje y comunas cercanas. La usan el inicio (ubicación del usuario) y
 * la página de cada comuna. `p.horas` debe venir desde la hora actual.
 */
export default function Pronostico({ p: recibido, etiqueta }: { p: PronosticoConAvisos & { horasPrevias?: Hora[] }; etiqueta?: string }) {
  const [dia, setDia] = useState(0);
  const panelId = useId();
  const minuto = useSyncExternalStore(suscribirMinuto, minutoActual, minutoServidor);
  // En el navegador se vuelve a separar lo ya pasado con la hora real: la página puede venir de caché
  // (p. ej. generada antes de medianoche, con el día anterior todavía primero).
  const p = minuto != null ? desdeAhora(recibido, new Date(minuto)) : recibido;
  // Algoritmo ClimApp: horas, máximas y mínimas parten de las mediciones del momento (lib/ahora.ts).
  const base = [...(p.horasPrevias ?? []), ...p.horas];
  const horas = minuto != null ? ajustarHoras(p.horas, p.ancla, minuto) : p.horas;
  const dias = (minuto != null ? ajustarDias(p.dias, p.horas, p.ancla, minuto, fechaLocal) : p.dias).slice(0, 7);
  const elegido = dias[dia];
  const horasDelDia = elegido ? horas.filter((h) => fechaLocal(h.hora) === elegido.fecha) : [];
  const sol = elegido ? salidaPuesta(new Date(`${elegido.fecha}T12:00:00-03:00`), p.ubicacion.lat, p.ubicacion.lon) : null;
  const ahora = p.horas[0];
  const hoy = dias.find((d) => ahora && d.fecha === fechaLocal(ahora.hora)) ?? dias[0];

  const puerto = p.ubicacion.tipo === "puerto";
  return (
    <VientoEnNudos activo={puerto}>
    <div className="space-y-4">
      <Ahora nombre={p.ubicacion.nombre} region={p.ubicacion.region} comuna={p.ubicacion.comuna?.nombre} etiqueta={etiqueta}
        ahora={ahora} horas={base} hoy={hoy} observacion={p.observacion} ancla={p.ancla} lluvia={p.lluvia} proxima={p.proxima_lluvia} />

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

      {puerto && <MarHoras marino={p.marino} horas={horas} />}
      {p.ubicacion.es_costera && <MarineForecast marino={p.marino} />}

      {p.puertos && p.puertos.length > 0 && (
        <section aria-labelledby="puertos-comuna">
          <h2 id="puertos-comuna" className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">Puertos</h2>
          <ul className="flex flex-wrap gap-2">
            {p.puertos.map((x) => (
              <li key={x.slug}>
                <Link href={`/puerto/${x.slug}`}
                  className="block rounded-full border border-climapp-line bg-climapp-card/70 px-3 py-1.5 text-sm hover:border-climapp-teal hover:text-white">
                  ⚓ {x.nombre} <span className="text-xs text-slate-400">viento en nudos y olas hora a hora</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {p.localidades && p.localidades.length > 0 && (
        <section aria-labelledby="localidades">
          <h2 id="localidades" className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
            {p.ubicacion.comuna ? `Otras localidades de ${p.ubicacion.comuna.nombre}` : `Localidades de ${p.ubicacion.nombre}`}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {p.ubicacion.comuna && (
              <li>
                <Link href={`/comuna/${p.ubicacion.comuna.slug}`}
                  className="block rounded-full border border-climapp-line bg-climapp-card/70 px-3 py-1.5 text-sm font-medium hover:border-climapp-teal hover:text-white">
                  {p.ubicacion.comuna.nombre} <span className="text-xs text-slate-400">comuna</span>
                </Link>
              </li>
            )}
            {p.localidades.map((l) => (
              <li key={l.slug}>
                <Link href={`/lugar/${p.ubicacion.comuna?.slug ?? p.ubicacion.slug}/${l.slug}`}
                  className="block rounded-full border border-climapp-line bg-climapp-card/70 px-3 py-1.5 text-sm hover:border-climapp-teal hover:text-white">
                  {l.nombre}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

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
    </VientoEnNudos>
  );
}
