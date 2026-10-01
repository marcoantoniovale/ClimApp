import type { Marino } from "@/lib/data";
import { cardinal, nombreDia } from "@/lib/format";

/** Flecha que apunta hacia donde va el oleaje (la dirección de la fuente es desde donde viene). */
function Arrow({ deg }: { deg: number | null }) {
  if (deg == null) return null;
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" style={{ transform: `rotate(${deg + 180}deg)` }}>
      <path d="M12 3v18M12 3l-6 6M12 3l6 6" fill="none" stroke="#cbd5e1" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Oleaje por día (comunas costeras): altura máxima como barra sobre escala común, período y dirección. */
export default function MarineForecast({ marino }: { marino: Marino | null }) {
  const dias = marino?.dias.filter((d) => d.altura_max != null) ?? [];
  if (dias.length === 0) return null;
  const hi = Math.max(...dias.map((d) => d.altura_max!), 1);

  return (
    <section aria-labelledby="oleaje" className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-4 sm:p-5">
      <h2 id="oleaje" className="text-sm font-semibold uppercase tracking-wide text-slate-400">Oleaje frente a la costa</h2>
      <p className="mb-2 text-xs text-slate-400">Altura significativa máxima del día (modelo marino de Open-Meteo)</p>
      <ul className="divide-y divide-climapp-line/70">
        {dias.map((d) => (
          <li key={d.fecha} className="grid grid-cols-[4.5rem_1fr_3.5rem_4.5rem] items-center gap-3 py-2 text-sm sm:grid-cols-[6rem_1fr_4rem_5rem]"
            aria-label={`${nombreDia(d.fecha)}: olas de hasta ${d.altura_max} m, período ${d.periodo_max ?? "–"} s, desde el ${cardinal(d.direccion)}`}>
            <span className="font-medium text-slate-100">{nombreDia(d.fecha)}</span>
            <div className="h-1.5 rounded-full bg-climapp-line">
              <div className="h-1.5 rounded-full bg-climapp-rain" style={{ width: `${(d.altura_max! / hi) * 100}%` }} />
            </div>
            <span className="font-semibold text-slate-100">{d.altura_max!.toFixed(1)} m</span>
            <span className="flex items-center gap-1 text-xs text-slate-400">
              <Arrow deg={d.direccion} />{cardinal(d.direccion)} · {d.periodo_max ?? "–"} s
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
