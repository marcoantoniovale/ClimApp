import type { Metadata } from "next";
import ListaPasos from "@/components/pasos/ListaPasos";
import { getPasos, type PasoResumen } from "@/lib/data";

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

      {pasos.length > 0 && <ListaPasos pasos={pasos} dmc={dmc} />}
    </div>
  );
}
