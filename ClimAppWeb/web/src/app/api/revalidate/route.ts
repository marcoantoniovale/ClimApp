import { timingSafeEqual } from "node:crypto";

import { revalidatePath, revalidateTag } from "next/cache";

import { CACHE, json } from "@/lib/api";
import { CACHE_TAG, getJson } from "@/lib/redis";

/**
 * POST /api/revalidate — la llama el ETL al terminar cada ingesta para que la web muestre los datos
 * nuevos al instante. Autenticación sin variables extra: el ETL deja una clave de un solo uso en Redis
 * (climapp:v1:revalidar, vence en 5 min) y la envía en el cuerpo; aquí se compara con la de Redis.
 */
export async function POST(request: Request) {
  let token = "";
  try {
    token = String((await request.json())?.token ?? "");
  } catch {
    return json({ error: "Cuerpo inválido" }, CACHE.ninguno, 400);
  }
  const [guardado] = await getJson<[{ token: string }]>(["revalidar"]);
  const esperado = guardado?.token ?? "";
  const valido =
    token.length > 0 && token.length === esperado.length && timingSafeEqual(Buffer.from(token), Buffer.from(esperado));
  if (!valido) return json({ error: "No autorizado" }, CACHE.ninguno, 401);

  revalidateTag(CACHE_TAG, { expire: 0 }); // datos de Redis: la próxima visita los lee de nuevo
  revalidatePath("/", "layout");           // todas las páginas (inicio, comunas, pasos, avisos)
  return json({ ok: true, renovado: new Date().toISOString() }, CACHE.ninguno);
}
