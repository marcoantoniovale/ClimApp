import type { Dia, Hora, Observacion } from "@/lib/data";
import { cardinal, cielo, esNoche, fechaHora, grados, hora, region as nombreRegion } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";
import Flecha from "./Flecha";

const OBS_MAX_MIN = 120; // una medición más antigua no se muestra como "actual"

/** Bloque superior: el tiempo de la hora actual (pronóstico ICON) y, si es reciente, la medición cercana. */
export default function Ahora({
  nombre,
  region,
  etiqueta,
  ahora,
  hoy,
  observacion,
}: {
  nombre: string;
  region: string;
  etiqueta?: string;
  ahora: Hora | undefined;
  hoy: Dia | undefined;
  observacion: Observacion | null;
}) {
  const estado = cielo(ahora?.estado_cielo);
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
      <p className="text-sm text-slate-400">{nombreRegion(region)}</p>

      {ahora ? (
        <div className="mt-4 flex items-center gap-4">
          <WeatherIcon code={ahora.estado_cielo} night={esNoche(ahora.hora)} size={84} className="shrink-0" />
          <div className="min-w-0">
            <p className="text-6xl font-extralight leading-none tracking-tighter">{grados(ahora.temperatura)}</p>
            <p className="mt-1 text-lg font-medium text-slate-100">{estado.texto}</p>
            <p className="text-sm text-slate-400">Sensación {grados(ahora.sensacion_termica)}</p>
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
              <Flecha desde={ahora.viento_dir} />{ahora.viento ?? "–"} km/h {cardinal(ahora.viento_dir)}
            </dd>
            {ahora.rafaga != null && <dd className="text-xs text-slate-400">ráfagas {ahora.rafaga}</dd>}
          </div>
          <div className="rounded-xl bg-climapp-bg/60 px-3 py-2">
            <dt className="text-xs text-slate-400">Lluvia</dt>
            <dd className="text-slate-100">{ahora.precip_prob ?? "–"} %</dd>
            <dd className="text-xs text-slate-400">{ahora.precipitacion ?? 0} mm</dd>
          </div>
          <div className="rounded-xl bg-climapp-bg/60 px-3 py-2">
            <dt className="text-xs text-slate-400">Hoy</dt>
            <dd className="text-slate-100">{grados(hoy?.temperatura_max)} / {grados(hoy?.temperatura_min)}</dd>
            <dd className="text-xs text-slate-400">máx. / mín.</dd>
          </div>
        </dl>
      )}

      {obsReciente && (
        <p className="mt-3 rounded-xl bg-climapp-bg/60 px-3 py-2 text-sm text-slate-300">
          Medido en <strong className="font-semibold text-slate-100">{obsReciente.estacion}</strong> a las {hora(obsReciente.hora)}:{" "}
          {grados(obsReciente.temperatura)}
          {obsReciente.viento != null && `, viento ${obsReciente.viento} km/h`}
        </p>
      )}

      {ahora && (
        <p className="mt-3 text-xs text-slate-400">Pronóstico para las {hora(ahora.hora)} · {fechaHora(ahora.hora).split(",")[0]}</p>
      )}
    </section>
  );
}
