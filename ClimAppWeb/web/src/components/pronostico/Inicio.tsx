"use client";

import { useEffect, useState } from "react";

import { desdeAhora, type PronosticoConAvisos } from "@/lib/data";
import { ErrorUbicacion, permisoConcedido, ubicacionGuardada, ubicarComuna } from "@/lib/ubicacion";

import Search from "../Search";
import Pronostico from "./Pronostico";

type Estado =
  | { tipo: "inicial" }
  | { tipo: "buscando"; texto: string }
  | { tipo: "listo"; p: PronosticoConAvisos; etiqueta: string }
  | { tipo: "error"; mensaje: string };

async function cargarPronostico(slug: string): Promise<PronosticoConAvisos> {
  const res = await fetch(`/api/forecast/${slug}`);
  if (!res.ok) throw new Error(String(res.status));
  return desdeAhora(await res.json());
}

function IconoUbicacion({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </svg>
  );
}

/**
 * Inicio: el tiempo de la ubicación del usuario. Si ya dio permiso, se ubica solo; si no, muestra la
 * última comuna usada en este dispositivo o invita a usar la ubicación. La posición no sale del equipo.
 */
export default function Inicio() {
  const [estado, setEstado] = useState<Estado>({ tipo: "inicial" });

  async function mostrar(slug: string, etiqueta: string) {
    try {
      setEstado({ tipo: "listo", p: await cargarPronostico(slug), etiqueta });
    } catch {
      setEstado({ tipo: "error", mensaje: "No pudimos cargar el pronóstico. Intenta de nuevo en unos segundos." });
    }
  }

  async function ubicar() {
    setEstado({ tipo: "buscando", texto: "Buscando tu ubicación…" });
    try {
      const comuna = await ubicarComuna();
      setEstado({ tipo: "buscando", texto: `Cargando el tiempo en ${comuna.nombre}…` });
      await mostrar(comuna.slug, "Tu ubicación");
    } catch (e) {
      setEstado({ tipo: "error", mensaje: e instanceof ErrorUbicacion ? e.message : "No pudimos obtener tu ubicación." });
    }
  }

  useEffect(() => {
    let cancelado = false;
    (async () => {
      if (await permisoConcedido()) {
        if (!cancelado) ubicar();
        return;
      }
      const guardada = ubicacionGuardada();
      if (guardada && !cancelado) {
        setEstado({ tipo: "buscando", texto: `Cargando el tiempo en ${guardada.nombre}…` });
        await mostrar(guardada.slug, "Tu última ubicación");
      }
    })();
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al abrir la página
  }, []);

  if (estado.tipo === "listo") {
    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <div className="flex-1"><Search size="md" /></div>
          <button type="button" onClick={ubicar}
            className="flex shrink-0 items-center gap-2 rounded-2xl border border-climapp-line bg-climapp-card px-3 text-sm font-medium text-climapp-teal hover:border-climapp-teal"
            aria-label="Actualizar con mi ubicación">
            <IconoUbicacion /> <span className="hidden sm:inline">Mi ubicación</span>
          </button>
        </div>
        <Pronostico p={estado.p} etiqueta={estado.etiqueta} />
      </div>
    );
  }

  return (
    <section className="space-y-5 pt-4 text-center">
      <div className="rounded-3xl border border-climapp-line bg-climapp-card/70 p-6 sm:p-8">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">El tiempo donde estás</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-300">
          Pronóstico hora a hora para hoy y los próximos 6 días. Tu ubicación se usa solo en este dispositivo.
        </p>
        {estado.tipo === "buscando" ? (
          <p className="mt-6 flex items-center justify-center gap-2 text-climapp-teal" aria-live="polite">
            <IconoUbicacion className="h-5 w-5 animate-pulse" /> {estado.texto}
          </p>
        ) : (
          <button type="button" onClick={ubicar}
            className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-sky-700 px-6 py-3 text-base font-semibold text-white hover:bg-sky-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-climapp-teal">
            <IconoUbicacion /> Ver el tiempo donde estoy
          </button>
        )}
        {estado.tipo === "error" && <p className="mt-4 text-sm text-climapp-warn" aria-live="polite">{estado.mensaje}</p>}
      </div>
      <div className="text-left">
        <p className="mb-2 text-sm text-slate-400">O busca una comuna:</p>
        <Search />
      </div>
    </section>
  );
}
