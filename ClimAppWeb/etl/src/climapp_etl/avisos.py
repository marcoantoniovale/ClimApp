"""Avisos de la Armada (marejadas, mal tiempo, temporal) y su asignación a comunas costeras.

La portada de meteoarmada.directemar.cl lista los avisos vigentes como tarjetas:
zona (alert__subtitle), tipo (alert__description), fecha en hora de Chile (alert__date) y enlace.
El contenido de cada aviso es una imagen y un PDF escaneado (sin texto): en la Fase 1 se guardan
los metadatos y los enlaces (docs/spikes-semana1.md §2).

Las zonas son tramos de costa ("PUNTA LAVAPIÉ A CORRAL", "GOLFO DE PENAS HASTA ARICA Y ARCH.
JUAN FERNÁNDEZ"). Cada extremo se resuelve con el nomenclátor LANDMARKS, los nombres de comunas o
los de regiones; un tramo cubre las comunas costeras continentales entre ambas latitudes.
"""

from __future__ import annotations

import html
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from . import http

BASE_URL = "https://meteoarmada.directemar.cl/"
CHILE = ZoneInfo("America/Santiago")

# Accidentes geográficos que aparecen en las zonas de aviso y no son comunas: (lat, lon) aproximados.
LANDMARKS = {
    "punta angamos": (-23.02, -70.51),
    "punta lengua de vaca": (-30.24, -71.63),
    "punta curaumilla": (-33.10, -71.74),
    "punta topocalma": (-34.13, -72.00),
    "punta lavapie": (-37.15, -73.58),
    "golfo de arauco": (-37.20, -73.30),
    "isla mocha": (-38.37, -73.90),
    "canal chacao": (-41.80, -73.50),
    "golfo coronados": (-41.75, -73.80),
    "seno de reloncavi": (-41.60, -72.60),
    "golfo de ancud": (-42.00, -73.00),
    "isla buta chauques": (-42.27, -73.10),
    "isla butachauques": (-42.27, -73.10),
    "golfo corcovado": (-43.40, -73.30),
    "boca del guafo": (-43.60, -74.00),
    "canal moraleda": (-45.00, -73.50),
    "moraleda": (-45.00, -73.50),
    "bahia anna pink": (-45.80, -74.70),
    "peninsula de taitao": (-46.50, -75.00),
    "golfo de penas": (-47.40, -74.70),
    "faro san pedro": (-47.72, -74.92),
    "faro evangelistas": (-52.40, -75.10),
    "estrecho de magallanes": (-53.50, -70.50),
    "bahia de punta arenas": (-53.16, -70.90),
    "puerto harris": (-53.80, -70.40),
    "canal beagle": (-54.90, -68.50),
}
ALIASES = {"rapa nui": "isla de pascua", "archipielago juan fernandez": "juan fernandez"}

# Orden de las regiones de norte a sur (para tramos entre regiones).
REGIONS = {
    "arica parinacota": "15", "tarapaca": "01", "antofagasta": "02", "atacama": "03", "coquimbo": "04",
    "valparaiso": "05", "ohiggins": "06", "maule": "07", "nuble": "16", "biobio": "08",
    "araucania": "09", "la araucania": "09", "los rios": "14", "los lagos": "10", "aysen": "11",
    "magallanes": "12",
}
CONTINENTAL_MIN_LON = -76.0     # excluye Isla de Pascua y Juan Fernández de los tramos
NEAREST_MAX_KM = 80.0
LAT_MARGIN = 0.05


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\barch\.?\s", "archipielago ", text)
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text.replace("arica y parinacota", "arica parinacota")   # para no partirla en " y "


@dataclass
class Comuna:
    id: int
    nombre: str
    region_id: str
    lat: float
    lon: float


@dataclass
class Warning:
    zona: str
    tipo: str
    titulo: str
    emitido_at: datetime
    url_fuente: str
    url_documento: str | None = None
    location_ids: list[int] = field(default_factory=list)
    sin_resolver: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{normalize(self.zona).replace(' ', '-')}-{self.emitido_at:%Y%m%d%H%M}"


def tipo_from(description: str) -> str:
    d = normalize(description)
    for key, tipo in (("marejada", "marejadas"), ("temporal", "temporal"), ("mal tiempo", "mal_tiempo"),
                      ("viento", "viento"), ("convectiv", "convectivas"), ("niebla", "niebla")):
        if key in d:
            return tipo
    return "otro"


