import { CACHE, json, serverError } from "@/lib/api";
import { getAvisos } from "@/lib/data";

/** GET /api/warnings — todos los avisos vigentes de la Armada, con las ubicaciones que cubren. */
export async function GET() {
  try {
    return json((await getAvisos()) ?? { generado: null, avisos: [] }, CACHE.corto);
  } catch (error) {
    return serverError(error);
  }
}
