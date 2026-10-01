import { CACHE, json, serverError } from "@/lib/api";
import { getMeta } from "@/lib/data";

const MAX_AGE_HOURS = 8; // el pronóstico se precalcula cada 6 h

/** GET /api/health — estado de los datos: cuándo se generaron y si están al día. */
export async function GET() {
  try {
    const meta = await getMeta();
    if (!meta) return json({ estado: "sin_datos" }, CACHE.ninguno, 503);
    const horas = (Date.now() - new Date(meta.generado).getTime()) / 3_600_000;
    const estado = horas <= MAX_AGE_HOURS ? "ok" : "desactualizado";
    return json({ estado, ...meta, horas: Math.round(horas * 10) / 10 }, CACHE.ninguno, estado === "ok" ? 200 : 503);
  } catch (error) {
    return serverError(error);
  }
}
