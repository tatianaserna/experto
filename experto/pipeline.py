"""Orquestador: API -> preparación -> inferencia -> recomendación -> IA -> notificación -> traza."""
from . import conocimiento as K
from . import datos, ia, motor, notificaciones, trazabilidad


def evaluar(lat, lon, fecha, nombre="Ubicación", usar_ia=True, api_key=None, modelo=None, carpeta="salidas"):
    """Ejecuta todo el flujo. Si carpeta es None no se escribe nada en disco."""
    fecha = datos.a_fecha(fecha)
    consulta = datos.obtener_horario(lat, lon, fecha, fecha)
    prep = datos.preparar(consulta["df"], fecha)
    inf = motor.inferir(prep["entradas"])                      # la decisión la toma el motor experto
    recomendacion = K.recomendar(inf["tipo"], inf["nivel"])    # y la recomendación sale de la base de conocimiento
    ubicacion = {"nombre": nombre, "lat": float(lat), "lon": float(lon), "elevacion": consulta["elevacion"]}
    contexto = {
        "ubicacion": ubicacion, "fecha": str(fecha), "entradas": inf["entradas_usadas"],
        "fuzzificacion": inf["fuzzificacion"], "reglas_activas": inf["reglas_activas"],
        "riesgo": inf["resultado"], "nivel": inf["nivel"], "tipo": inf["tipo"], "recomendacion": recomendacion,
    }
    explicacion = ia.explicar(contexto, usar_ia=usar_ia, api_key=api_key, modelo=modelo)  # la IA solo explica
    traza_id = trazabilidad.nuevo_id()
    notificacion = notificaciones.notificar(traza_id, ubicacion, fecha, inf, recomendacion, carpeta)
    traza = trazabilidad.crear_traza(traza_id, consulta, ubicacion, fecha, prep, inf, recomendacion, explicacion, notificacion)
    ruta = trazabilidad.guardar(traza, carpeta) if carpeta else None
    return {
        "ubicacion": ubicacion, "fecha": str(fecha), "consulta": consulta, "prep": prep, "inferencia": inf,
        "recomendacion": recomendacion, "explicacion": explicacion, "notificacion": notificacion,
        "contexto": contexto, "traza": traza, "ruta_traza": ruta,
    }
