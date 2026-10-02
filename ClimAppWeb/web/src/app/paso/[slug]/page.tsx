import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import Alertas from "@/components/pasos/Alertas";
import Pronostico from "@/components/pronostico/Pronostico";
import { desdeAhora, getPaso, isValidSlug } from "@/lib/data";
import { region } from "@/lib/format";

export const revalidate = 600;

export async function generateStaticParams() {
  return [];
}

const UPF_URL = "https://www.pasosfronterizos.gov.cl/";

const cargar = cache(async (ruta: string) => (isValidSlug(ruta) ? getPaso(ruta, { revalidate: 600 }) : null));

export async function generateMetadata({ params }: PageProps<"/paso/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const d = await cargar(slug);
  if (!d) return { title: "Paso no encontrado" };
  return {
    title: `Paso ${d.p.ubicacion.nombre}`,
    description: `Clima en el paso ${d.p.ubicacion.nombre} (${d.p.ubicacion.altura_m} m): alertas de nieve y viento, pronóstico hora a hora y pronóstico oficial de la DMC.`,
    alternates: { canonical: `/paso/${slug}` },
  };
}

export default async function PasoPage({ params }: PageProps<"/paso/[slug]">) {
  const { slug } = await params;
  const d = await cargar(slug);
  if (!d) notFound();
  const { p, alertas, dmc } = d;

  return (
    <div className="space-y-4">
      <nav className="text-sm"><Link href="/pasos" className="text-climapp-teal hover:underline">← Pasos fronterizos</Link></nav>

      <section aria-labelledby="estado" className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-climapp-teal">Paso fronterizo</p>
        <h1 id="estado" className="text-2xl font-semibold tracking-tight">{p.ubicacion.nombre}</h1>
        <p className="text-sm text-slate-400">{region(p.ubicacion.region)} · {p.ubicacion.altura_m?.toLocaleString("es-CL")} m de altura</p>
        <h2 className="mb-2 mt-4 text-sm font-semibold uppercase tracking-wide text-slate-400">Alertas (modelo ICON)</h2>
        <Alertas alertas={alertas} />
        <p className="mt-4 rounded-xl bg-climapp-bg/60 px-3 py-2 text-sm text-slate-300">
          Estado oficial (abierto o cerrado):{" "}
          <a href={UPF_URL} target="_blank" rel="noopener" className="font-semibold text-climapp-teal underline">Unidad de Pasos Fronterizos</a>.
        </p>
      </section>

      {dmc && dmc.dias.length > 0 && (
        <section aria-labelledby="dmc" className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-5">
          <h2 id="dmc" className="text-sm font-semibold uppercase tracking-wide text-slate-400">Pronóstico oficial DMC</h2>
          {dmc.emision && <p className="text-xs text-slate-400">Emitido el {dmc.emision.toLowerCase()}</p>}
          {dmc.apreciacion && <p className="mt-2 text-sm text-slate-300">Situación: {dmc.apreciacion}</p>}
          <ul className="mt-3 divide-y divide-climapp-line/70">
            {dmc.dias.map((dia) => (
              <li key={dia.etiqueta ?? dia.fecha} className="py-2.5 text-sm">
                <p className="font-semibold text-slate-100">{dia.etiqueta}</p>
                <p className="text-slate-300">{dia.texto}</p>
                {dia.isoterma && <p className="text-xs text-slate-400">Isoterma 0 °C: {dia.isoterma.replaceAll("-", " – ")} m</p>}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-400">
            Fuente:{" "}
            <a href="https://archivos.meteochile.gob.cl/portaldmc/pasos/pronostico_pasos_fronterizos.php" target="_blank" rel="noopener" className="underline">
              Dirección Meteorológica de Chile
            </a>.
          </p>
        </section>
      )}

      <Pronostico p={desdeAhora(p)} />
    </div>
  );
}
