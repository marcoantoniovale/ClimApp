import type { ReactNode } from "react";

import type { AvisoUbicacion } from "@/lib/data";
import { fechaHora, oracion, tipoAviso, titulo } from "@/lib/format";

function WarnIcon() {
  return (
    <svg className="mt-0.5 h-5 w-5 shrink-0 text-climapp-warn" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18h.01" />
    </svg>
  );
}

/** Avisos vigentes de la Armada. El estado se indica con ícono y texto, no solo con color. */
export default function WarningList({
  avisos,
  heading = "Avisos vigentes de la Armada",
  extra,
}: {
  avisos: AvisoUbicacion[];
  heading?: string;
  extra?: (aviso: AvisoUbicacion) => ReactNode;
}) {
  if (avisos.length === 0) return null;
  return (
    <section aria-labelledby="avisos" className="rounded-3xl border border-climapp-warn/40 bg-climapp-warn/10 p-5">
      <h2 id="avisos" className="mb-3 text-sm font-semibold uppercase tracking-wide text-climapp-warn">
        {heading} ({avisos.length})
      </h2>
      <ul className="space-y-3">
        {avisos.map((a) => (
          <li key={a.id} className="flex gap-3">
            <WarnIcon />
            <div className="min-w-0 text-sm">
              <p className="font-semibold text-slate-100">
                <span className="mr-2 rounded-md bg-climapp-warn/20 px-1.5 py-0.5 text-xs text-climapp-warn">{tipoAviso(a.tipo)}</span>
                {oracion(a.titulo)}
              </p>
              <p className="text-slate-300">{titulo(a.zona)}</p>
              <p className="text-xs text-slate-400">
                Emitido {fechaHora(a.emitido)} ·{" "}
                <a href={a.documento ?? a.url} target="_blank" rel="noopener" className="underline hover:text-white">
                  Ver aviso oficial
                </a>
                {extra?.(a)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
