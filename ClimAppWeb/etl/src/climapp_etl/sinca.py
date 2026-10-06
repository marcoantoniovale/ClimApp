"""SINCA (Sistema de Información Nacional de Calidad del Aire, Ministerio del Medio Ambiente).

Muchas estaciones de calidad del aire miden también temperatura. Segunda fuente de mediciones del
algoritmo ClimApp, sobre todo en ciudades donde la DMC tiene pocas estaciones (p. ej. el norte de
Santiago).

- Catálogo: `listadomapa2k19` (estaciones con coordenadas) y la página de cada estación, de donde se
  toma la serie de temperatura vigente (`./RM/D14/Met/TEMP//horario_003.ic`). El job `sinca_catalogo`
  lo renueva cada semana en la base (stations.serie); data/catalog/estaciones_sinca.csv
  (scripts/build_sinca.py) es la semilla y el respaldo.
- Datos: exportación CSV de Airviro (`apub.tsindico2.cgi?outtype=xcl`), promedio horario.
  Hora rotulada al INICIO del período, en hora estándar UTC−4 fija (sin horario de verano): verificado
  el 2026-10-01 contra Quinta Normal (DMC); la serie de Parque O'Higgins calza desfasada una hora
  respecto de la hora oficial de verano. Cada promedio se fecha en el centro de su hora.
"""

from __future__ import annotations

import csv
import functools
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import http

BASE = "https://sinca.mma.gob.cl"
LISTADO_URL = f"{BASE}/index.php/json/listadomapa2k19/"
ESTACION_URL = f"{BASE}/index.php/estacion/index/key/{{key}}"
EXPORT_URL = f"{BASE}/cgi-bin/APUB-MMA/apub.tsindico2.cgi"
CATALOGO = Path(__file__).resolve().parents[2] / "data" / "catalog" / "estaciones_sinca.csv"
HORA_SINCA = timezone(timedelta(hours=-4))
# La consulta típica tarda ~1 s, pero a veces una queda colgada: con el plazo general (60 s) esa sola
# estación alargaba sinca_obs de ~15 a ~75 s (medido el 2026-10-06). Plazo corto y reintento.
_get_rapido = functools.partial(http.get_text, timeout=8, attempts=3)

_SERIE = re.compile(r"macropath=(\./[^&\"']+/Met/TEMP)&(?:amp;)?macro=(horario_\d+)&(?:amp;)?from=\d+&(?:amp;)?to=(\d+)")


@dataclass(frozen=True)
class Estacion:
    key: str
    nombre: str
    comuna: str
    lat: float
    lon: float
    serie: str          # macro de Airviro de la temperatura horaria

    @property
    def id(self) -> str:
        return f"sinca-{self.key}"


def serie_temperatura(pagina: str) -> tuple[str, str] | None:
    """(macro, fecha final AAMMDD) de la serie de temperatura más reciente en la página de una estación."""
    series = [(hasta, f"{ruta}//{macro}.ic") for ruta, macro, hasta in _SERIE.findall(pagina)]
    if not series:
        return None
    hasta, macro = max(series)
    return macro, hasta


def descubrir(get_json=None, get_text=None, vigencia_dias: int = 30) -> tuple[list[Estacion], int]:
    """Estaciones de SINCA con temperatura actualizada en los últimos `vigencia_dias` días.
    Devuelve (estaciones, total del listado). Lee el listado del mapa y la página de cada estación."""
    get_json = get_json or http.get_json
    get_text = get_text or http.get_text
    listado = get_json(LISTADO_URL)
    vigente = (datetime.now(timezone.utc) - timedelta(days=vigencia_dias)).astimezone(HORA_SINCA).strftime("%y%m%d")

    def serie(est: dict):
        try:
            return est, serie_temperatura(get_text(ESTACION_URL.format(key=est["key"])))
        except Exception:  # una estación caída no detiene el catálogo
            return est, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        encontradas = [(est, s) for est, s in pool.map(serie, listado) if s and s[1] >= vigente]
    estaciones = [Estacion(str(e["key"]), e["nombre"].strip(), e["comuna"], round(float(e["latitud"]), 5),
                           round(float(e["longitud"]), 5), s[0]) for e, s in encontradas]
    return sorted(estaciones, key=lambda e: (-e.lat, e.key)), len(listado)


def guardar_catalogo(estaciones: list[Estacion], path: Path = CATALOGO) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key", "nombre", "comuna", "lat", "lon", "serie"])
        w.writeheader()
        w.writerows({"key": e.key, "nombre": e.nombre, "comuna": e.comuna, "lat": f"{e.lat:.5f}",
                     "lon": f"{e.lon:.5f}", "serie": e.serie} for e in estaciones)


def cargar_catalogo(path: Path = CATALOGO) -> list[Estacion]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [Estacion(r["key"], r["nombre"], r["comuna"], float(r["lat"]), float(r["lon"]), r["serie"])
                for r in csv.DictReader(f)]


def parse_csv(texto: str) -> dict[datetime, float]:
    """CSV de Airviro → {instante UTC (centro de la hora): °C}. Ignora horas sin dato."""
    out = {}
    for linea in texto.splitlines()[1:]:
        campos = linea.split(";")
        if len(campos) < 3 or not re.fullmatch(r"\d{6}", campos[0]) or not re.fullmatch(r"\d{4}", campos[1]):
            continue
        valor = next((c for c in campos[2:] if c.strip()), None)
        if valor is None:
            continue
        try:
            temp = float(valor.replace(",", "."))
        except ValueError:
            continue
        d, h = campos[0], campos[1]
        inicio = datetime(2000 + int(d[:2]), int(d[2:4]), int(d[4:]), tzinfo=HORA_SINCA) + timedelta(hours=int(h[:2]))
        out[(inicio + timedelta(minutes=30)).astimezone(timezone.utc)] = temp
    return out


def fetch_temperaturas(estacion: Estacion, desde: datetime, hasta: datetime, get_text=None) -> dict[datetime, float]:
    """Temperatura horaria de una estación entre dos fechas (inclusive, días en hora SINCA)."""
    get_text = get_text or _get_rapido
    params = {"outtype": "xcl", "macro": estacion.serie,
              "from": desde.astimezone(HORA_SINCA).strftime("%y%m%d"),
              "to": hasta.astimezone(HORA_SINCA).strftime("%y%m%d"),
              "path": "/usr/airviro/data/CONAMA/", "lang": "esp", "rsrc": "", "macropath": ""}
    texto = get_text(f"{EXPORT_URL}?{urllib.parse.urlencode(params, safe='./')}")
    ahora = datetime.now(timezone.utc)
    return {t: v for t, v in parse_csv(texto).items() if t <= ahora}
