import type { Dia } from "@/lib/data";
import { cielo, diaLargo, grados, nombreDia } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";

/**
 * Pronóstico de 7 días. La barra de cada día va de la mínima a la máxima sobre una escala común a
 * toda la semana (una serie, un color). Los valores se muestran como texto a ambos lados de la barra.
 * Debajo de la máxima, el rango entre modelos (base de la "fiabilidad del pronóstico").
 */
export default function WeeklyForecast({ dias }: { dias: Dia[] }) {
  const validos = dias.filter((d) => d.temperatura_min != null && d.temperatura_max != null);
  if (validos.length === 0) return null;
  const lo = Math.min(...validos.map((d) => d.temperatura_min!));
  const hi = Math.max(...validos.map((d) => d.temperatura_max!));
  const span = Math.max(hi - lo, 1);
  const pct = (t: number) => ((t - lo) / span) * 100;

  return (
    <section aria-labelledby="semana" className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-4 sm:p-5">
      <h2 id="semana" className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">Próximos 7 días</h2>
      <ul className="divide-y divide-climapp-line/70">
        {dias.map((d) => {
          const estado = cielo(d.estado_cielo);
          const completo = d.temperatura_min != null && d.temperatura_max != null;
          const modelos = d.rango_max && d.rango_max[1] - d.rango_max[0] >= 0.5
            ? `modelos ${grados(d.rango_max[0])}–${grados(d.rango_max[1])}`
            : null;
          return (
            <li
              key={d.fecha}
              className="grid grid-cols-[4.5rem_2.25rem_3rem_1fr] items-center gap-2 py-2.5 sm:grid-cols-[6rem_2.5rem_4rem_1fr]"
              aria-label={`${diaLargo(d.fecha)}: ${estado.texto}, mínima ${grados(d.temperatura_min)}, máxima ${grados(d.temperatura_max)}, lluvia ${d.precip_prob ?? 0} %`}
            >
              <span className="font-medium text-slate-100">{nombreDia(d.fecha)}</span>
              <WeatherIcon code={d.estado_cielo} size={32} />
              <span className={`text-xs ${d.precip_prob && d.precip_prob >= 30 ? "text-sky-300" : "text-slate-400"}`}>
                {d.precip_prob ? `${d.precip_prob} %` : ""}
                {d.precipitacion ? <span className="block">{d.precipitacion} mm</span> : null}
              </span>
              {completo ? (
                <div className="flex items-center gap-2">
                  <span className="w-8 text-right text-sm text-slate-300">{grados(d.temperatura_min)}</span>
                  <div className="relative h-1.5 flex-1 rounded-full bg-climapp-line">
                    <div
                      className="absolute h-1.5 rounded-full bg-climapp-temp"
                      style={{ left: `${pct(d.temperatura_min!)}%`, width: `${Math.max(pct(d.temperatura_max!) - pct(d.temperatura_min!), 2)}%` }}
                    />
                  </div>
                  <span className="w-12 text-sm font-semibold text-slate-100">
                    {grados(d.temperatura_max)}
                    {modelos && <span className="block text-[10px] font-normal leading-tight text-slate-400">{modelos}</span>}
                  </span>
                </div>
              ) : (
                <span className="text-xs text-slate-400">Datos incompletos</span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
