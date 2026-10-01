import type { Dia, Hora, Observacion } from "@/lib/data";
import { cielo, esNoche, fechaHora, grados, hora, region as nombreRegion } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";

/** Clima de la hora actual (promedio de modelos) y, si existe, la última medición cercana. */
export default function CurrentWeather({
  nombre,
  region,
  ahora,
  hoy,
  observacion,
  actualizado,
  corridas,
}: {
  nombre: string;
  region: string;
  ahora: Hora | undefined;
  hoy: Dia | undefined;
  observacion: Observacion | null;
  actualizado: string | null;
  corridas?: Record<string, string>;
}) {
  const estado = cielo(ahora?.estado_cielo);
  return (
    <section aria-labelledby="actual" className="relative overflow-hidden rounded-3xl border border-climapp-line bg-climapp-card/70 p-6 text-center shadow-xl sm:p-8">
      <div className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-climapp-teal/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-12 -left-12 h-40 w-40 rounded-full bg-climapp-sun/15 blur-3xl" />

      <h1 id="actual" className="text-2xl font-semibold tracking-tight">{nombre}</h1>
      <p className="text-sm text-slate-400">{nombreRegion(region)}</p>

      {ahora ? (
        <>
          <WeatherIcon code={ahora.estado_cielo} night={esNoche(ahora.hora)} size={88} className="mx-auto my-3" />
          <p className="text-7xl font-extralight tracking-tighter">{grados(ahora.temperatura)}</p>
          <p className="mt-1 text-lg font-medium text-slate-200">{estado.texto}</p>
          <p className="mt-1 text-sm text-slate-400">Sensación térmica {grados(ahora.sensacion_termica)}</p>
          {hoy && (
            <p className="mt-3 flex justify-center gap-4 text-sm font-semibold text-slate-300">
              <span>Máx. <strong className="text-white">{grados(hoy.temperatura_max)}</strong></span>
              <span>Mín. <strong className="text-white">{grados(hoy.temperatura_min)}</strong></span>
            </p>
          )}
        </>
      ) : (
        <p className="my-8 text-slate-300">Sin pronóstico disponible por ahora.</p>
      )}

      {observacion && (
        <p className="mx-auto mt-5 max-w-sm rounded-xl bg-climapp-bg/60 px-4 py-2 text-sm text-slate-300">
          Medido en <strong className="font-semibold text-slate-100">{observacion.estacion}</strong> a las {hora(observacion.hora)}:{" "}
          {grados(observacion.temperatura)}
          {observacion.viento != null && `, viento ${observacion.viento} km/h`}
          {observacion.humedad != null && `, humedad ${Math.round(observacion.humedad)} %`}
        </p>
      )}

      {actualizado && (
        <p className="mt-4 text-xs text-slate-400">
          Pronóstico provisional · actualizado {fechaHora(actualizado)}
          {corridas && Object.keys(corridas).length > 0 && (
            <span className="block">
              Corridas de los modelos:{" "}
              {Object.entries(corridas)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([m, iso]) => `${m.toUpperCase()} ${fechaHora(iso)}`)
                .join(" · ")}
            </span>
          )}
        </p>
      )}
    </section>
  );
}
