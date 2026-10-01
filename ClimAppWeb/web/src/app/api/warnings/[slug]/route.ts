import type { NextRequest } from "next/server";

import { CACHE, json, notFound, serverError } from "@/lib/api";
import { getAvisosDe, isValidSlug } from "@/lib/data";

/** GET /api/warnings/:slug — avisos vigentes que cubren la ubicación. */
export async function GET(_request: NextRequest, ctx: RouteContext<"/api/warnings/[slug]">) {
  const { slug } = await ctx.params;
  if (!isValidSlug(slug)) return notFound("Ubicación no válida");
  try {
    return json(await getAvisosDe(slug), CACHE.corto);
  } catch (error) {
    return serverError(error);
  }
}
