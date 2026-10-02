import assert from "node:assert/strict";
import { test } from "node:test";

import { estimacionActual, interpolar } from "../src/lib/ahora.ts";

const h = (hhmm: string) => `2026-10-01T${hhmm}-03:00`;
const t = (hhmm: string) => Date.parse(h(hhmm));
const HORAS = [
  { hora: h("21:00"), temperatura: 14.9, sensacion_termica: 14.0 },
  { hora: h("22:00"), temperatura: 14.5, sensacion_termica: 13.6 },
  { hora: h("23:00"), temperatura: 14.0, sensacion_termica: 13.0 },
];

test("la curva baja entre horas en vez de quedarse fija", () => {
  assert.equal(interpolar(HORAS, "temperatura", t("21:00")), 14.9);
  assert.ok(Math.abs(interpolar(HORAS, "temperatura", t("21:30"))! - 14.7) < 1e-9);
  assert.equal(interpolar(HORAS, "temperatura", t("22:00")), 14.5);
  assert.ok(Math.abs(interpolar(HORAS, "temperatura", t("22:30"))! - 14.25) < 1e-9);
  assert.equal(interpolar(HORAS, "temperatura", t("23:30")), 14.0);   // después del último dato
});

test("sin medición: la estimación es la curva", () => {
  const e = estimacionActual(HORAS, null, t("21:45"))!;
  assert.equal(e.temperatura, 14.6);
  assert.equal(e.ajustada, false);
});

test("parte de la medición y converge a la curva", () => {
  const medicion = { hora: h("21:12"), temperatura: 15.3 };      // 0,48° sobre la curva a las 21:12
  const recien = estimacionActual(HORAS, medicion, t("21:12"))!;
  assert.equal(recien.temperatura, 15.3);
  assert.equal(recien.ajustada, true);
  const a22 = estimacionActual(HORAS, medicion, t("22:00"))!;
  assert.ok(a22.temperatura > 14.5 && a22.temperatura < 15.3);   // baja, sin quedarse en 15,3
  const tarde = estimacionActual(HORAS, medicion, t("23:00"))!;
  assert.ok(tarde.temperatura < a22.temperatura);
});

test("una medición antigua (> 3 h) no se usa", () => {
  const e = estimacionActual(HORAS, { hora: h("17:00"), temperatura: 20 }, t("21:30"))!;
  assert.equal(e.temperatura, 14.7);
  assert.equal(e.ajustada, false);
});
