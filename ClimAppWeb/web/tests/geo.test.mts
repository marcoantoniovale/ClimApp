// Pruebas de "Usar mi ubicación" con el catálogo y los polígonos del repositorio.
// Ejecutar: npm test
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { comunaEnPosicion, enGeometria } from "../src/lib/geo.ts";

const ROOT = new URL("../", import.meta.url);
const csv = await readFile(new URL("../etl/data/catalog/comunas.csv", ROOT), "utf8");
const slugify = (s: string) =>
  s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const [header, ...lines] = csv.trim().split(/\r?\n/);
const cols = header.split(",");
const indice = lines.map((line) => {
  const row = Object.fromEntries(line.split(",").map((v, i) => [cols[i], v]));
  return { slug: slugify(row.nombre), lat: Number(row.lat), lon: Number(row.lon) };
});
const geo = async (slug: string) => JSON.parse(await readFile(new URL(`public/geo/${slug}.json`, ROOT), "utf8"));

const CASOS: [string, number, number, string][] = [
  ["Plaza Sotomayor, Valparaíso", -33.0389, -71.629, "valparaiso"],
  ["Reloj de Flores, Viña del Mar", -33.0215, -71.5537, "vina-del-mar"],
  ["Costanera Center, Providencia (cabecera más cercana: Vitacura)", -33.4172, -70.6064, "providencia"],
  ["Estadio Nacional, Ñuñoa", -33.4645, -70.6107, "nunoa"],
  ["Aeropuerto, Pudahuel", -33.393, -70.7858, "pudahuel"],
  ["Hanga Roa, Rapa Nui", -27.15, -109.433, "isla-de-pascua"],
];

for (const [nombre, lat, lon, esperado] of CASOS) {
  test(nombre, async () => {
    const r = await comunaEnPosicion(indice, lat, lon, geo);
    assert.equal(r?.lugar.slug, esperado);
    assert.equal(r?.exacta, true);
  });
}

test("en el mar frente a la costa usa la cabecera más cercana", async () => {
  const r = await comunaEnPosicion(indice, -33.02, -71.66, geo);
  assert.deepEqual([r?.lugar.slug, r?.exacta], ["valparaiso", false]);
});

test("fuera de Chile queda lejos de toda cabecera", async () => {
  const r = await comunaEnPosicion(indice, -34.6037, -58.3816, geo);
  assert.equal(r?.exacta, false);
  assert.ok(r!.km > 80);
});

test("polígono con hueco", () => {
  const cuadrado = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]] as [number, number][];
  const hueco = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]] as [number, number][];
  const g = { type: "Polygon" as const, coordinates: [cuadrado, hueco] };
  assert.equal(enGeometria(2, 2, g), true);
  assert.equal(enGeometria(5, 5, g), false);
  assert.equal(enGeometria(11, 5, g), false);
});
