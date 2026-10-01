import Search from "@/components/Search";

export default function ComunaNoEncontrada() {
  return (
    <div className="space-y-6 pt-8 text-center">
      <h1 className="text-2xl font-semibold">No encontramos esa comuna</h1>
      <p className="text-slate-300">Revisa el nombre o búscala de nuevo.</p>
      <div className="mx-auto max-w-xl text-left">
        <Search autoFocus />
      </div>
    </div>
  );
}
