"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import type { PasoDmc, PasoResumen } from "@/lib/data";
import { rutaPaso } from "@/lib/data";
import { grados, region } from "@/lib/format";

import WeatherIcon from "../WeatherIcon";
import Alertas from "./Alertas";

const normalizar = (s: string) =>
  s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

// El filtro y el último paso abierto se guardan en la sesión del navegador: al volver desde un paso
// se recupera el filtro y la página vuelve a ese paso (si no, la lista cambia de largo y se pierde la posición).
const CLAVE = "climapp:pasos:lista";
type Guardado = { texto?: string; soloAlertas?: boolean; abierto?: string };

function leer(): Guardado {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE) ?? "{}") as Guardado;
  } catch {
    return {};
  }
}

function guardar(cambios: Guardado) {
  try {
    sessionStorage.setItem(CLAVE, JSON.stringify({ ...leer(), ...cambios }));
  } catch {
    // sin almacenamiento (modo privado): solo se pierde la comodidad
  }
}

/** Lista de pasos por región con buscador (nombre, región o "con alerta"). */
export default function ListaPasos({ pasos, dmc }: { pasos: PasoResumen[]; dmc: Record<string, PasoDmc> }) {
  const [texto, setTexto] = useState("");
  const [soloAlertas, setSoloAlertas] = useState(false);
  const id = useId();
  const [restaurado, setRestaurado] = useState(false);
  const volverA = useRef<string | null>(null);

  // Al montar: recuperar el filtro y recordar a qué paso volver.
  useEffect(() => {
    let cancelado = false;
    queueMicrotask(() => {
      if (cancelado) return;
      const g = leer();
      volverA.current = g.abierto ?? null;
      if (g.texto) setTexto(g.texto);
      if (g.soloAlertas) setSoloAlertas(true);
      setRestaurado(true);
    });
    return () => {
      cancelado = true;
    };
  }, []);

  // Guardar el filtro (después de recuperarlo, para no pisarlo con el estado inicial).
  useEffect(() => {
    if (restaurado) guardar({ texto, soloAlertas });
  }, [restaurado, texto, soloAlertas]);

  const filtrados = useMemo(() => {
    const q = normalizar(texto);
    return pasos.filter((p) =>
      (!soloAlertas || p.alertas.length > 0) &&
      (!q || normalizar(`${p.nombre} ${region(p.region)} ${p.region}`).includes(q)));
  }, [pasos, texto, soloAlertas]);

  // Con la lista ya filtrada, volver al paso que se abrió (una sola vez).
  useEffect(() => {
    const slug = volverA.current;
    if (!restaurado || !slug) return;
    volverA.current = null;
    guardar({ abierto: undefined });
    requestAnimationFrame(() => document.getElementById(`paso-${slug}`)?.scrollIntoView({ block: "center" }));
  }, [restaurado, filtrados]);

  const regiones = new Map<string, PasoResumen[]>();
  for (const p of filtrados) regiones.set(p.region, [...(regiones.get(p.region) ?? []), p]);

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <label htmlFor={id} className="sr-only">Buscar paso fronterizo</label>
        <div className="relative">
          <svg className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" />
          </svg>
          <input
            id={id}
            type="search"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Busca un paso o región… (ej. Libertadores, Aysén)"
            autoComplete="off"
            className="w-full rounded-2xl border border-climapp-line bg-climapp-card py-2.5 pl-10 pr-3 text-base text-slate-100 placeholder:text-slate-400 focus:border-climapp-teal focus:outline-none focus:ring-2 focus:ring-climapp-teal/40"
          />
        </div>
        <div className="flex items-center justify-between gap-3 text-sm">
          <label className="flex cursor-pointer items-center gap-2 text-slate-300">
            <input type="checkbox" checked={soloAlertas} onChange={(e) => setSoloAlertas(e.target.checked)}
              className="h-4 w-4 accent-sky-600" />
            Solo pasos con alertas
          </label>
          <span className="text-xs text-slate-400" aria-live="polite">
            {filtrados.length} de {pasos.length} pasos
          </span>
        </div>
      </div>

      {filtrados.length === 0 && (
        <p className="rounded-2xl border border-climapp-line bg-climapp-card/70 p-4 text-sm text-slate-300">
          No hay pasos que coincidan con “{texto}”.
        </p>
      )}

      {[...regiones.entries()].map(([reg, lista]) => (
        <section key={reg} aria-labelledby={`r-${reg}`} className="space-y-2">
          <h2 id={`r-${reg}`} className="text-sm font-semibold uppercase tracking-wide text-slate-400">{region(reg)}</h2>
          <ul className="space-y-2">
            {lista.map((p) => (
              <li key={p.slug} id={`paso-${p.slug}`} className="scroll-mt-24">
                <Link href={`/paso/${rutaPaso(p.slug)}`} onClick={() => guardar({ abierto: p.slug })}
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
