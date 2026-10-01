export default function Footer() {
  return (
    <footer className="mx-auto w-full max-w-4xl px-4 pb-28 pt-10 text-xs leading-relaxed text-slate-400 md:pb-10">
      <p>
        Pronóstico provisional: promedio de los modelos GFS, ECMWF e ICON. Datos meteorológicos de{" "}
        <a href="https://open-meteo.com" className="underline hover:text-white" rel="noopener">Open-Meteo</a>{" "}
        (<a href="https://creativecommons.org/licenses/by/4.0/deed.es" className="underline hover:text-white" rel="noopener">CC BY 4.0</a>);
        observaciones y avisos del{" "}
        <a href="https://meteoarmada.directemar.cl" className="underline hover:text-white" rel="noopener">
          Servicio Meteorológico de la Armada de Chile
        </a>
        . Ante una emergencia, siga siempre los avisos oficiales.
      </p>
    </footer>
  );
}
