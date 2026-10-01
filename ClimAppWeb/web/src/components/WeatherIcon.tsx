// Íconos del estado del cielo en el estilo del logo (figuras planas: sol naranja, nube turquesa).
import type { ReactNode } from "react";

import { cielo } from "@/lib/format";

const SUN = "var(--color-climapp-sun)";
const CLOUD = "var(--color-climapp-teal)";
const GREY = "#94a3b8";
const DROP = "#38bdf8";

function Cloud({ color = CLOUD, y = 0 }: { color?: string; y?: number }) {
  return (
    <g transform={`translate(0 ${y})`} fill={color}>
      <circle cx="22" cy="38" r="10" />
      <circle cx="34" cy="32" r="13" />
      <rect x="22" y="32" width="22" height="16" rx="2" />
      <circle cx="44" cy="40" r="8" />
    </g>
  );
}

export default function WeatherIcon({
  code,
  night = false,
  size = 40,
  className,
}: {
  code: number | null | undefined;
  night?: boolean;
  size?: number;
  className?: string;
}) {
  const { tipo, texto } = cielo(code);
  const sky = night ? (
    <path d="M44 10a14 14 0 1 0 12 20 11 11 0 0 1-12-20z" fill="#e2e8f0" />
  ) : (
    <circle cx="42" cy="20" r="12" fill={SUN} />
  );

  let content: ReactNode;
  switch (tipo) {
    case "despejado":
      content = night ? (
        <path d="M38 12a18 18 0 1 0 16 26 14 14 0 0 1-16-26z" fill="#e2e8f0" />
      ) : (
        <circle cx="32" cy="32" r="16" fill={SUN} />
      );
      break;
    case "parcial":
      content = (<>{sky}<Cloud /></>);
      break;
    case "nublado":
      content = (<><Cloud color={GREY} y={-6} /><Cloud y={2} /></>);
      break;
    case "niebla":
      content = (
        <g stroke={GREY} strokeWidth="4" strokeLinecap="round">
          <line x1="12" y1="24" x2="52" y2="24" />
          <line x1="8" y1="34" x2="48" y2="34" />
          <line x1="16" y1="44" x2="56" y2="44" />
        </g>
      );
      break;
    case "llovizna":
    case "lluvia":
      content = (
        <>
          <Cloud y={-8} />
          <g stroke={DROP} strokeWidth="3" strokeLinecap="round">
            <line x1="24" y1="48" x2="21" y2="56" />
            {tipo === "lluvia" && <line x1="33" y1="48" x2="30" y2="58" />}
            <line x1="42" y1="48" x2="39" y2="56" />
          </g>
        </>
      );
      break;
    case "nieve":
      content = (
        <>
          <Cloud color={GREY} y={-8} />
          <g fill="#f8fafc">
            <circle cx="22" cy="52" r="3" />
            <circle cx="33" cy="56" r="3" />
            <circle cx="44" cy="52" r="3" />
          </g>
        </>
      );
      break;
    case "tormenta":
      content = (
        <>
          <Cloud color={GREY} y={-8} />
          <path d="M34 42l-8 12h7l-3 9 10-14h-7l3-7z" fill="var(--color-climapp-warn)" />
        </>
      );
      break;
  }

  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={texto} className={className}>
      <title>{texto}</title>
      {content}
    </svg>
  );
}
