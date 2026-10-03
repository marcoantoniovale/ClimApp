import assert from "node:assert/strict";
import { test } from "node:test";

import { desfase, diasDe, horasDe, type Lugar } from "../src/lib/lugar.ts";

const h = (hhmm: string, dia = "03") => `2026-10-${dia}T${hhmm}-03:00`;
const BASE: Lugar = { nombre: "Loncura", tipo: "suburb", lat: -32.786, lon: -71.508, altura: 32,
                      franjas: { "0": 0.5, "1": 0, "2": -0.4, "3": 0.2 }, por_altura: -0.1 };

test("desfase = diferencia de sesgo de la franja + altura", () => {
  assert.ok(Math.abs(desfase(BASE, h("03:00")) - 0.4) < 1e-9);    // franja 0: 0,5 − 0,1
  assert.ok(Math.abs(desfase(BASE, h("15:00")) + 0.5) < 1e-9);    // franja 2: −0,4 − 0,1
});

test("con perfil propio se usa la hora local, no la altura", () => {
  const perfil = Array.from({ length: 24 }, (_, i) => (i === 14 ? -2 : 0));
  const lejana = { ...BASE, perfil, franjas: {} };
  assert.equal(desfase(lejana, h("14:00")), -2);
  assert.equal(desfase(lejana, h("13:00")), 0);
});

test("horas y máximas/mínimas se mueven con el desfase de su hora", () => {
  const horas = [
    { hora: h("05:00"), temperatura: 9.0, sensacion_termica: 8.0 },
    { hora: h("15:00"), temperatura: 20.0, sensacion_termica: 19.5 },
  ];
  const [madrugada, tarde] = horasDe(horas, BASE);
  assert.equal(madrugada.temperatura, 9.4);
  assert.equal(tarde.temperatura, 19.5);
  assert.equal(tarde.sensacion_termica, 19);
  const [dia] = diasDe([{ fecha: "2026-10-03", temperatura_max: 20, temperatura_min: 9, rango_max: [19, 21], rango_min: null }],
                       horas, BASE);
  assert.equal(dia.temperatura_max, 19.5);
  assert.equal(dia.temperatura_min, 9.4);
  assert.deepEqual(dia.rango_max, [18.5, 20.5]);
});
