"""Motor de inferencia difuso tipo Mamdani implementado desde cero con NumPy.

Flujo: datos -> fuzzificación -> grados de pertenencia -> activación de reglas (mínimo)
       -> agregación (máximo) -> defuzzificación (centroide) -> resultado.
"""
import numpy as np

from . import conocimiento as K


def trapmf(x, a, b, c, d):
    x = np.asarray(x, dtype=float)
    y = np.zeros_like(x)
    if b > a:
        y = np.where((x > a) & (x < b), (x - a) / (b - a), y)
    y = np.where((x >= b) & (x <= c), 1.0, y)
    if d > c:
        y = np.where((x > c) & (x < d), (d - x) / (d - c), y)
    return y


def membresia(x, definicion):
    tipo, p = definicion
    if tipo == "trap":
        return trapmf(x, *p)
    return trapmf(x, p[0], p[1], p[1], p[2])


def recortar_universo(entradas):
    """Limita cada entrada a su universo de discurso y registra si hubo ajuste."""
    usadas, recortes = {}, []
    for var, valor in entradas.items():
        lo, hi = K.VARIABLES[var]["universo"]
        u = float(min(max(valor, lo), hi))
        if u != float(valor):
            recortes.append({"variable": var, "original": float(valor), "usado": u})
        usadas[var] = u
    return usadas, recortes


def fuzzificar(entradas):
    return {
        var: {c: float(membresia(x, d)) for c, d in K.VARIABLES[var]["conjuntos"].items()}
        for var, x in entradas.items()
    }


def activar(grados):
    """Evalúa todas las reglas: fuerza = mínimo de los grados de sus antecedentes (operador Y)."""
    resultado = []
    for r in K.REGLAS:
        ants = [{"variable": v, "conjunto": c, "grado": grados[v][c]} for v, c in r["si"].items()]
        limitante = min(ants, key=lambda a: a["grado"])
        resultado.append({
            "id": r["id"], "texto": K.texto_regla(r), "tipo": r["tipo"],
            "consecuente": r["entonces"], "fuerza": min(a["grado"] for a in ants),
            "antecedentes": ants, "limitante": f"{limitante['variable']} es {limitante['conjunto']}",
        })
    return resultado


def agregar(activas, puntos=1001):
    lo, hi = K.SALIDA["universo"]
    x = np.linspace(lo, hi, puntos)
    agg = np.zeros_like(x)
    for r in activas:
        recorte = np.minimum(r["fuerza"], membresia(x, K.SALIDA["conjuntos"][r["consecuente"]]))
        agg = np.maximum(agg, recorte)
    return x, agg


def defuzzificar(x, agg):
    area = agg.sum()
    return float((x * agg).sum() / area) if area > 0 else 0.0


def inferir(entradas):
    usadas, recortes = recortar_universo(entradas)
    grados = fuzzificar(usadas)
    reglas = activar(grados)
    activas = sorted([r for r in reglas if r["fuerza"] > 1e-9], key=lambda r: -r["fuerza"])
    x, agg = agregar(activas)
    resultado = round(defuzzificar(x, agg), 2)

    grados_salida = {c: float(membresia(resultado, d)) for c, d in K.SALIDA["conjuntos"].items()}
    nivel = max(K.ORDEN_NIVELES, key=lambda n: (grados_salida[n], K.ORDEN_NIVELES.index(n)))

    puntajes = {"helada": 0.0, "calor": 0.0}
    for r in activas:
        if r["consecuente"] != "bajo":
            puntajes[r["tipo"]] = max(puntajes[r["tipo"]], r["fuerza"])
    tipo = max(puntajes, key=puntajes.get) if (nivel != "bajo" and max(puntajes.values()) > 0) else "ninguno"

    consecuentes = {}
    for r in activas:
        consecuentes[r["consecuente"]] = max(consecuentes.get(r["consecuente"], 0.0), r["fuerza"])

    return {
        "entradas_originales": {k: float(v) for k, v in entradas.items()},
        "entradas_usadas": usadas, "recortes_universo": recortes,
        "fuzzificacion": grados, "reglas": reglas, "reglas_activas": activas,
        "agregacion": {"recorte_por_consecuente": consecuentes},
        "resultado": resultado, "grados_salida": grados_salida,
        "nivel": nivel, "tipo": tipo, "puntajes_tipo": puntajes,
        "_curva": {"x": x, "agg": agg},
    }
