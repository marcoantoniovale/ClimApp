import Image from "next/image";
import Link from "next/link";

export default function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-climapp-line/60 bg-climapp-bg/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 rounded-lg focus-visible:outline-2 focus-visible:outline-climapp-teal">
          <Image src="/brand/climapp_icon.svg" alt="" width={28} height={28} priority />
          <span className="text-lg font-semibold tracking-tight">ClimApp</span>
        </Link>
        <nav aria-label="Principal" className="hidden gap-1 text-sm font-medium text-slate-300 md:flex">
          <Link href="/" className="rounded-lg px-3 py-2 hover:bg-climapp-card hover:text-white">Inicio</Link>
          <Link href="/avisos" className="rounded-lg px-3 py-2 hover:bg-climapp-card hover:text-white">Avisos marítimos</Link>
        </nav>
      </div>
    </header>
  );
}
