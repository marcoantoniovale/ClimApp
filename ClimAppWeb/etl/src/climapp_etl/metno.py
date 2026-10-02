"""MET Norway Locationforecast 2.0 (el pronóstico de la aplicación Yr), solo para comparar.

ClimApp usa la mezcla ICON + ECMWF IFS; este conector guarda en forecast_archive (modelo 'yr') el
pronóstico de Yr en los puntos de las estaciones, para medirlo contra las mediciones con el mismo
criterio que los demás modelos. Fuera de los países nórdicos Yr se basa en ECMWF IFS 9 km con
ajuste por altura (GMTED2010, 1 km).

Condiciones de uso (https://api.met.no/doc/TermsOfService): identificarse con un User-Agent con
datos de contacto, no más de 20 peticiones por segundo, coordenadas con ≤ 4 decimales. Licencia de
los datos: CC BY 4.0 (atribución a MET Norway).
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime

URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
USER_AGENT = "ClimApp/0.1 (+https://climapp-chile.vercel.app)"


def fetch(lat: float, lon: float, timeout: int = 30) -> dict:
    request = urllib.request.Request(f"{URL}?lat={lat:.4f}&lon={lon:.4f}",
                                     headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def rows(data: dict) -> list[tuple[datetime, dict]]:
    """(hora UTC, {columna: valor}) con las columnas de forecast_archive. Viento en m/s.
    La lluvia es la de la hora siguiente (solo en el tramo horario, ~60 h)."""
    out = []
    for paso in data["properties"]["timeseries"]:
        d = paso["data"]["instant"]["details"]
        lluvia = paso["data"].get("next_1_hours", {}).get("details", {}).get("precipitation_amount")
        out.append((datetime.fromisoformat(paso["time"].replace("Z", "+00:00")), {
            "temperatura": d.get("air_temperature"),
            "humedad": d.get("relative_humidity"),
            "precipitacion": lluvia,
            "viento_vel": d.get("wind_speed"),
            "viento_dir": d.get("wind_from_direction"),
            "viento_rafaga": d.get("wind_speed_of_gust"),
            "presion": d.get("air_pressure_at_sea_level"),
        }))
    return out

