import type { NextRequest } from "next/server";

import { CACHE, json, notFound, serverError } from "@/lib/api";
import { getLugar, isValidSlug } from "@/lib/data";

/** GET /api/lugar/:comuna/:slug — pronóstico de una localidad o barrio (el de su comuna con su ajuste propio). */
export async function GET(_request: NextRequest, ctx: RouteContext<"/api/lugar/[comuna]/[slug]">) {
  const { comuna, slug } = await ctx.params;
  if (!isValidSlug(comuna) || !isValidSlug(slug)) return notFound("Lugar no válido");
  try {
    const lugar = await getLugar(comuna, slug, { revalidate: 60 });
    return lugar ? json(lugar, CACHE.corto) : notFound(`No hay pronóstico para "${comuna}/${slug}"`);
  } catch (error) {
    return serverError(error);
  }
}
