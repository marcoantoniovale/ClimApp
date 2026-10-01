import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import Search from "@/components/Search";
import ClimateMetrics from "@/components/weather/ClimateMetrics";
import CurrentWeather from "@/components/weather/CurrentWeather";
import HourlyForecast from "@/components/weather/HourlyForecast";
import MarineForecast from "@/components/weather/MarineForecast";
import WarningList from "@/components/weather/WarningList";
import WeeklyForecast from "@/components/weather/WeeklyForecast";
import { getPronostico, isValidSlug } from "@/lib/data";
import { fechaLocal, grados, region } from "@/lib/format";

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
    description: `Pronóstico para ${p.ubicacion.nombre} (${region(p.ubicacion.region)}): hoy máx. ${grados(hoy?.temperatura_max)}, mín. ${grados(hoy?.temperatura_min)}. Por hora, 7 días${p.ubicacion.es_costera ? ", oleaje" : ""} y avisos de la Armada.`,
    alternates: { canonical: `/comuna/${slug}` },
  };
}

export default async function ComunaPage({ params }: PageProps<"/comuna/[slug]">) {
  const { slug } = await params;
  const p = await cargar(slug);
  if (!p) notFound();

  // El JSON se regenera cada 6 h: se descartan las horas ya pasadas (la página se renueva cada 10 min).
  const horaActual = new Date();
  horaActual.setMinutes(0, 0, 0);
  const horas = p.horas.filter((h) => Date.parse(h.hora) >= horaActual.getTime());
  const ahora = horas[0];
  const hoy = p.dias.find((d) => d.fecha === (ahora ? fechaLocal(ahora.hora) : p.dias[0]?.fecha)) ?? p.dias[0];

  return (
    <div className="space-y-4">
      <Search size="md" />
      <CurrentWeather
        nombre={p.ubicacion.nombre}
        region={p.ubicacion.region}
        ahora={ahora}
        hoy={hoy}
        observacion={p.observacion}
        actualizado={p.actualizado}
      />
      <WarningList avisos={p.avisos} />
      <HourlyForecast horas={horas} />
      <ClimateMetrics ahora={ahora} hoy={hoy} />
      <WeeklyForecast dias={p.dias} />
      {p.ubicacion.es_costera && <MarineForecast marino={p.marino} />}
      <p className="px-1 text-xs text-slate-400">
        Fiabilidad: el rango “modelos” muestra la diferencia entre GFS, ECMWF e ICON. Mientras más amplio, más incierto el pronóstico.
      </p>
    </div>
  );
}
