import type { Metadata } from "next";
import Link from "next/link";

import WarningList from "@/components/weather/WarningList";
import { getAvisos, getIndice } from "@/lib/data";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Avisos marítimos vigentes",
  description: "Avisos de marejadas, mal tiempo y temporal vigentes del Servicio Meteorológico de la Armada de Chile.",
};

async function cargar() {
  try {
    const [avisos, indice] = await Promise.all([
      getAvisos({ revalidate: 600 }),
      getIndice({ revalidate: 3600 }),
    ]);
    return { avisos: avisos?.avisos ?? [], nombres: new Map((indice ?? []).map((u) => [u.slug, u.nombre])) };
  } catch {
    return { avisos: [], nombres: new Map<string, string>() };
  }
}

export default async function AvisosPage() {
  const { avisos, nombres } = await cargar();
  const comunas = new Map(avisos.map((a) => [a.id, a.ubicaciones]));

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Avisos marítimos vigentes</h1>
        <p className="mt-1 text-sm text-slate-300">
          Publicados por el Servicio Meteorológico de la Armada de Chile. Las comunas indicadas son una
          aproximación según la zona del aviso; el documento oficial es el que vale.
        </p>
      </header>

      {avisos.length === 0 ? (
        <p className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-5 text-slate-300">No hay avisos vigentes.</p>
      ) : (
        <WarningList
          avisos={avisos}
          heading="Avisos"
          extra={(a) => {
            const slugs = comunas.get(a.id) ?? [];
            if (slugs.length === 0) return null;
            const visibles = slugs.slice(0, 6);
            return (
              <span className="mt-1 block">
                Comunas:{" "}
                {visibles.map((s, i) => (
                  <span key={s}>
                    {i > 0 && ", "}
                    <Link href={`/comuna/${s}`} className="underline hover:text-white">{nombres.get(s) ?? s}</Link>
                  </span>
                ))}
                {slugs.length > visibles.length && ` y ${slugs.length - visibles.length} más`}
              </span>
            );
          }}
        />
      )}
    </div>
  );
}
