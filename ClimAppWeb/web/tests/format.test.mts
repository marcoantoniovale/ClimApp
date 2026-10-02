import assert from "node:assert/strict";
import { test } from "node:test";

import { grados, grados1 } from "../src/lib/format.ts";

test("temperatura actual con un decimal y coma", () => {
  assert.equal(grados1(14.8), "14,8°");
  assert.equal(grados1(15), "15,0°");
  assert.equal(grados1(-0.3), "-0,3°");
  assert.equal(grados1(null), "–");
  assert.equal(grados(14.8), "15°");
});
