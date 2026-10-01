import Image from "next/image";
import Link from "next/link";

import Search from "@/components/Search";
import { getAvisos } from "@/lib/data";
import { tipoAviso } from "@/lib/format";

export const revalidate = 600;

const CIUDADES = [
  ["arica", "Arica"], ["iquique", "Iquique"], ["antofagasta", "Antofagasta"], ["la-serena", "La Serena"],
  ["valparaiso", "Valparaíso"], ["vina-del-mar", "Viña del Mar"], ["santiago", "Santiago"], ["concepcion", "Concepción"],
  ["temuco", "Temuco"], ["valdivia", "Valdivia"], ["puerto-montt", "Puerto Montt"], ["punta-arenas", "Punta Arenas"],
] as const;

async function avisosVigentes() {
  try {
    return (await getAvisos({ revalidate: 600 }))?.avisos ?? [];
  } catch {
    return [];
  }
}

export default async function Home() {
  const avisos = await avisosVigentes();
  const porTipo = Object.entries(
    avisos.reduce<Record<string, number>>((acc, a) => ({ ...acc, [a.tipo]: (acc[a.tipo] ?? 0) + 1 }), {}),
  );

  return (
    <div className="space-y-8">
      <section className="flex flex-col items-center pt-6 text-center sm:pt-12">
        <Image src="/brand/climapp_logo.svg" alt="" width={96} height={96} priority className="rounded-3xl" />
        <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">El tiempo en tu comuna</h1>
        <p className="mt-2 max-w-md text-slate-300">
          Pronóstico para las 346 comunas de Chile combinando tres modelos globales, con avisos marítimos y oleaje de la Armada.
        </p>
        <div className="mt-6 w-full max-w-xl">
          <Search />
        </div>
      </section>

      {avisos.length > 0 && (
        <Link
          href="/avisos"
          className="flex items-start gap-3 rounded-3xl border border-climapp-warn/40 bg-climapp-warn/10 p-4 hover:bg-climapp-warn/15"
        >
          <svg className="mt-0.5 h-5 w-5 shrink-0 text-climapp-warn" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18h.01" />
          </svg>
          <span className="text-sm">
            <strong className="text-climapp-warn">{avisos.length} avisos marítimos vigentes</strong>
            <span className="block text-slate-300">
              {porTipo.map(([tipo, n]) => `${tipoAviso(tipo)} (${n})`).join(" · ")} — ver detalle
            </span>
          </span>
        </Link>
      )}

      <section aria-labelledby="ciudades">
        <h2 id="ciudades" className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Ciudades</h2>
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {CIUDADES.map(([slug, nombre]) => (
            <li key={slug}>
              <Link
                href={`/comuna/${slug}`}
                className="block rounded-2xl border border-climapp-line bg-climapp-card/70 px-4 py-3 font-medium hover:border-climapp-teal hover:text-white"
              >
                {nombre}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
