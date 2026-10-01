import type { Metadata, Viewport } from "next";
import { Geist } from "next/font/google";

import BottomNav from "@/components/BottomNav";
import Footer from "@/components/Footer";
import Header from "@/components/Header";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://climapp-chile.vercel.app"),
  title: { default: "ClimApp · Pronóstico para Chile", template: "%s · ClimApp" },
  description:
    "Pronóstico del tiempo para las 346 comunas de Chile combinando modelos globales (GFS, ECMWF, ICON), con avisos marítimos y oleaje de la Armada de Chile.",
  applicationName: "ClimApp",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "ClimApp" },
  openGraph: { type: "website", locale: "es_CL", siteName: "ClimApp" },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es-CL" className={`${geistSans.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans selection:bg-climapp-teal selection:text-white">
        <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-climapp-card focus:px-4 focus:py-2">
          Saltar al contenido
        </a>
        <Header />
        <main id="contenido" className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">
          {children}
        </main>
        <Footer />
        <BottomNav />
      </body>
    </html>
  );
}
