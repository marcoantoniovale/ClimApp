import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import Pronostico from "@/components/pronostico/Pronostico";
import Search from "@/components/Search";
import { desdeAhora, getLugar, isValidSlug } from "@/lib/data";
import { grados } from "@/lib/format";

// ISR, igual que las comunas: se genera en la primera visita y se renueva cada 10 min como máximo.
export const revalidate = 600;

export async function generateStaticParams() {
  return [];
}

const cargar = cache(async (comuna: string, slug: string) =>
  isValidSlug(comuna) && isValidSlug(slug) ? getLugar(comuna, slug, { revalidate: 600 }) : null,
);

export async function generateMetadata({ params }: PageProps<"/lugar/[comuna]/[slug]">): Promise<Metadata> {
  const { comuna, slug } = await params;
  const p = await cargar(comuna, slug);
  if (!p) return { title: "Lugar no encontrado" };
  const hoy = p.dias[0];
  return {
    title: `El tiempo en ${p.ubicacion.nombre}, ${p.ubicacion.comuna?.nombre}`,
    description: `Pronóstico para ${p.ubicacion.nombre} (comuna de ${p.ubicacion.comuna?.nombre}): hoy máx. ${grados(hoy?.temperatura_max)}, mín. ${grados(hoy?.temperatura_min)}. Corregido con las estaciones de medición más cercanas.`,
    alternates: { canonical: `/lugar/${comuna}/${slug}` },
  };
}

export default async function LugarPage({ params }: PageProps<"/lugar/[comuna]/[slug]">) {
  const { comuna, slug } = await params;
  const p = await cargar(comuna, slug);
  if (!p) notFound();
  return (
    <div className="space-y-4">
      <Search size="md" />
      <Pronostico p={desdeAhora(p)} />
    </div>
  );
}
