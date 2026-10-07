"""Consumo y preparación de datos desde la API pública Open-Meteo (sin clave)."""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from . import conocimiento as K

URL_FORECAST = "https://api.open-meteo.com/v1/forecast"
URL_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES_HORARIAS = ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "cloud_cover", "wind_speed_10m"]


def a_fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def obtener_horario(lat, lon, inicio, fin):
    """Consulta datos horarios. Usa el archivo histórico (ERA5) para fechas pasadas y el pronóstico para las recientes."""
    inicio, fin = a_fecha(inicio), a_fecha(fin)
    endpoint = URL_ARCHIVE if fin < date.today() - timedelta(days=7) else URL_FORECAST
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": inicio.isoformat(), "end_date": fin.isoformat(),
        "hourly": ",".join(VARIABLES_HORARIAS), "timezone": "auto",
    }
    r = requests.get(endpoint, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "hourly" not in j:
        raise ValueError(f"Respuesta inesperada de la API: {str(j)[:200]}")
    df = pd.DataFrame(j["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    sha = hashlib.sha256(json.dumps(j["hourly"], sort_keys=True).encode()).hexdigest()
    return {
        "fuente": "Open-Meteo", "endpoint": endpoint, "url": r.url,
        "consulta_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lat": j.get("latitude"), "lon": j.get("longitude"), "elevacion": j.get("elevation"),
        "zona_horaria": j.get("timezone"), "unidades": j.get("hourly_units"),
        "sha256_horario": sha, "df": df,
    }


def preparar(df, fecha):
    """Transforma 24 valores horarios del día local en las 4 entradas del sistema experto."""
    fecha = a_fecha(fecha)
    dia = df[df["time"].dt.date == fecha].copy()
    if len(dia) < 20 or dia["temperature_2m"].isna().sum() > 4:
        raise ValueError("Datos insuficientes para la fecha solicitada (se requieren >= 20 horas válidas).")
    h0, h1 = K.VENTANA_NOCTURNA
    noche = dia[dia["time"].dt.hour.between(h0, h1)]
    if noche["wind_speed_10m"].isna().all() or noche["cloud_cover"].isna().all():
        raise ValueError("Faltan datos de viento o nubosidad en la ventana nocturna.")
    entradas = {
        "temp_min": round(float(dia["temperature_2m"].min()), 1),
        "temp_max": round(float(dia["temperature_2m"].max()), 1),
        "viento": round(float(noche["wind_speed_10m"].mean()), 1),
        "nubosidad": round(float(noche["cloud_cover"].mean()), 0),
    }
    ventana = f"{h0:02d}:00-{h1:02d}:59"
    transformaciones = [
        {"variable": "temp_min", "origen": "temperature_2m (horario, °C)", "operacion": "mínimo de las 24 h del día local",
         "justificacion": "La helada depende de la temperatura mínima alcanzada, no del promedio.", "valor": entradas["temp_min"]},
        {"variable": "temp_max", "origen": "temperature_2m (horario, °C)", "operacion": "máximo de las 24 h del día local",
         "justificacion": "El estrés por calor se asocia al pico diurno.", "valor": entradas["temp_max"]},
        {"variable": "viento", "origen": "wind_speed_10m (horario, km/h)", "operacion": f"promedio en la ventana nocturna {ventana}",
         "justificacion": "La helada radiativa se define en la madrugada; el viento diurno no es relevante.", "valor": entradas["viento"]},
        {"variable": "nubosidad", "origen": "cloud_cover (horario, %)", "operacion": f"promedio en la ventana nocturna {ventana}",
         "justificacion": "El cielo despejado nocturno favorece el enfriamiento radiativo.", "valor": entradas["nubosidad"]},
    ]
    return {"entradas": entradas, "transformaciones": transformaciones, "horario_dia": dia.reset_index(drop=True)}


def dia_extremo(lat, lon, inicio, fin, modo="frio"):
    """Busca en un rango el día con la mínima más baja ('frio') o la máxima más alta ('calor'). Una sola consulta."""
    d = obtener_horario(lat, lon, inicio, fin)["df"].copy()
    d["fecha"] = d["time"].dt.date
    g = d.groupby("fecha")["temperature_2m"].agg(["min", "max", "count"])
    g = g[g["count"] >= 20]
    if g.empty:
        raise ValueError("No hay días completos en el rango solicitado.")
    fecha = g["min"].idxmin() if modo == "frio" else g["max"].idxmax()
    return fecha, g
