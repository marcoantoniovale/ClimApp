import assert from "node:assert/strict";
import { test } from "node:test";

import { textoProximaLluvia } from "../src/lib/proximaLluvia.ts";

const h = (dia: string, hhmm: string) => `2026-10-${dia}T${hhmm}:00-03:00`;
const t = (dia: string, hhmm: string) => Date.parse(h(dia, hhmm));

test("lluvia de consenso con rango entre modelos", () => {
  const p = { inicio: h("06", "19:00"), fin: h("07", "02:00"), desde: h("06", "17:00"), hasta: h("06", "22:00"),
              modelos: 5, modelos_con_lluvia: 4 };
  assert.equal(textoProximaLluvia(p, t("06", "12:10")),
    "Lluvia probable desde las 19:00 · los modelos la empiezan entre las 17:00 y las 22:00 (4 de 5 modelos)");
  assert.equal(textoProximaLluvia(p, t("06", "20:30")), "Lluvia hasta cerca de las 02:00 de mañana");
  assert.equal(textoProximaLluvia(p, t("07", "03:00")), null);   // ya pasó
});

test("día siguiente y rango estrecho", () => {
  const p = { inicio: h("08", "15:00"), fin: h("08", "20:00"), desde: h("08", "14:00"), hasta: h("08", "15:00"),
              modelos: 5, modelos_con_lluvia: 5 };
  assert.equal(textoProximaLluvia(p, t("06", "22:00")), "Lluvia probable desde las 15:00 del jueves (5 de 5 modelos)");
  assert.equal(textoProximaLluvia(p, t("07", "22:00")), "Lluvia probable desde las 15:00 de mañana (5 de 5 modelos)");
});

test("solo algunos modelos: posible lluvia", () => {
  const p = { desde: h("06", "16:00"), hasta: h("06", "18:00"), modelos: 5, modelos_con_lluvia: 2 };
  assert.equal(textoProximaLluvia(p, t("06", "12:00")), "Posible lluvia desde las 16:00 (solo 2 de 5 modelos)");
  assert.equal(textoProximaLluvia(p, t("06", "19:00")), null);
  assert.equal(textoProximaLluvia(null, t("06", "12:00")), null);
});
