// Lluvia medida en "Ahora" (lib/lluvia.ts). Ejecutar: npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import { estadoLluvia, lluviaCercana, mm, type LluviaEstacion } from "../src/lib/lluvia.ts";

// Valores reales del 5-oct a las 23:15: lluvia en Quintero y Quinta Normal (visor de precipitación DMC).
const QUINTERO: LluviaEstacion = { id: "dmc-320056", nombre: "Quintero, Climatológica", lat: -32.78417, lon: -71.52278,
  hasta: "2026-10-05T23:15-03:00", mm_1h: 0.1, mm_3h: 2.6, mm_6h: 5.2, mm_24h: 5.4, ultima: "2026-10-05T22:58-03:00" };
const QUINTA_NORMAL: LluviaEstacion = { id: "dmc-330020", nombre: "Quinta Normal", lat: -33.445, lon: -70.6828,
  hasta: "2026-10-05T23:15-03:00", mm_1h: 0.2, mm_3h: 3.0, ultima: null };
const PAYLOAD = { generado: "2026-10-05T23:59-03:00", estaciones: [QUINTA_NORMAL, QUINTERO] };
const LONCURA = [-32.7862, -71.5081] as const;
const t = (iso: string) => Date.parse(iso);

test("Loncura toma la estación de Quintero (1,4 km)", () => {
  const m = lluviaCercana(PAYLOAD, ...LONCURA);
  assert.equal(m?.id, "dmc-320056");
  assert.equal(m?.km, 1.4);
});

test("sin estación a menos de 15 km no hay lluvia medida", () => {
  assert.equal(lluviaCercana(PAYLOAD, -32.4, -71.4), null);      // Papudo
  assert.equal(lluviaCercana(null, ...LONCURA), null);
});

test("lluvia en la última hora: el cielo pasa a lluvia según la intensidad", () => {
  const m = lluviaCercana(PAYLOAD, ...LONCURA)!;
  const e = estadoLluvia(m, t("2026-10-05T23:40-03:00"));
  assert.deepEqual([e?.lloviendo, e?.codigo], [true, 61]);
  assert.equal(estadoLluvia({ ...m, mm_1h: 1.2 }, t("2026-10-05T23:40-03:00"))?.codigo, 63);
  assert.equal(estadoLluvia({ ...m, mm_1h: 6 }, t("2026-10-05T23:40-03:00"))?.codigo, 65);
});

test("sin lluvia en la última hora pero sí en 3 h: se informa sin cambiar el cielo", () => {
  const e = estadoLluvia({ ...lluviaCercana(PAYLOAD, ...LONCURA)!, mm_1h: 0 }, t("2026-10-05T23:40-03:00"));
  assert.deepEqual([e?.lloviendo, e?.codigo], [false, null]);
});

test("medición vieja o sin lluvia en 3 h: nada", () => {
  const m = lluviaCercana(PAYLOAD, ...LONCURA)!;
  assert.equal(estadoLluvia(m, t("2026-10-06T01:30-03:00")), null);   // 2 h 15 min después
  assert.equal(estadoLluvia({ ...m, mm_1h: 0, mm_3h: 0 }, t("2026-10-05T23:40-03:00")), null);
});

test("milímetros con coma decimal", () => {
  assert.equal(mm(2.6), "2,6\u00a0mm");
  assert.equal(mm(0), "0\u00a0mm");
});
