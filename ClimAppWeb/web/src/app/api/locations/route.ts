import { CACHE, json, serverError } from "@/lib/api";
import { getIndice } from "@/lib/data";

/** GET /api/locations — catálogo de ubicaciones para el buscador (slug, nombre, alias, región). */
export async function GET() {
  try {
    return json((await getIndice()) ?? [], CACHE.largo);
  } catch (error) {
    return serverError(error);
  }
}
