import type { Hora, Marino } from "@/lib/data";
import { cardinal, hora, nombreDia, nudos } from "@/lib/format";

import Flecha from "./Flecha";

/**
 * Puertos: el mar hora a hora (48 h) en una tabla compacta: viento y ráfagas en nudos con su dirección,
 * altura de ola, período y dirección del oleaje, y marejada de fondo (swell). Viento: pronóstico de la
 * ubicación (ICON + ECMWF); oleaje: modelo marino de Open-Meteo en la celda de mar más cercana.
 */
export default function MarHoras({ marino, horas }: { marino: Marino | null; horas: Hora[] }) {
  const viento = new Map(horas.map((h) => [h.hora, h]));
  const desde = horas.length ? Date.parse(horas[0].hora) : 0;   // sin horas ya pasadas
  const filas = (marino?.horas ?? []).filter((m) => Date.parse(m.hora) >= desde && (viento.has(m.hora) || m.altura != null));
  if (filas.length === 0) return null;

  return (
    <section aria-labelledby="mar-horas" className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-4 sm:p-5">
      <h2 id="mar-horas" className="text-sm font-semibold uppercase tracking-wide text-slate-400">El mar hora a hora</h2>
      <p className="mb-3 text-xs text-slate-400">Viento en nudos (kn); olas: altura significativa, período y dirección de donde vienen.</p>
      <div className="max-h-[28rem] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-climapp-card text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" className="py-1.5 pr-2 font-medium">Hora</th>
              <th scope="col" className="py-1.5 pr-2 font-medium">Viento</th>
              <th scope="col" className="py-1.5 pr-2 font-medium">Ráfagas</th>
              <th scope="col" className="py-1.5 pr-2 font-medium">Olas</th>
              <th scope="col" className="hidden py-1.5 font-medium sm:table-cell">Marejada</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-climapp-line/60">
            {filas.map((m, i) => {
              const v = viento.get(m.hora);
              const fecha = m.hora.slice(0, 10);
              const nuevoDia = i === 0 || filas[i - 1].hora.slice(0, 10) !== fecha;
              return [
                nuevoDia && (
                  <tr key={`d-${fecha}`}>
                    <th scope="rowgroup" colSpan={5} className="pt-3 pb-1 text-left text-xs font-semibold text-slate-300">{nombreDia(fecha)}</th>
                  </tr>
                ),
                <tr key={m.hora} className="text-slate-200">
                  <th scope="row" className="py-1.5 pr-2 text-left font-medium text-slate-300">{hora(m.hora)}</th>
                  <td className="py-1.5 pr-2">
                    <span className="inline-flex items-center gap-1">
                      <Flecha desde={v?.viento_dir} />{nudos(v?.viento)} kn
                      <span className="text-xs text-slate-400">{cardinal(v?.viento_dir)}</span>
                    </span>
                  </td>
                  <td className="py-1.5 pr-2">{nudos(v?.rafaga)} kn</td>
                  <td className="py-1.5 pr-2">
                    <span className="inline-flex items-center gap-1">
                      <Flecha desde={m.direccion} />
                      {m.altura == null ? "–" : `${m.altura.toLocaleString("es-CL")} m`}
                      <span className="text-xs text-slate-400">{m.periodo == null ? "" : `${m.periodo} s`}</span>
                    </span>
                  </td>
                  <td className="hidden py-1.5 sm:table-cell">{m.marejada == null ? "–" : `${m.marejada.toLocaleString("es-CL")} m`}</td>
                </tr>,
              ];
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
