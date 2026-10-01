"use client";

import { useRouter } from "next/navigation";
import { type KeyboardEvent, useId, useMemo, useRef, useState } from "react";

import type { UbicacionIndice } from "@/lib/data";
import { region } from "@/lib/format";

const normalize = (s: string) =>
  s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

type Entry = UbicacionIndice & { key: string; aliasKey: string };

const MAX_RESULTS = 8;

/** Buscador de comunas (combobox accesible). Carga el catálogo al enfocarlo. */
export default function Search({ autoFocus = false, size = "lg" }: { autoFocus?: boolean; size?: "lg" | "md" }) {
  const router = useRouter();
  const listId = useId();
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const loading = useRef(false);

  async function load() {
    if (entries || loading.current) return;
    loading.current = true;
    try {
      const res = await fetch("/api/locations");
      if (!res.ok) throw new Error(String(res.status));
      const data: UbicacionIndice[] = await res.json();
      setEntries(data.map((u) => ({ ...u, key: normalize(u.nombre), aliasKey: normalize(u.alias ?? "") })));
    } catch {
      setError(true);
    } finally {
      loading.current = false;
    }
  }

  const results = useMemo(() => {
    const q = normalize(query);
    if (!q || !entries) return [];
    const score = (e: Entry) =>
      e.key.startsWith(q) || e.aliasKey.startsWith(q) ? 0
        : e.key.split(" ").some((w) => w.startsWith(q)) ? 1
          : e.key.includes(q) || e.aliasKey.includes(q) ? 2 : 3;
    return entries
      .map((e) => [score(e), e] as const)
      .filter(([s]) => s < 3)
      .sort((a, b) => a[0] - b[0] || a[1].nombre.localeCompare(b[1].nombre, "es"))
      .slice(0, MAX_RESULTS)
      .map(([, e]) => e);
  }, [entries, query]);

  const go = (entry: Entry | undefined) => {
    if (!entry) return;
    setOpen(false);
    setQuery(entry.nombre);
    router.push(`/comuna/${entry.slug}`);
  };

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(results[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showList = open && query.trim().length > 0;
  const big = size === "lg";

  return (
    <div className="relative w-full">
      <label htmlFor={`${listId}-input`} className="sr-only">Buscar comuna</label>
      <div className="relative">
        <svg className={`pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 ${big ? "h-5 w-5" : "h-4 w-4"}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" />
        </svg>
        <input
          id={`${listId}-input`}
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && results[active] ? `${listId}-${results[active].slug}` : undefined}
          autoComplete="off"
          autoFocus={autoFocus}
          placeholder="Busca tu comuna o ciudad…"
          value={query}
          onFocus={() => { load(); setOpen(true); }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => { setQuery(e.target.value); setActive(0); setOpen(true); }}
          onKeyDown={onKeyDown}
          className={`w-full rounded-2xl border border-climapp-line bg-climapp-card text-slate-100 placeholder:text-slate-400 focus:border-climapp-teal focus:outline-none focus:ring-2 focus:ring-climapp-teal/40 ${big ? "py-4 pl-12 pr-4 text-lg" : "py-2.5 pl-10 pr-3 text-base"}`}
        />
      </div>
      {showList && (
        <ul id={listId} role="listbox" aria-label="Comunas"
          className="absolute z-40 mt-2 max-h-80 w-full overflow-auto rounded-2xl border border-climapp-line bg-climapp-card py-1 shadow-xl">
          {error && <li className="px-4 py-3 text-sm text-slate-300">No se pudo cargar el listado de comunas.</li>}
          {!error && !entries && <li className="px-4 py-3 text-sm text-slate-300">Cargando…</li>}
          {entries && results.length === 0 && <li className="px-4 py-3 text-sm text-slate-300">Sin resultados para “{query}”.</li>}
          {results.map((r, i) => (
            <li
              key={r.slug}
              id={`${listId}-${r.slug}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); go(r); }}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-baseline justify-between gap-3 px-4 py-2.5 ${i === active ? "bg-climapp-line/70" : ""}`}
            >
              <span className="font-medium text-slate-100">{r.nombre}</span>
              <span className="truncate text-xs text-slate-400">{r.costera ? "Costa · " : ""}{region(r.region)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
