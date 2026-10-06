import type { Hora } from "@/lib/data";
import { cardinal, categoriaUV, cielo, esNoche, grados, hora, proteccionUV, visibilidad } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";
import Flecha from "./Flecha";
import { useViento } from "./viento";

function Dato({ label, valor, detalle }: { label: string; valor: string; detalle?: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="text-sm text-slate-100">{valor}</dd>
      {detalle && <dd className="text-xs text-slate-400">{detalle}</dd>}
    </div>
  );
}

/**
 * Pronóstico hora a hora de un día. Cada hora es una fila resumida (estado, temperatura, lluvia, viento)
 * que se despliega con el detalle: sensación, humedad, punto de rocío, nubosidad, visibilidad, UV,
 * presión, isoterma 0 °C y nieve.
 */
export default function Horas({ horas, id, etiquetaId }: { horas: Hora[]; id: string; etiquetaId: string }) {
  const viento = useViento();
  if (horas.length === 0) {
    return <p id={id} role="tabpanel" aria-labelledby={etiquetaId} className="px-1 py-4 text-sm text-slate-400">Sin datos para este día.</p>;
  }
  return (
    <ul id={id} role="tabpanel" aria-labelledby={etiquetaId} className="divide-y divide-climapp-line/70">
      {horas.map((h) => {
        const lluvia = (h.precip_prob ?? 0) >= 30 || (h.precipitacion ?? 0) > 0;
        return (
          <li key={h.hora}>
            <details className="group">
              <summary className="grid cursor-pointer list-none grid-cols-[3.25rem_2.25rem_3rem_1fr_auto] items-center gap-2 py-2.5 focus-visible:outline-2 focus-visible:outline-climapp-teal [&::-webkit-details-marker]:hidden">
                <span className="text-sm font-medium text-slate-300">{hora(h.hora)}</span>
                <WeatherIcon code={h.estado_cielo} night={esNoche(h.hora)} size={32} />
                <span className="text-lg font-semibold text-white">{grados(h.temperatura)}</span>
                <span className={`text-sm ${lluvia ? "text-sky-300" : "text-slate-400"}`}>
                  {h.precip_prob ?? 0} %
                  {h.precipitacion ? <span className="text-xs"> · {h.precipitacion.toLocaleString("es-CL")} mm</span> : null}
                  <span className="sr-only">, {cielo(h.estado_cielo).texto}</span>
                </span>
                <span className="flex items-center gap-1 text-sm text-slate-300">
                  <Flecha desde={h.viento_dir} />
                  {viento.valor(h.viento)}
                  <span className="text-xs text-slate-400">{viento.unidad}</span>
                  <svg className="ml-1 h-4 w-4 text-slate-500 transition-transform group-open:rotate-180" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
                </span>
              </summary>
              <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-3 rounded-2xl bg-climapp-bg/60 p-3 sm:grid-cols-4">
                <Dato label="Estado" valor={cielo(h.estado_cielo).texto} />
                <Dato label="Sensación térmica" valor={grados(h.sensacion_termica)} />
                <Dato label="Viento" valor={`${viento.valor(h.viento)} ${viento.unidad} ${cardinal(h.viento_dir)}`}
                  detalle={h.rafaga != null ? `ráfagas ${viento.valor(h.rafaga)} ${viento.unidad}` : undefined} />
                <Dato label="Lluvia" valor={`${h.precip_prob ?? 0} % · ${(h.precipitacion ?? 0).toLocaleString("es-CL")} mm`}
                  detalle={h.nieve ? `nieve ${h.nieve} cm` : undefined} />
                <Dato label="Humedad" valor={h.humedad == null ? "–" : `${h.humedad} %`} />
                <Dato label="Punto de rocío" valor={grados(h.punto_rocio)} />
                <Dato label="Nubosidad" valor={h.nubosidad == null ? "–" : `${h.nubosidad} %`} />
                <Dato label="Visibilidad" valor={visibilidad(h.visibilidad)} />
                <Dato label="Índice UV" valor={h.indice_uv == null ? "–" : `${Math.round(h.indice_uv)} · ${categoriaUV(h.indice_uv)}`}
                  detalle={h.indice_uv != null && h.indice_uv >= 3 ? proteccionUV(h.indice_uv) : undefined} />
                <Dato label="Presión" valor={h.presion == null ? "–" : `${h.presion} hPa`} />
                <Dato label="Isoterma 0 °C" valor={h.isoterma_0 == null ? "–" : `${h.isoterma_0.toLocaleString("es-CL")} m`}
                  detalle="nivel de congelación" />
              </dl>
            </details>
          </li>
        );
      })}
    </ul>
  );
}