def parse_portada(page: str) -> list[Warning]:
    warnings = []
    for block in re.findall(r'<div class="alert__info">(.*?)</div>', page, re.S):
        def text(cls: str) -> str:
            m = re.search(rf'class="{cls}"[^>]*>(.*?)<', block, re.S)
            return html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""

        zona, titulo, fecha = text("alert__subtitle").rstrip(". "), text("alert__description"), text("alert__date")
        href = re.search(r'href="([^"]+)"', block)
        try:
            emitido = datetime.strptime(fecha, "%d/%m/%Y %H:%M").replace(tzinfo=CHILE).astimezone(timezone.utc)
        except ValueError:
            continue
        if not zona:
            continue
        url = urljoin(BASE_URL, href.group(1)) if href else BASE_URL
        warnings.append(Warning(zona=zona, tipo=tipo_from(titulo), titulo=titulo, emitido_at=emitido,
                                url_fuente=url))
    return warnings


def parse_documento(page: str, url: str) -> str | None:
    """Enlace al PDF del aviso (o, si no hay, a la imagen más reciente) en la página de detalle."""
    pdfs = re.findall(r'href="([^"]*/site/docs/[^"]+\.pdf)"', page, re.I)
    if pdfs:
        return urljoin(url, pdfs[-1])
    images = sorted(re.findall(r'src="([^"]*/site/artic/(\d{8})/[^"]+\.(?:jpg|jpeg|png))"', page, re.I),
                    key=lambda m: m[1])
    return urljoin(url, images[-1][0]) if images else None


def _km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


class ZoneResolver:
    """Resuelve el texto de una zona a las comunas costeras que cubre."""

    def __init__(self, coastal: list[Comuna]):
        self.coastal = coastal
        self.by_name = {normalize(c.nombre): c for c in coastal}

    def _place(self, name: str):
        """('punto', lat, lon) | ('region', region_id) | None."""
        name = ALIASES.get(name, name)
        candidates = [name] + [re.sub(rf"^{p} ", "", name) for p in
                               ("faro", "puerto", "bahia de", "bahia", "isla", "caleta", "punta", "archipielago")]
        for cand in candidates:
            if cand in LANDMARKS:
                return ("punto", *LANDMARKS[cand])
            cand = ALIASES.get(cand, cand)
            if cand in self.by_name:
                c = self.by_name[cand]
                return ("punto", c.lat, c.lon)
            if cand in REGIONS:
                return ("region", REGIONS[cand])
        return None

    def _lat_range(self, place) -> tuple[float, float]:
        if place[0] == "punto":
            return place[1], place[1]
        lats = [c.lat for c in self.coastal if c.region_id == place[1] and c.lon > CONTINENTAL_MIN_LON]
        return min(lats), max(lats)

    def resolve(self, zona: str) -> tuple[set[int], list[str]]:
        ids: set[int] = set()
        unresolved = []
        parts = [p for chunk in zona.split(",") for p in re.split(r"\s+y\s+", normalize(chunk))]
        for part in parts:
            if not part:
                continue
            ends = re.split(r"\s+(?:a|hasta)\s+", part)
            places = [self._place(e) for e in ends]
            if any(p is None for p in places):
                unresolved.append(part)
                continue
            if len(places) >= 2:
                ranges = [self._lat_range(p) for p in places]
                lo = min(r[0] for r in ranges) - LAT_MARGIN
                hi = max(r[1] for r in ranges) + LAT_MARGIN
                ids |= {c.id for c in self.coastal if lo <= c.lat <= hi and c.lon > CONTINENTAL_MIN_LON}
            elif places[0][0] == "region":
                ids |= {c.id for c in self.coastal if c.region_id == places[0][1]}
            else:
                _, lat, lon = places[0]
                nearest = min(self.coastal, key=lambda c: _km(lat, lon, c.lat, c.lon))
                if _km(lat, lon, nearest.lat, nearest.lon) <= NEAREST_MAX_KM:
                    ids.add(nearest.id)
                else:
                    unresolved.append(part)
        return ids, unresolved


def fetch_vigentes(coastal: list[Comuna], known_ids: set[str], get_text=None) -> list[Warning]:
    """Avisos vigentes con sus comunas. Solo visita la página de detalle de los avisos nuevos."""
    get_text = get_text or http.get_text
    warnings = parse_portada(get_text(BASE_URL))
    resolver = ZoneResolver(coastal)
    for w in warnings:
        ids, w.sin_resolver = resolver.resolve(w.zona)
        w.location_ids = sorted(ids)
        if w.id not in known_ids and w.url_fuente.rstrip("/") != BASE_URL.rstrip("/"):
            try:
                w.url_documento = parse_documento(get_text(w.url_fuente), w.url_fuente)
            except RuntimeError:
                w.url_documento = None
    return warnings
