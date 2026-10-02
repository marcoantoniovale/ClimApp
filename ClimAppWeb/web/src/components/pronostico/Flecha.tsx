/** Flecha hacia donde va el viento u oleaje (la fuente informa desde dónde viene). */
export default function Flecha({ desde, size = 14 }: { desde: number | null | undefined; size?: number }) {
  if (desde == null) return null;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="inline-block shrink-0"
      style={{ transform: `rotate(${desde + 180}deg)` }}>
      <path d="M12 3v18M12 3l-6 6M12 3l6 6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
