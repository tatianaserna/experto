"""Notificaciones: mensaje en la interfaz + archivo de alertas (JSON Lines y texto legible)."""
import json
import os
from datetime import datetime, timezone

from . import conocimiento as K

TIPO_TXT = {"helada": "HELADA", "calor": "ESTRÉS POR CALOR", "ninguno": "RIESGO TÉRMICO"}


def notificar(traza_id, ubicacion, fecha, inf, recomendacion, carpeta="salidas"):
    """Genera una alerta si el índice del motor difuso alcanza el umbral. Devuelve la alerta o None."""
    if inf["resultado"] < K.UMBRAL_NOTIFICACION:
        return None
    e = inf["entradas_usadas"]
    nivel = K.NOMBRES_NIVEL[inf["nivel"]]
    alerta = {
        "id_traza": traza_id,
        "momento_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "titulo": f"ALERTA DE {TIPO_TXT[inf['tipo']]}: riesgo {nivel.upper()}",
        "mensaje": (
            f"{ubicacion['nombre']} ({fecha}): índice {inf['resultado']:.0f}/100. "
            f"Tmín {e['temp_min']} °C, Tmáx {e['temp_max']} °C, viento nocturno {e['viento']} km/h, "
            f"nubosidad nocturna {e['nubosidad']:.0f}%. Acción: {recomendacion}"
        ),
        "nivel": inf["nivel"], "tipo": inf["tipo"], "riesgo": inf["resultado"],
        "umbral": K.UMBRAL_NOTIFICACION,
        "reglas": [r["id"] for r in inf["reglas_activas"]],
    }
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, "alertas.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(alerta, ensure_ascii=False) + "\n")
        with open(os.path.join(carpeta, "alertas.txt"), "a", encoding="utf-8") as f:
            f.write(f"[{alerta['momento_utc']}] {alerta['titulo']}\n{alerta['mensaje']}\n\n")
    return alerta


def leer_alertas(carpeta="salidas"):
    ruta = os.path.join(carpeta, "alertas.jsonl")
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
