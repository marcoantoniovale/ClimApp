"use client";

import { useSyncExternalStore } from "react";

import { estimacionActual, minutoActual, minutoServidor, suscribirMinuto } from "@/lib/ahora";
import type { AnclaUbicacion, Dia, Hora, Observacion } from "@/lib/data";
import { cardinal, cielo, esNoche, fechaHora, grados, grados1, hora, region as nombreRegion } from "@/lib/format";
import { cieloAhora, estadoLluvia, mm, type LluviaMedida } from "@/lib/lluvia";
import { textoProximaLluvia, type ProximaLluvia } from "@/lib/proximaLluvia";

import WeatherIcon from "../WeatherIcon";
import Flecha from "./Flecha";
import { useViento } from "./viento";

const OBS_MAX_MIN = 120; // una medición más antigua no se muestra como "actual"

/**
 * Bloque superior: el tiempo de la hora actual (pronóstico ICON + ECMWF) y, si es reciente, la medición
 * cercana. Manda la lluvia medida en la estación DMC cercana: si llovió en la última hora, el cielo es
 * lluvia; si una estación cercana estuvo seca y el pronóstico decía lluvia, el cielo pasa a nublado.
 */
export default function Ahora({
  nombre,
  region,
  comuna,
  etiqueta,
  ahora,
  horas,
  hoy,
  observacion,
  ancla,
  lluvia,
  proxima,
}: {
  nombre: string;
  region: string;
  /** Solo localidades: nombre de su comuna. */
  comuna?: string;
  etiqueta?: string;
  ahora: Hora | undefined;
  horas: Hora[];
  hoy: Dia | undefined;
  observacion: Observacion | null;
  ancla?: AnclaUbicacion | null;
  lluvia?: LluviaMedida | null;
  proxima?: ProximaLluvia;
}) {
  const viento = useViento();
  // Temperatura actual cada 5 minutos (algoritmo ClimApp, lib/ahora.ts); en el servidor, el valor horario.
  const minuto = useSyncExternalStore(suscribirMinuto, minutoActual, minutoServidor);
  // Lluvia medida (lib/lluvia.ts): en el servidor se compara con la mitad de la hora mostrada.
  const medida = ahora ? estadoLluvia(lluvia, minuto ?? Date.parse(ahora.hora) + 30 * 60_000) : null;
  const { codigo, nota } = cieloAhora(ahora?.estado_cielo, ahora?.nubosidad, medida);
  const estado = cielo(codigo);
  const estimada = minuto != null ? estimacionActual(horas, ancla, minuto) : null;
  const temperatura = estimada?.temperatura ?? ahora?.temperatura;
  const sensacion = estimada?.sensacion_termica ?? ahora?.sensacion_termica;
  // Antigüedad de la medición respecto de la hora mostrada (no de Date.now(): el render debe ser puro).
  const obsReciente =
    observacion && ahora &&
    Math.abs(new Date(ahora.hora).getTime() - new Date(observacion.hora).getTime()) / 60_000 <= OBS_MAX_MIN
      ? observacion : null;

  return (
    <section aria-labelledby="ahora" className="relative overflow-hidden rounded-3xl border border-climapp-line bg-climapp-card/70 p-5 shadow-xl sm:p-7">
      <div className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-climapp-teal/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-12 -left-12 h-40 w-40 rounded-full bg-climapp-sun/15 blur-3xl" />

      {etiqueta && <p className="text-xs font-semibold uppercase tracking-wide text-climapp-teal">{etiqueta}</p>}
      <h1 id="ahora" className="text-2xl font-semibold tracking-tight">{nombre}</h1>
      <p className="text-sm text-slate-400">{comuna ? `${comuna} · ` : ""}{nombreRegion(region)}</p>

      {ahora ? (
        <div className="mt-4 flex items-center gap-4">
          <WeatherIcon code={codigo} night={esNoche(ahora.hora)} size={84} className="shrink-0" />
          <div className="min-w-0">
            <p className="text-6xl font-extralight leading-none tracking-tighter">{grados1(temperatura)}</p>
            <p className="mt-1 text-lg font-medium text-slate-100">
              {estado.texto}{nota && <span className="text-sm font-normal text-slate-400"> ({nota})</span>}
            </p>
            <p className="text-sm text-slate-400">Sensación {grados(sensacion)}</p>
          </div>
        </div>
      ) : (
        <p className="my-6 text-slate-300">Sin pronóstico disponible por ahora.</p>
      )}

      {ahora && (
        <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-xl bg-climapp-bg/60 px-3 py-2">
            <dt className="text-xs text-slate-400">Viento</dt>
            <dd className="flex items-center gap-1 text-slate-100">
              <Flecha desde={ahora.viento_dir} />{viento.valor(ahora.viento)} {viento.unidad} {cardinal(ahora.viento_dir)}
            </dd>
            {ahora.rafaga != null && <dd className="text-xs text-slate-400">ráfagas {viento.valor(ahora.rafaga)}</dd>}
          </div>
          <div className="rounded-xl bg-climapp-bg/60 px-3 py-2">
            <dt className="text-xs text-slate-400">Lluvia</dt>
            <dd className="text-slate-100">{ahora.precip_prob ?? "–"} %</dd>
            <dd className="text-xs text-slate-400">
              {medida?.lloviendo ? `${mm(medida.medida.mm_1h)} medidos`
                : nota ? `${mm(ahora.precipitacion)} pronost.` : mm(ahora.precipitacion)}
            </dd>
            {medida && medida.medida.mm_24h != null && (
              <dd className={`text-xs ${medida.medida.mm_24h > 0 ? "text-sky-300" : "text-slate-400"}`}
                title={`Lluvia caída en las últimas 24 h en ${medida.medida.nombre}`}>
                24&nbsp;h: {mm(medida.medida.mm_24h)}
              </dd>
            )}
          </div>
          <div className="rounded-xl bg-climapp-bg/60 px-3 py-2">
            <dt className="text-xs text-slate-400">Hoy</dt>
            <dd className="text-slate-100">{grados(hoy?.temperatura_max)} / {grados(hoy?.temperatura_min)}</dd>
            <dd className="text-xs text-slate-400">máx. / mín.</dd>
          </div>
        </dl>
      )}

      {medida && (
        <p className="mt-3 rounded-xl bg-climapp-bg/60 px-3 py-2 text-sm text-slate-300">
          {medida.lloviendo ? "Lluvia medida en " : "Sin lluvia en la última hora en "}
          <strong className="font-semibold text-slate-100">{medida.medida.nombre}</strong>
          {medida.medida.km >= 1 && ` (a ${medida.medida.km.toLocaleString("es-CL")} km)`}
          {medida.lloviendo
            ? `: ${mm(medida.medida.mm_1h)} entre las ${hora(new Date(Date.parse(medida.medida.hasta) - 3_600_000).toISOString())} y las ${hora(medida.medida.hasta)}`
            : ` hasta las ${hora(medida.medida.hasta)}`}
          {(medida.medida.mm_3h ?? 0) > 0 && medida.medida.mm_3h !== medida.medida.mm_24h && ` · ${mm(medida.medida.mm_3h)} en 3 h`}
          {(medida.medida.mm_24h ?? 0) > 0 && ` · ${mm(medida.medida.mm_24h)} en 24 h`}
        </p>
      )}

      {/* Próxima lluvia (en el navegador, con la hora real); no se muestra si la estación cercana mide lluvia ahora. */}
      {minuto != null && !medida?.lloviendo && textoProximaLluvia(proxima, minuto) && (
        <p className="mt-3 flex gap-2 rounded-xl bg-climapp-bg/60 px-3 py-2 text-sm text-slate-300">
          <span aria-hidden="true" className="text-climapp-rain">☂</span>
          <span>{textoProximaLluvia(proxima, minuto)}</span>
        </p>
      )}

      {obsReciente && (
        <p className="mt-3 rounded-xl bg-climapp-bg/60 px-3 py-2 text-sm text-slate-300">
          Medido en <strong className="font-semibold text-slate-100">{obsReciente.estacion}</strong>
          {obsReciente.km != null && obsReciente.km >= 1 && ` (a ${obsReciente.km.toLocaleString("es-CL")} km)`} a las {hora(obsReciente.hora)}:{" "}
          {grados1(obsReciente.temperatura)}
          {obsReciente.viento != null && `, viento ${viento.valor(obsReciente.viento)} ${viento.unidad}`}
        </p>
      )}

      {ahora && (
        <p className="mt-3 text-xs text-slate-400">
          {minuto != null
            ? <>Estimación ClimApp para las {hora(new Date(minuto).toISOString())}{estimada?.ajustada ? `, con ${ancla!.estaciones.length === 1 ? "1 estación" : `${ancla!.estaciones.length} estaciones`} cercanas` : ""} · se actualiza cada 5 minutos</>
            : <>Pronóstico para las {hora(ahora.hora)} · {fechaHora(ahora.hora).split(",")[0]}</>}
        </p>
      )}
    </section>
  );
}
