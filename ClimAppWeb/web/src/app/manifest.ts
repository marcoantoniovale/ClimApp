import type { MetadataRoute } from "next";

/** PWA instalable. Íconos generados con `npm run icons` desde public/brand/climapp_icon.svg. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ClimApp · Pronóstico para Chile",
    short_name: "ClimApp",
    description: "Pronóstico por comuna, avisos marítimos y oleaje para Chile.",
    lang: "es-CL",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0f172a",
    theme_color: "#0f172a",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
