import Image from "next/image";

export default function Footer() {
  return (
    <footer className="mx-auto w-full max-w-4xl px-4 pb-28 pt-10 text-xs leading-relaxed text-slate-400 md:pb-10">
      <p>
        Pronóstico del modelo ICON (Servicio Meteorológico Alemán, DWD); índice UV y visibilidad del modelo GFS. Datos meteorológicos de{" "}
        <a href="https://open-meteo.com" className="underline hover:text-white" rel="noopener">Open-Meteo</a>{" "}
        (<a href="https://creativecommons.org/licenses/by/4.0/deed.es" className="underline hover:text-white" rel="noopener">CC BY 4.0</a>);
        observaciones y avisos del{" "}
        <a href="https://meteoarmada.directemar.cl" className="underline hover:text-white" rel="noopener">
          Servicio Meteorológico de la Armada de Chile
        </a>
        . Ante una emergencia, siga siempre los avisos oficiales.
      </p>

      <div className="mt-6 flex items-center gap-2 border-t border-climapp-line/60 pt-4">
        <Image src="/brand/msins-mark.svg" alt="" width={24} height={24} className="rounded-md ring-1 ring-white/15" />
        <p>
          <span className="font-semibold text-slate-200">Marco (sin S)</span>
        </p>
      </div>
    </footer>
  );
}
