import type { AlertaPaso } from "@/lib/data";
import { nombreDia } from "@/lib/format";

const ESTILO = {
  alerta: "border-orange-400/50 bg-orange-500/15 text-orange-200",
  aviso: "border-climapp-warn/40 bg-climapp-warn/10 text-amber-100",
} as const;

function Icono({ nivel }: { nivel: AlertaPaso["nivel"] }) {
  return (
    <svg className={`mt-0.5 h-4 w-4 shrink-0 ${nivel === "alerta" ? "text-orange-300" : "text-climapp-warn"}`} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18h.01" />
    </svg>
  );
}

/** Alertas de un paso agrupadas por día. Nivel indicado con ícono y texto (no solo color). */
export default function Alertas({ alertas, compacto = false }: { alertas: AlertaPaso[]; compacto?: boolean }) {
  if (alertas.length === 0) {
    return <p className="text-sm text-slate-400">Sin alertas en los próximos días.</p>;
  }
  const porDia = new Map<string, AlertaPaso[]>();
  for (const a of alertas) porDia.set(a.fecha, [...(porDia.get(a.fecha) ?? []), a]);

  return (
    <ul className={compacto ? "space-y-1" : "space-y-2"}>
      {[...porDia.entries()].map(([fecha, lista]) => (
        <li key={fecha} className="text-sm">
          <span className="mr-2 font-semibold text-slate-200">{nombreDia(fecha)}</span>
          <span className="inline-flex flex-wrap gap-1.5 align-middle">
            {lista.map((a) => (
              <span key={a.tipo + a.texto} className={`inline-flex items-start gap-1 rounded-lg border px-2 py-0.5 text-xs ${ESTILO[a.nivel]}`}>
                <Icono nivel={a.nivel} />
                <span><span className="sr-only">{a.nivel === "alerta" ? "Alerta: " : "Aviso: "}</span>{a.texto}</span>
              </span>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}
