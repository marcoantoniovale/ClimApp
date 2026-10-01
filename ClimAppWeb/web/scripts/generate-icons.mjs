// Genera los íconos de la app desde public/brand/climapp_icon.svg (fuente única; ver
// docs/frontend-template-analisis.md, ajustes 11 y 12).
//
//   public/icons/icon-192.png, icon-512.png   ícono con esquinas redondeadas ("any")
//   public/icons/icon-maskable-512.png        a sangre completa, logo en la zona segura (80 %)
//   src/app/apple-icon.png                     180×180 a sangre completa (iOS redondea solo)
//   src/app/icon.svg                           favicon vectorial
//
// Uso: npm run icons

import { mkdir, readFile, writeFile } from "node:fs/promises";
import sharp from "sharp";

const source = await readFile("public/brand/climapp_icon.svg", "utf8");
const background = source.match(/<rect[^>]*fill="(#[0-9A-Fa-f]{6})"/)[1];
const artwork = source.replace(/<svg[^>]*>/, "").replace("</svg>", "").replace(/<rect[^>]*\/>/, "");

const fullBleed = (scale) => `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="${background}"/>
  <g transform="translate(256 256) scale(${scale}) translate(-256 -256)">${artwork}</g>
</svg>`;

const png = (svg, size) => sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();

await mkdir("public/icons", { recursive: true });
await writeFile("public/icons/icon-192.png", await png(source, 192));
await writeFile("public/icons/icon-512.png", await png(source, 512));
await writeFile("public/icons/icon-maskable-512.png", await png(fullBleed(0.8), 512));
await writeFile("src/app/apple-icon.png", await png(fullBleed(0.9), 180));
await writeFile("src/app/icon.svg", source);
console.log("Íconos generados.");
