import { CACHE, json, serverError } from "@/lib/api";
import { getJson } from "@/lib/redis";

// Vigilancia (flujo .github/workflows/vigilancia.yml, cada hora): cada dato publicado por el ETL tiene su
// propio plazo. Si alguno se atrasa, responde 503 y el flujo falla (GitHub avisa por correo).
const PLAZOS_H: Record<string, number> = {
  meta: 8,        // pronóstico de comunas: se precalcula con cada corrida de los modelos y al cambiar el día
  algoritmo: 3,   // ajuste del momento (job residuos, cada hora)
  lluvia: 2,      // lluvia medida DMC (cada 15 min; cada hora si fallan las mediciones)
  avisos: 3,      // avisos de la Armada (cada hora)
};

/** GET /api/health — estado de cada dato publicado: cuándo se generó y si está al día. */
export async function GET() {
  try {
    const claves = Object.keys(PLAZOS_H);
    const datos = await getJson<{ generado?: string }[]>(claves);
    const ahora = Date.now();
    const componentes = Object.fromEntries(claves.map((clave, i) => {
      const generado = datos[i]?.generado ?? null;
      const horas = generado ? Math.round(((ahora - Date.parse(generado)) / 3_600_000) * 10) / 10 : null;
      return [clave, { generado, horas, plazo_h: PLAZOS_H[clave], ok: horas != null && horas <= PLAZOS_H[clave] }];
    }));
    const atrasados = claves.filter((c) => !componentes[c].ok);
    const estado = atrasados.length === 0 ? "ok" : "desactualizado";
    return json({ estado, atrasados, componentes }, CACHE.ninguno, estado === "ok" ? 200 : 503);
  } catch (error) {
    return serverError(error);
  }
}
