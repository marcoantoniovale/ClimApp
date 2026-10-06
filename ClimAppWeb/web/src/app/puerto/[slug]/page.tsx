import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import Pronostico from "@/components/pronostico/Pronostico";
import Search from "@/components/Search";
import { desdeAhora, getPronostico, isValidSlug, slugPuerto } from "@/lib/data";

// ISR, igual que las comunas: se genera en la primera visita y se renueva cada 10 min como máximo.
export const revalidate = 600;

export async function generateStaticParams() {
  return [];
}

const cargar = cache(async (ruta: string) =>
  isValidSlug(ruta) ? getPronostico(slugPuerto(ruta), { revalidate: 600 }) : null,
);

export async function generateMetadata({ params }: PageProps<"/puerto/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const p = await cargar(slug);
  if (!p || p.ubicacion.tipo !== "puerto") return { title: "Puerto no encontrado" };
  const ola = p.marino?.dias[0]?.altura_max;
  return {
    title: `Puerto de ${p.ubicacion.nombre}: viento y oleaje`,
    description: `Viento en nudos, oleaje hora a hora${ola != null ? ` (olas de hasta ${ola} m hoy)` : ""} y avisos de la Armada en el puerto de ${p.ubicacion.nombre}.`,
    alternates: { canonical: `/puerto/${slug}` },
  };
}

export default async function PuertoPage({ params }: PageProps<"/puerto/[slug]">) {
  const { slug } = await params;
  const p = await cargar(slug);
  if (!p || p.ubicacion.tipo !== "puerto") notFound();
  return (
    <div className="space-y-4">
      <Search size="md" />
      <Pronostico p={desdeAhora(p)} etiqueta="⚓ Puerto" />
    </div>
  );
}
