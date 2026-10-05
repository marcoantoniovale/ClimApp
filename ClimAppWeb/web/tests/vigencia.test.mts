import assert from "node:assert/strict";
import { test } from "node:test";

import { desdeAhora } from "../src/lib/vigencia.ts";

type Pronostico = { horas: { hora: string; temperatura: number }[]; dias: { fecha: string }[] };

const hora = (dia: string, hh: string) => ({ hora: `2026-10-${dia}T${hh}:00-03:00`, temperatura: 10 }) as Pronostico["horas"][number];
const dia = (d: string) => ({ fecha: `2026-10-${d}` }) as Pronostico["dias"][number];

test("después de medianoche se quita el día anterior (JSON generado antes de las 00:00)", () => {
  const p = { horas: [hora("04", "22"), hora("04", "23"), hora("05", "00"), hora("05", "01")],
              dias: [dia("04"), dia("05"), dia("06")] } as unknown as Pronostico;
  const r = desdeAhora(p, new Date("2026-10-05T00:46:00-03:00"));
  assert.deepEqual(r.dias.map((d) => d.fecha), ["2026-10-05", "2026-10-06"]);
  assert.deepEqual(r.horas.map((h) => h.hora.slice(8, 13)), ["05T00", "05T01"]);
  assert.equal(r.horasPrevias.length, 2);
  // aplicarlo otra vez (en el navegador) no pierde las horas previas
  const otra = desdeAhora(r, new Date("2026-10-05T01:10:00-03:00"));
  assert.deepEqual(otra.horasPrevias.map((h) => h.hora.slice(8, 13)), ["04T22", "04T23", "05T00"]);
});
