import Link from "next/link";

export default function NotFound() {
  return (
    <div className="space-y-4 pt-12 text-center">
      <h1 className="text-2xl font-semibold">Página no encontrada</h1>
      <Link href="/" className="inline-block rounded-xl bg-sky-700 px-4 py-2 font-medium text-white hover:bg-sky-600">
        Volver al inicio
      </Link>
    </div>
  );
}
