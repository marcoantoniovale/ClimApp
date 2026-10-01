"""Genera el catálogo geográfico de ClimApp (comunas y estaciones Armada).

Fuentes:
- Lista oficial de 346 comunas con código CUT (SUBDERE), copiada del paquete
  chilemapas (Apache-2.0) en data/sources/codigos_territoriales_subdere.csv.
- Wikidata: nombre con tildes y coordenadas por código CUT (propiedad P6929).
- Open-Meteo Geocoding: respaldo para comunas sin CUT o sin coordenadas en Wikidata.
- API del mapa de estaciones de la Armada (serviciosonline.directemar.cl).

Salidas (data/catalog/):
- comunas.csv: cut, nombre, alias, provincia, region_id, region, lat, lon, fuente_coord
- estaciones_armada.csv: id, red, nombre, lat, lon, coord_valida, comuna_cut, comuna, distancia_km

Las respuestas de Wikidata, Open-Meteo y la Armada se guardan en data/sources/ para que el
catálogo se pueda regenerar sin red. Con --refresh se vuelven a descargar.

Uso: python scripts/build_catalog.py [--refresh]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
CATALOG = ROOT / "data" / "catalog"

USER_AGENT = "ClimApp-catalog/0.1"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARMADA_API = "https://serviciosonline.directemar.cl/meteomapa/api/meteo"

# Chile continental + insular (Rapa Nui, Juan Fernández) + Territorio Chileno Antártico (53°O–90°O).
LAT_RANGE = (-90.0, -17.0)
LON_RANGE = (-110.0, -53.0)

# Correcciones manuales a coordenadas de las fuentes (revisadas el 2026-10-01).
COMUNA_OVERRIDES = {
    # Wikidata ubica la comuna Antártica en el centro del territorio antártico (-75, -71.5);
    # para pronóstico se usa su cabecera, Villa Las Estrellas (isla Rey Jorge).
    "12202": {"lat": -62.2, "lon": -58.96},
}
STATION_OVERRIDES = {
    # La API publica la longitud sin punto decimal (-7029193.0). Valor tomado de la
    # capitanía de puerto TIMBALES, en el mismo lugar.
    "99545": {"lat": -54.86759, "lon": -70.29193},
}

WIKIDATA_QUERY = """
SELECT ?cut ?label ?coord WHERE {
  ?item wdt:P6929 ?cut ; wdt:P625 ?coord .
  ?item rdfs:label ?label . FILTER(LANG(?label) = "es")
}
"""


def http_get(url: str, params: dict | None = None, accept: str = "application/json") -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


REFRESH = False


def cached_json(filename: str, fetch):
    """Lee data/sources/<filename> o, si no existe o se pidió --refresh, lo descarga y guarda."""
    path = SOURCES / filename
    if path.exists() and not REFRESH:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def normalize(text: str) -> str:
    """Minúsculas sin tildes ni signos, para comparar nombres."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse_wkt_point(wkt: str) -> tuple[float, float]:
    lon, lat = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", wkt).groups()
    return float(lat), float(lon)


