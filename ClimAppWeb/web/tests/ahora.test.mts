import assert from "node:assert/strict";
import { test } from "node:test";

import { ajustarDias, ajustarHoras, estimacionActual, interpolar } from "../src/lib/ahora.ts";

const h = (hhmm: string, dia = "01") => `2026-10-${dia}T${hhmm}-03:00`;
const t = (hhmm: string, dia = "01") => Date.parse(h(hhmm, dia));
const HORAS = [
  { hora: h("21:00"), temperatura: 14.9, sensacion_termica: 14.0 },
  { hora: h("22:00"), temperatura: 14.5, sensacion_termica: 13.6 },
  { hora: h("23:00"), temperatura: 14.0, sensacion_termica: 13.0 },
];
const fecha = (iso: string) => iso.slice(0, 10);

test("la curva baja entre horas en vez de quedarse fija", () => {
  assert.equal(interpolar(HORAS, "temperatura", t("21:00")), 14.9);
  assert.ok(Math.abs(interpolar(HORAS, "temperatura", t("21:30"))! - 14.7) < 1e-9);
  assert.equal(interpolar(HORAS, "temperatura", t("22:00")), 14.5);
  assert.ok(Math.abs(interpolar(HORAS, "temperatura", t("22:30"))! - 14.25) < 1e-9);
  assert.equal(interpolar(HORAS, "temperatura", t("23:30")), 14.0);   // después del último dato
});

test("sin ancla: la estimación es la curva", () => {
  const e = estimacionActual(HORAS, null, t("21:45"))!;
  assert.equal(e.temperatura, 14.6);
  assert.equal(e.ajustada, false);
});

test("parte de la anomalía medida y vuelve a la curva con τ", () => {
  const ancla = { anomalia: -2, hora: h("21:00"), tau_h: 4 };          // 2° bajo la curva a las 21:00
  const a21 = estimacionActual(HORAS, ancla, t("21:00"))!;
  assert.equal(a21.temperatura, 12.9);
  assert.equal(a21.ajustada, true);
  const a23 = estimacionActual(HORAS, ancla, t("23:00"))!;            // 14,0 − 2·e^(−2/4) ≈ 12,8
  assert.equal(a23.temperatura, 12.8);
  const lento = estimacionActual(HORAS, { ...ancla, tau_h: 20 }, t("23:00"))!;
  assert.ok(lento.temperatura < a23.temperatura);                    // τ mayor: el ajuste dura más
});

test("un ancla de más de 6 h no se usa", () => {
  const e = estimacionActual(HORAS, { anomalia: 3, hora: h("15:00"), tau_h: 4 }, t("21:30"))!;
  assert.equal(e.temperatura, 14.7);
  assert.equal(e.ajustada, false);
});

test("las horas siguientes también se ajustan", () => {
  const ancla = { anomalia: -2, hora: h("21:00"), tau_h: 4 };
  const [h22, h23] = ajustarHoras(HORAS.slice(1), ancla, t("21:10"));
  assert.equal(h22.temperatura, 12.9);                               // 14,5 − 2·e^(−1/4) ≈ 12,94
  assert.equal(h23.temperatura, 12.8);
  assert.equal(ajustarHoras(HORAS, null, t("21:10")), HORAS);
  assert.equal(ajustarHoras(HORAS, ancla, t("04:00", "02")), HORAS);  // ancla vencida
});

test("máximas y mínimas siguen al ajuste si su hora aún no pasa", () => {
  const horas = [
    { hora: h("06:00", "02"), temperatura: 8.0 },
    { hora: h("15:00", "02"), temperatura: 20.0 },
  ];
  const dias = [{ fecha: "2026-10-02", temperatura_max: 20, temperatura_min: 8 }];
  const ancla = { anomalia: -3, hora: h("23:00"), tau_h: 4 };
  const [d] = ajustarDias(dias, horas, ancla, t("23:00"), fecha);
  assert.equal(d.temperatura_min, 7.5);                              // 06:00 → 7 h después: −3·e^(−7/4) ≈ −0,52
  assert.equal(d.temperatura_max, 19.9);                             // 16 h después: −3·e^(−4) ≈ −0,05
  assert.equal(ajustarDias(dias, horas, null, t("23:00"), fecha), dias);
});
