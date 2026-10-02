// Salida y puesta del sol contra los valores de Open-Meteo (2-oct-2026, hora de Chile).
import assert from "node:assert/strict";
import { test } from "node:test";

import { salidaPuesta } from "../src/lib/sol.ts";

const hora = (d: Date) =>
  new Intl.DateTimeFormat("es-CL", { timeZone: "America/Santiago", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
const minutos = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3));
const dia = new Date("2026-10-02T12:00:00-03:00");

const CASOS: [string, number, number, string, string][] = [
  ["Santiago", -33.45, -70.67, "07:18", "19:45"],
  ["Punta Arenas", -53.16, -70.91, "07:07", "19:59"],
  ["Arica", -18.48, -70.31, "07:21", "19:38"],
];

for (const [nombre, lat, lon, salida, puesta] of CASOS) {
  test(`${nombre}: salida ${salida}, puesta ${puesta} (±2 min)`, () => {
    const s = salidaPuesta(dia, lat, lon)!;
    assert.ok(Math.abs(minutos(hora(s.salida)) - minutos(salida)) <= 2, `salida ${hora(s.salida)}`);
    assert.ok(Math.abs(minutos(hora(s.puesta)) - minutos(puesta)) <= 2, `puesta ${hora(s.puesta)}`);
  });
}

test("Antártica en invierno: el sol no sale", () => {
  assert.equal(salidaPuesta(new Date("2026-06-21T12:00:00-04:00"), -75, -71.5), null);
});