def in_chile(lat: float, lon: float) -> bool:
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def load_official_comunas() -> list[dict]:
    with open(SOURCES / "codigos_territoriales_subdere.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_wikidata() -> dict[str, dict]:
    bindings = cached_json("wikidata_cut.json", lambda: json.loads(http_get(
        WIKIDATA_SPARQL, {"query": WIKIDATA_QUERY, "format": "json"},
        accept="application/sparql-results+json"))["results"]["bindings"])
    result: dict[str, dict] = {}
    for row in bindings:
        digits = re.sub(r"\D", "", row["cut"]["value"])
        if not digits:
            continue
        cut = digits.zfill(5)
        lat, lon = parse_wkt_point(row["coord"]["value"])
        if cut in result or not in_chile(lat, lon):
            continue
        label = re.sub(r"^comuna de ", "", row["label"]["value"], flags=re.IGNORECASE)
        result[cut] = {"nombre": label, "lat": lat, "lon": lon}
    return result


def geocode(name: str, region: str) -> dict | None:
    """Busca la comuna en Open-Meteo Geocoding y elige el resultado de la región correcta."""
    candidates = cached_json(f"geocoding_{normalize(name).replace(' ', '_')}.json", lambda: json.loads(
        http_get(GEOCODING_URL, {"name": name, "count": 20, "language": "es",
                                 "countryCode": "CL", "format": "json"})).get("results") or [])
    region_key = normalize(region)
    name_key = normalize(name)

    def score(c: dict) -> tuple:
        same_region = any(w in normalize(c.get("admin1", "")) for w in region_key.split() if len(w) > 3)
        same_name = normalize(c["name"]) == name_key
        is_admin3 = c.get("feature_code") == "ADM3"
        return (same_region, same_name, is_admin3, c.get("population") or 0)

    candidates = [c for c in candidates if score(c)[0] and score(c)[1]]
    if not candidates:
        return None
    best = max(candidates, key=score)
    return {"nombre": best["name"], "lat": best["latitude"], "lon": best["longitude"]}


def build_comunas() -> list[dict]:
    official = load_official_comunas()
    wikidata = fetch_wikidata()
    rows = []
    for c in official:
        cut = c["commune_id"].zfill(5)
        hit, source = wikidata.get(cut), "wikidata"
        if hit is None:
            hit, source = geocode(c["commune_name"], c["region_name"]), "open-meteo-geocoding"
            time.sleep(0.2)
        if cut in COMUNA_OVERRIDES:
            hit, source = {**(hit or {"nombre": c["commune_name"]}), **COMUNA_OVERRIDES[cut]}, "manual"
        nombre = hit["nombre"] if hit else c["commune_name"]
        rows.append({
            "cut": cut,
            "nombre": nombre,
            # Nombre de la lista SUBDERE cuando difiere (p. ej. "Coihaique"); se usa en la búsqueda.
            "alias": c["commune_name"] if normalize(c["commune_name"]) != normalize(nombre) else "",
            "provincia": c["province_name"],
            "region_id": c["region_id"],
            "region": c["region_name"],
            "lat": round(hit["lat"], 5) if hit else "",
            "lon": round(hit["lon"], 5) if hit else "",
            "fuente_coord": source if hit else "SIN_COORDENADAS",
        })
    return rows


def build_estaciones(comunas: list[dict]) -> list[dict]:
    """Estaciones de las dos redes que expone el mapa de la Armada, con su comuna más cercana."""
    automaticas = cached_json("armada_mapa.json", lambda: json.loads(http_get(f"{ARMADA_API}/mapa")))
    capitanias = cached_json("armada_observaciones_directemar.json", lambda: json.loads(
        http_get(f"{ARMADA_API}/observaciones/directemar")))

    stations = [{"id": str(s["CDuidestmeteo"]), "red": "ema", "nombre": s["NMestmeteo"],
                 "lat": s["NRLatitud"], "lon": s["NRLongitud"]} for s in automaticas]
    stations += [{"id": s["codigo"], "red": "capitania", "nombre": s["nombre"],
                  "lat": s["latitud"], "lon": s["longitud"]} for s in capitanias]

    with_coords = [c for c in comunas if c["lat"] != ""]
    for s in stations:
        s.update(STATION_OVERRIDES.get(s["id"], {}))
        s["coord_valida"] = in_chile(s["lat"], s["lon"])
        if not s["coord_valida"]:
            s.update(comuna_cut="", comuna="", distancia_km="")
            continue
        nearest = min(with_coords, key=lambda c: haversine_km(s["lat"], s["lon"], c["lat"], c["lon"]))
        s["lat"], s["lon"] = round(s["lat"], 5), round(s["lon"], 5)
        s["comuna_cut"] = nearest["cut"]
        s["comuna"] = nearest["nombre"]
        s["distancia_km"] = round(haversine_km(s["lat"], s["lon"], nearest["lat"], nearest["lon"]), 1)
    return stations


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    global REFRESH
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="volver a descargar las fuentes")
    REFRESH = parser.parse_args().refresh

    comunas = build_comunas()
    write_csv(CATALOG / "comunas.csv", comunas)
    estaciones = build_estaciones(comunas)
    write_csv(CATALOG / "estaciones_armada.csv", estaciones)

    by_source: dict[str, int] = {}
    for c in comunas:
        by_source[c["fuente_coord"]] = by_source.get(c["fuente_coord"], 0) + 1
    print(f"comunas: {len(comunas)} {by_source}")
    print(f"estaciones Armada: {len(estaciones)}")
    for s in estaciones:
        if not s["coord_valida"]:
            print(f"  coordenadas inválidas: {s['id']} {s['nombre']} ({s['lat']}, {s['lon']})")
    for c in comunas:
        if c["fuente_coord"] == "SIN_COORDENADAS":
            print(f"  sin coordenadas: {c['cut']} {c['nombre']} ({c['region']})")


if __name__ == "__main__":
    main()
