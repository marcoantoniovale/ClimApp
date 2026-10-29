import assert from "node:assert/strict";
import { test } from "node:test";
import { gzipSync } from "node:zlib";

import { decodificar } from "../src/lib/redis.ts";

test("lee JSON plano y comprimido (formato del ETL)", () => {
  const dato = { slug: "quintero", horas: [{ temperatura: 14.8, cielo: "Neblina" }] };
  assert.deepEqual(decodificar(JSON.stringify(dato)), dato);
  const gz = "gz:" + gzipSync(Buffer.from(JSON.stringify(dato), "utf8")).toString("base64");
  assert.deepEqual(decodificar(gz), dato);
});
