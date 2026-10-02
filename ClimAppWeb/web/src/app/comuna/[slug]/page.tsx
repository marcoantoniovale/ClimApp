import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import Pronostico from "@/components/pronostico/Pronostico";
import Search from "@/components/Search";
import { desdeAhora, getPronostico, isValidSlug } from "@/lib/data";
import { grados, region } from "@/lib/format";

// ISR: cada página se genera en la primera visita y se renueva cada 10 min como máximo.
export const revalidate = 600;

export async function generateStaticParams() {
  return [];
}

const cargar = cache(async (slug: string) =>
  isValidSlug(slug) ? getPronostico(slug, { revalidate: 600 }) : null,
);

export async function generateMetadata({ params }: PageProps<"/comuna/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const p = await cargar(slug);
  if (!p) return { title: "Comuna no encontrada" };
  const hoy = p.dias[0];
  return {
    title: `El tiempo en ${p.ubicacion.nombre}`,
    description: `Pronóstico para ${p.ubicacion.nombre} (${region(p.ubicacion.region)}): hoy máx. ${grados(hoy?.temperatura_max)}, mín. ${grados(hoy?.temperatura_min)}. Hora a hora y 7 días${p.ubicacion.es_costera ? ", oleaje" : ""} y avisos de la Armada.`,
    alternates: { canonical: `/comuna/${slug}` },
  };
}

export default async function ComunaPage({ params }: PageProps<"/comuna/[slug]">) {
  const { slug } = await params;
  const p = await cargar(slug);
  if (!p) notFound();

  // El JSON se regenera con cada corrida: se descartan las horas pasadas (la página se renueva cada 10 min).
  return (
    <div className="space-y-4">
      <Search size="md" />
      <Pronostico p={desdeAhora(p)} />
    </div>
  );
}
