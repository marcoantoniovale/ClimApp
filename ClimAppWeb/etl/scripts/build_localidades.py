"""Catálogo de localidades y barrios → data/catalog/localidades.csv (+ índice de búsqueda de la web).

Propuesta: docs/localidades-propuesta.md (etapa L1).

Fuentes:
- OpenStreetMap (ODbL, © colaboradores de OpenStreetMap), nodos `place` en Chile, consultados con
  Overpass. Copia en data/sources/osm_lugares.tsv (para regenerar sin red: --sin-red).
- data/catalog/localidades_extra.csv: correcciones a mano (lugares que faltan en OSM con otro tipo).
- Altura del terreno: API de elevación de Open-Meteo (modelo digital, ~90 m).

Reglas:
- Tipos: city, town, village, suburb, locality; y neighbourhood (barrio) si no es una villa, población,
  condominio, etc. (por el nombre) y está a ≥ 1 km de otra localidad ya incluida.
- Comuna: la que contiene el punto (polígonos de web/public/geo). Se omite el lugar que es la propia
  comuna (mismo nombre a < 5 km de la cabecera).
- Slug único dentro de la comuna.

Uso: python scripts/build_localidades.py [--sin-red]
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from climapp_etl import correccion, db, geo, open_meteo  # noqa: E402

SOURCES = ROOT / "data" / "sources"
CATALOG = ROOT / "data" / "catalog"
WEB_INDEX = ROOT.parent / "web" / "public" / "localidades.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
TIPOS = {"city": 0, "town": 1, "village": 2, "suburb": 3, "locality": 4, "neighbourhood": 5}
EXCLUIR_BARRIO = re.compile(
    r"^(villa|villas|poblacion|pobl\.|condominio|conjunto|comunidad|barrio|lote|loteo|parcelacion|parcela|"
    r"sector|campamento|toma|hacienda|fundo|block|edificio|residencial|jardines? del)\b")


def normalizar(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(s)).strip("-")


def descargar_osm() -> list[tuple[str, str, float, float]]:
    consulta = ('[out:csv(name,place,::lat,::lon;false;"\\t")][timeout:200];area["ISO3166-1"="CL"][admin_level=2]->.a;'
                '(node["place"~"^(' + "|".join(TIPOS) + ')$"]["name"](area.a););out;')
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": consulta}).encode(),
                                 headers={"User-Agent": "ClimApp-catalog/0.1 (+https://climapp-chile.vercel.app)"})
    texto = urllib.request.urlopen(req, timeout=300).read().decode("utf-8")
    (SOURCES / "osm_lugares.tsv").write_text(texto, encoding="utf-8")
    return leer_osm()


def leer_osm() -> list[tuple[str, str, float, float]]:
    out = []
    for linea in (SOURCES / "osm_lugares.tsv").read_text(encoding="utf-8").splitlines():
        partes = linea.split("\t")
        if len(partes) == 4 and partes[0] and partes[1] in TIPOS:
            out.append((partes[0].strip(), partes[1], float(partes[2]), float(partes[3])))
    return out


def main(sin_red: bool = False) -> None:
    lugares = leer_osm() if sin_red else descargar_osm()
    extra = list(csv.DictReader((CATALOG / "localidades_extra.csv").open(encoding="utf-8")))
    with db.connect() as conn:
        cabeceras = {r[0]: {"lat": r[1], "lon": r[2], "nombre": r[3]} for r in conn.execute(
            "select slug, lat, lon, nombre from locations where tipo = 'comuna'")}

    candidatos = [(TIPOS[t], n, t, la, lo) for n, t, la, lo in lugares]
    candidatos += [(-1, e["nombre"], e["tipo"], float(e["lat"]), float(e["lon"])) for e in extra]   # primero
    candidatos.sort(key=lambda c: c[0])
    elegidos, por_celda = [], defaultdict(list)
    for orden, nombre, tipo, lat, lon in candidatos:
        if tipo == "neighbourhood" and EXCLUIR_BARRIO.match(normalizar(nombre)):
            continue
        comuna = geo.comuna_de(lat, lon)
        if comuna not in cabeceras:
            continue
        cab = cabeceras[comuna]
        if normalizar(nombre) == normalizar(cab["nombre"]) and correccion.km(lat, lon, cab["lat"], cab["lon"]) < 5:
            continue   # es la propia comuna
        celda = por_celda[(round(lat, 1), round(lon, 1))]
        cerca = [x for x in celda if correccion.km(lat, lon, x["lat"], x["lon"]) < (1.0 if tipo == "neighbourhood" else 0.3)]
        if (tipo == "neighbourhood" and cerca) or any(normalizar(x["nombre"]) == normalizar(nombre) for x in cerca):
            continue
        item = {"nombre": nombre, "tipo": tipo, "comuna": comuna, "lat": round(lat, 5), "lon": round(lon, 5),
                "km_cabecera": round(correccion.km(lat, lon, cab["lat"], cab["lon"]), 1)}
        elegidos.append(item)
        celda.append(item)

    usados = defaultdict(set)
    for e in sorted(elegidos, key=lambda e: (e["comuna"], TIPOS.get(e["tipo"], 9), e["nombre"])):
        base = slugify(e["nombre"]) or "lugar"
        slug, i = base, 2
        while slug in usados[e["comuna"]]:
            slug, i = f"{base}-{i}", i + 1
        usados[e["comuna"]].add(slug)
        e["slug"] = slug

    # Altura: se reutiliza la del catálogo anterior y solo se piden a Open-Meteo los lugares nuevos.
    previas = {}
    if (CATALOG / "localidades.csv").exists():
        previas = {(r["lat"], r["lon"]): r["altura"] for r in csv.DictReader((CATALOG / "localidades.csv").open(encoding="utf-8"))
                   if r["altura"]}
    faltan = [i for i, e in enumerate(elegidos) if (f"{e['lat']}", f"{e['lon']}") not in previas]
    alturas = open_meteo.elevations([open_meteo.Point(i, elegidos[i]["lat"], elegidos[i]["lon"]) for i in faltan]) if faltan else {}
    for i, e in enumerate(elegidos):
        previa = previas.get((f"{e['lat']}", f"{e['lon']}"))
        e["altura"] = previa if previa is not None else (round(alturas[i]) if i in alturas else "")
    print(f"alturas: {len(elegidos) - len(faltan)} reutilizadas, {len(faltan)} nuevas")

    elegidos.sort(key=lambda e: (e["comuna"], e["slug"]))
    campos = ["comuna", "slug", "nombre", "tipo", "lat", "lon", "altura", "km_cabecera"]
    with (CATALOG / "localidades.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows({k: e[k] for k in campos} for e in elegidos)
    # Índice de búsqueda de la web (se carga solo al escribir): slug, nombre, comuna, coordenadas.
    WEB_INDEX.write_text(json.dumps([{"s": e["slug"], "n": e["nombre"], "c": e["comuna"], "la": round(e["lat"], 4),
                                      "lo": round(e["lon"], 4)} for e in elegidos],
                                    ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tipos = defaultdict(int)
    for e in elegidos:
        tipos[e["tipo"]] += 1
    print(f"{len(elegidos)} localidades {dict(tipos)} → {CATALOG / 'localidades.csv'} y {WEB_INDEX}")


if __name__ == "__main__":
    main(sin_red="--sin-red" in sys.argv)
