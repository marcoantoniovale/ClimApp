import type { NextRequest } from "next/server";

import { CACHE, json, notFound, serverError } from "@/lib/api";
import { getPronostico, isValidSlug } from "@/lib/data";

/** GET /api/forecast/:slug — pronóstico precalculado de la ubicación con sus avisos vigentes. */
export async function GET(_request: NextRequest, ctx: RouteContext<"/api/forecast/[slug]">) {
  const { slug } = await ctx.params;
  if (!isValidSlug(slug)) return notFound("Ubicación no válida");
  try {
    const pronostico = await getPronostico(slug, { revalidate: 60 });
    return pronostico ? json(pronostico, CACHE.corto) : notFound(`No hay pronóstico para "${slug}"`);
  } catch (error) {
    return serverError(error);
  }
}
