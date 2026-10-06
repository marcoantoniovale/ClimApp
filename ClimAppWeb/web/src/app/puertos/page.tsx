import type { Metadata } from "next";
import Link from "next/link";

import Flecha from "@/components/pronostico/Flecha";
import WeatherIcon from "@/components/WeatherIcon";
import { getPuertos, rutaPuerto } from "@/lib/data";
import { cardinal, nudos, region } from "@/lib/format";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Puertos",
  description: "Viento en nudos y oleaje hora a hora en los puertos de Chile, con los avisos de la Armada.",
};

async function cargar() {
  try {
    return await getPuertos({ revalidate: 600 });
  } catch {
    return [];
  }
}

const m = (v: number | null | undefined) => (v == null ? "–" : `${v.toLocaleString("es-CL")} m`);

export default async function PuertosPage() {
  const puertos = await cargar();
  const regiones = new Map<string, typeof puertos>();
  for (const p of puertos) regiones.set(p.region, [...(regiones.get(p.region) ?? []), p]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Puertos</h1>
        <p className="mt-1 text-sm text-slate-300">
          Viento en nudos y oleaje en {puertos.length} puertos, de norte a sur. Toca un puerto para verlo hora a hora.
        </p>
        <p className="mt-2 rounded-xl border border-climapp-line bg-climapp-card/70 px-3 py-2 text-sm text-slate-300">
          El estado de cada puerto (abierto o cerrado) lo informa la{" "}
          <a href="https://meteoarmada.directemar.cl" target="_blank" rel="noopener" className="font-semibold text-climapp-teal underline">
            Armada de Chile
          </a>
          . Revísalo antes de zarpar.
        </p>
      </header>

      {[...regiones.entries()].map(([reg, lista]) => (
        <section key={reg} aria-labelledby={`r-${reg}`} className="space-y-2">
          <h2 id={`r-${reg}`} className="text-sm font-semibold uppercase tracking-wide text-slate-400">{region(reg)}</h2>
          <ul className="space-y-2">
            {lista.map((p) => (
              <li key={p.slug}>
                <Link href={`/puerto/${rutaPuerto(p.slug)}`}
                  className="flex items-center gap-3 rounded-2xl border border-climapp-line bg-climapp-card/70 p-4 hover:border-climapp-teal">
                  <WeatherIcon code={p.ahora.estado_cielo} size={36} className="shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-100">
                      {p.nombre}
                      {p.comuna && p.comuna.nombre !== p.nombre && <span className="font-normal text-slate-400"> · {p.comuna.nombre}</span>}
                    </p>
                    <p className="flex flex-wrap items-center gap-x-3 text-xs text-slate-300">
                      <span className="inline-flex items-center gap-1">
                        <Flecha desde={p.ahora.viento_dir} size={12} />
                        {nudos(p.ahora.viento)} kn {cardinal(p.ahora.viento_dir)}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Flecha desde={p.ahora.ola_dir} size={12} />
                        olas {m(p.ahora.ola)}{p.ahora.periodo != null && ` · ${p.ahora.periodo} s`}
                      </span>
                    </p>
                    <p className="text-xs text-slate-400">
                      Hoy: ráfagas hasta {nudos(p.hoy.rafaga_max)} kn · olas hasta {m(p.hoy.ola_max)}
                    </p>
                  </div>
                  {p.avisos > 0 && (
                    <span className="shrink-0 rounded-lg bg-climapp-warn/15 px-2 py-0.5 text-xs font-semibold text-amber-100">
                      {p.avisos === 1 ? "1 aviso" : `${p.avisos} avisos`}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
