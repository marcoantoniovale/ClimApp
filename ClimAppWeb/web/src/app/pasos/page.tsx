import type { Metadata } from "next";
import Link from "next/link";

import Alertas from "@/components/pasos/Alertas";
import WeatherIcon from "@/components/WeatherIcon";
import { getPasos, rutaPaso, type PasoResumen } from "@/lib/data";
import { grados, region } from "@/lib/format";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Pasos fronterizos",
  description: "Alertas de nieve, ventisca y viento en los pasos fronterizos de Chile, con el pronóstico oficial de la DMC.",
};

const UPF_URL = "https://www.pasosfronterizos.gov.cl/";

async function cargar() {
  try {
    return await getPasos({ revalidate: 600 });
  } catch {
    return { pasos: [] as PasoResumen[], dmc: {} };
  }
}

export default async function PasosPage() {
  const { pasos, dmc } = await cargar();
  const regiones = new Map<string, PasoResumen[]>();
  for (const p of pasos) regiones.set(p.region, [...(regiones.get(p.region) ?? []), p]);
  const conAlerta = pasos.filter((p) => p.alertas.length > 0).length;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Pasos fronterizos</h1>
        <p className="mt-1 text-sm text-slate-300">
          Alertas calculadas con el modelo ICON a la altura de cada paso y pronóstico oficial de la DMC.{" "}
          {pasos.length > 0 && <>{conAlerta} de {pasos.length} pasos con alertas en los próximos días.</>}
        </p>
        <p className="mt-2 rounded-xl border border-climapp-line bg-climapp-card/70 px-3 py-2 text-sm text-slate-300">
          ¿Está abierto? El estado oficial lo informa la{" "}
          <a href={UPF_URL} target="_blank" rel="noopener" className="font-semibold text-climapp-teal underline">
            Unidad de Pasos Fronterizos
          </a>
          . Revísalo antes de viajar.
        </p>
      </header>

      {pasos.length === 0 && <p className="text-slate-300">No hay datos de pasos por ahora.</p>}

      {[...regiones.entries()].map(([reg, lista]) => (
        <section key={reg} aria-labelledby={`r-${reg}`} className="space-y-2">
          <h2 id={`r-${reg}`} className="text-sm font-semibold uppercase tracking-wide text-slate-400">{region(reg)}</h2>
          <ul className="space-y-2">
            {lista.map((p) => (
              <li key={p.slug}>
                <Link href={`/paso/${rutaPaso(p.slug)}`}
                  className="block rounded-2xl border border-climapp-line bg-climapp-card/70 p-4 hover:border-climapp-teal">
                  <div className="flex items-center gap-3">
                    <WeatherIcon code={p.hoy.estado_cielo} size={36} className="shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-slate-100">{p.nombre}</p>
                      <p className="text-xs text-slate-400">
                        {p.altura_m?.toLocaleString("es-CL")} m · hoy {grados(p.hoy.temperatura_min)} / {grados(p.hoy.temperatura_max)}
                      </p>
                    </div>
                    {p.alertas.length > 0 && (
                      <span className={`shrink-0 rounded-lg px-2 py-0.5 text-xs font-semibold ${p.alertas.some((a) => a.nivel === "alerta") ? "bg-orange-500/20 text-orange-200" : "bg-climapp-warn/15 text-amber-100"}`}>
                        {p.alertas.some((a) => a.nivel === "alerta") ? "Alerta" : "Aviso"}
                      </span>
                    )}
                  </div>
                  {p.alertas.length > 0 && <div className="mt-2"><Alertas alertas={p.alertas.slice(0, 4)} compacto /></div>}
                  {dmc[p.slug]?.dias[0]?.texto && (
                    <p className="mt-2 line-clamp-2 text-xs text-slate-400">
                      DMC, {dmc[p.slug].dias[0].etiqueta}: {dmc[p.slug].dias[0].texto}
                    </p>
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
