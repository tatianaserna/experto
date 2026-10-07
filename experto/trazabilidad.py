"""Trazabilidad: dato de origen -> transformación -> inferencia -> reglas -> resultado -> recomendación -> explicación/acción."""
import json
import os
import uuid
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from . import conocimiento as K
from . import motor


def limpiar(obj):
    """Convierte a tipos JSON y descarta claves internas (que empiezan con '_')."""
    if isinstance(obj, dict):
        return {str(k): limpiar(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [limpiar(v) for v in obj]
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (date, datetime, pd.Timestamp)):
        return str(obj)
    return obj


def nuevo_id():
    return uuid.uuid4().hex[:12]


def crear_traza(traza_id, consulta, ubicacion, fecha, prep, inf, recomendacion, explicacion, notificacion):
    horario = prep["horario_dia"].copy()
    horario["time"] = horario["time"].astype(str)
    traza = {
        "id": traza_id,
        "creado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_conocimiento_huella": K.huella(),
        "1_dato_origen": {
            "fuente": consulta["fuente"], "endpoint": consulta["endpoint"], "url": consulta["url"],
            "consulta_utc": consulta["consulta_utc"], "sha256_horario": consulta["sha256_horario"],
            "ubicacion": ubicacion, "fecha": str(fecha), "unidades": consulta.get("unidades"),
            "horario_dia": horario.to_dict("records"),
        },
        "2_transformacion": {
            "operaciones": prep["transformaciones"],
            "entradas_originales": inf["entradas_originales"],
            "entradas_usadas": inf["entradas_usadas"], "recortes_universo": inf["recortes_universo"],
        },
        "3_inferencia": {
            "fuzzificacion": inf["fuzzificacion"],
            "agregacion": inf["agregacion"], "defuzzificacion": "centroide (0-100)",
        },
        "4_reglas": inf["reglas_activas"],
        "5_resultado": {"riesgo": inf["resultado"], "nivel": inf["nivel"], "tipo": inf["tipo"],
                        "grados_salida": inf["grados_salida"]},
        "6_recomendacion": recomendacion,
        "7_explicacion_accion": {"explicacion": explicacion, "notificacion": notificacion},
    }
    return limpiar(traza)


def guardar(traza, carpeta="salidas"):
    destino = os.path.join(carpeta, "trazas")
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, f"traza_{traza['id']}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(traza, f, ensure_ascii=False, indent=2)
    with open(os.path.join(carpeta, "trazas.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": traza["id"], "creado_utc": traza["creado_utc"],
                            "ubicacion": traza["1_dato_origen"]["ubicacion"]["nombre"],
                            "fecha": traza["1_dato_origen"]["fecha"],
                            "riesgo": traza["5_resultado"]["riesgo"], "nivel": traza["5_resultado"]["nivel"]},
                           ensure_ascii=False) + "\n")
    return ruta


def cadena(t):
    o, tr, i = t["1_dato_origen"], t["2_transformacion"], t["3_inferencia"]
    res, ex = t["5_resultado"], t["7_explicacion_accion"]
    L = [f"TRAZA {t['id']}  (creada {t['creado_utc']}, base de conocimiento {t['base_conocimiento_huella']})", ""]
    L += ["1) DATO DE ORIGEN",
          f"   {o['fuente']} | {o['ubicacion']['nombre']} ({o['ubicacion']['lat']}, {o['ubicacion']['lon']}) | fecha {o['fecha']}",
          f"   URL: {o['url']}", f"   Consulta UTC: {o['consulta_utc']} | SHA-256 de los datos horarios: {o['sha256_horario'][:16]}...", ""]
    L += ["2) TRANSFORMACIÓN"]
    L += [f"   {x['variable']} = {x['valor']}  <-  {x['operacion']} de {x['origen']}" for x in tr["operaciones"]]
    if tr["recortes_universo"]:
        L += [f"   Ajuste al universo: {tr['recortes_universo']}"]
    L += ["", "3) INFERENCIA (grados de pertenencia > 0)"]
    for var, conj in i["fuzzificacion"].items():
        L += [f"   {var}: " + (", ".join(f"{c}={g:.2f}" for c, g in conj.items() if g > 0) or "ninguno")]
    L += [f"   Agregación: recorte máximo por consecuente = {i['agregacion']['recorte_por_consecuente']}",
          f"   Defuzzificación: {i['defuzzificacion']}", "", "4) REGLAS ACTIVADAS"]
    L += [f"   {r['id']} fuerza={r['fuerza']:.2f} (limita: {r['limitante']}) | {r['texto']}" for r in t["4_reglas"]]
    L += ["", f"5) RESULTADO: riesgo {res['riesgo']}/100 | nivel {res['nivel']} | tipo {res['tipo']}",
          "", f"6) RECOMENDACIÓN: {t['6_recomendacion']}", "",
          f"7) EXPLICACIÓN ({ex['explicacion']['fuente']}): {ex['explicacion']['texto']}"]
    n = ex["notificacion"]
    L += [f"   ACCIÓN: {'NOTIFICACIÓN -> ' + n['titulo'] if n else 'sin notificación (riesgo por debajo del umbral ' + str(K.UMBRAL_NOTIFICACION) + ')'}"]
    return "\n".join(L)


def verificar(t):
    """Reproduce la inferencia desde las entradas guardadas y compara con lo registrado."""
    inf = motor.inferir(t["2_transformacion"]["entradas_originales"])
    return {
        "resultado_reproducido": abs(inf["resultado"] - t["5_resultado"]["riesgo"]) < 0.01,
        "base_conocimiento_igual": K.huella() == t["base_conocimiento_huella"],
        "riesgo_guardado": t["5_resultado"]["riesgo"], "riesgo_recalculado": inf["resultado"],
    }
