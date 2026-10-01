"use client";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="space-y-4 pt-12 text-center">
      <h1 className="text-2xl font-semibold">No pudimos cargar los datos</h1>
      <p className="text-slate-300">Puede ser algo pasajero. Intenta de nuevo en unos segundos.</p>
      <button type="button" onClick={reset} className="rounded-xl bg-sky-700 px-4 py-2 font-medium text-white hover:bg-sky-600">
        Reintentar
      </button>
    </div>
  );
}
