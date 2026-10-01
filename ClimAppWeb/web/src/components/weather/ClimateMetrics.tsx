import type { Dia, Hora } from "@/lib/data";
import { cardinal, categoriaUV } from "@/lib/format";

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-2xl border border-climapp-line bg-climapp-card/70 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-light text-slate-100">{value}</p>
      {detail && <p className="text-xs text-slate-400">{detail}</p>}
    </div>
  );
}

/** Indicadores rápidos de la hora actual y del día. */
export default function ClimateMetrics({ ahora, hoy }: { ahora: Hora | undefined; hoy: Dia | undefined }) {
  if (!ahora) return null;
  const uv = hoy?.indice_uv_max ?? null;
  return (
    <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <Metric
        label="Viento"
        value={ahora.viento == null ? "–" : `${ahora.viento} km/h`}
        detail={[cardinal(ahora.viento_dir) && `Desde el ${cardinal(ahora.viento_dir)}`, ahora.rafaga != null && `ráfagas ${ahora.rafaga} km/h`]
          .filter(Boolean).join(" · ")}
      />
      <Metric label="Humedad" value={ahora.humedad == null ? "–" : `${ahora.humedad} %`} />
      <Metric
        label="Lluvia"
        value={ahora.precip_prob == null ? "–" : `${ahora.precip_prob} %`}
        detail={hoy?.precipitacion ? `${hoy.precipitacion} mm hoy` : "probabilidad esta hora"}
      />
      <Metric label="Índice UV máx." value={uv == null ? "–" : String(Math.round(uv))} detail={categoriaUV(uv)} />
      <Metric label="Presión" value={ahora.presion == null ? "–" : `${ahora.presion} hPa`} detail="a nivel del mar" />
      <Metric
        label="Ráfaga máx. hoy"
        value={hoy?.rafaga_max == null ? "–" : `${hoy.rafaga_max} km/h`}
      />
    </section>
  );
}
