"""Base de conocimiento: variables lingüísticas, conjuntos difusos, reglas SI-ENTONCES y recomendaciones.

Tipos de función de pertenencia:
  ("trap", (a, b, c, d))  trapezoidal: sube de a a b, vale 1 entre b y c, baja de c a d.
  ("tri",  (a, b, c))     triangular: sube de a a b, baja de b a c.
"""
import hashlib
import json

ORDEN_NIVELES = ["bajo", "moderado", "alto", "critico"]
NOMBRES_NIVEL = {"bajo": "Bajo", "moderado": "Moderado", "alto": "Alto", "critico": "Crítico"}
COLORES_NIVEL = {"bajo": "#2e9e5b", "moderado": "#f2c200", "alto": "#f07f1a", "critico": "#d62828"}

# Condición de notificación (decisión de modelado): se activa cuando el índice de riesgo calculado
# por el motor difuso es >= 60, valor a partir del cual el nivel "alto" domina sobre "moderado".
UMBRAL_NOTIFICACION = 60.0
# Ventana nocturna local (horas 0-7): periodo de enfriamiento radiativo previo al amanecer.
VENTANA_NOCTURNA = (0, 7)

VARIABLES = {
    "temp_min": {
        "etiqueta": "Temperatura mínima del día (°C)",
        "universo": (-10.0, 25.0),
        "conjuntos": {
            "helada": ("trap", (-10, -10, 0, 2)),
            "fria": ("tri", (0, 3, 7)),
            "fresca": ("tri", (5, 10, 15)),
            "templada": ("trap", (13, 17, 25, 25)),
        },
        "justificacion": (
            "Referencia técnica: helada meteorológica = temperatura del aire a 2 m <= 0 °C (definición OMM). "
            "La temperatura a nivel del cultivo suele ser 1-3 °C menor que la del abrigo meteorológico, por eso "
            "'helada' decrece gradualmente hasta 2 °C (decisión de modelado). 'fria' (0-7 °C) representa noches donde "
            "una helada radiativa es posible si el cielo está despejado y en calma. 'fresca' y 'templada' no "
            "representan amenaza por frío (decisión de modelado)."
        ),
    },
    "temp_max": {
        "etiqueta": "Temperatura máxima del día (°C)",
        "universo": (5.0, 45.0),
        "conjuntos": {
            "moderada": ("trap", (5, 5, 24, 28)),
            "calida": ("tri", (26, 31, 36)),
            "muy_calida": ("trap", (33, 37, 45, 45)),
        },
        "justificacion": (
            "Referencia agronómica general: por encima de ~30-35 °C muchos cultivos reducen la fotosíntesis, "
            "aumentan la demanda hídrica y pueden abortar flores. El umbral exacto depende de la especie, por lo que "
            "estos rangos son una decisión de modelado que debe ajustarse al cultivo evaluado."
        ),
    },
    "viento": {
        "etiqueta": "Viento medio nocturno a 10 m (km/h)",
        "universo": (0.0, 40.0),
        "conjuntos": {
            "calma": ("trap", (0, 0, 3, 8)),
            "brisa": ("tri", (5, 12, 20)),
            "fuerte": ("trap", (15, 25, 40, 40)),
        },
        "justificacion": (
            "Las heladas radiativas se forman con aire en calma; el viento mezcla las capas de aire y reduce la "
            "inversión térmica cerca del suelo. Los cortes (calma <= ~5 km/h, brisa 5-20, fuerte > 15) son una "
            "decisión de modelado inspirada en la escala Beaufort."
        ),
    },
    "nubosidad": {
        "etiqueta": "Nubosidad media nocturna (%)",
        "universo": (0.0, 100.0),
        "conjuntos": {
            "despejado": ("trap", (0, 0, 20, 40)),
            "parcial": ("tri", (30, 50, 70)),
            "nublado": ("trap", (60, 80, 100, 100)),
        },
        "justificacion": (
            "Las nubes devuelven radiación de onda larga y frenan el enfriamiento nocturno. Se tomó como referencia la "
            "clasificación meteorológica en octas (<=2/8 despejado, 3-5/8 parcial, >=6/8 nublado) con transiciones "
            "suaves (decisión de modelado)."
        ),
    },
}

SALIDA = {
    "etiqueta": "Índice de riesgo térmico (0-100)",
    "universo": (0.0, 100.0),
    "conjuntos": {
        "bajo": ("trap", (0, 0, 15, 30)),
        "moderado": ("tri", (20, 40, 60)),
        "alto": ("tri", (50, 70, 85)),
        "critico": ("trap", (75, 90, 100, 100)),
    },
    "justificacion": "Escala normalizada de 0 a 100 con cuatro niveles traslapados (decisión de modelado).",
}

# tipo: tipo de riesgo que representa la regla (helada / calor). si: antecedentes unidos con Y (mínimo).
REGLAS = [
    {"id": "R1", "si": {"temp_min": "helada", "nubosidad": "despejado"}, "entonces": "critico", "tipo": "helada"},
    {"id": "R2", "si": {"temp_min": "helada", "nubosidad": "parcial"}, "entonces": "critico", "tipo": "helada"},
    {"id": "R3", "si": {"temp_min": "helada", "nubosidad": "nublado"}, "entonces": "alto", "tipo": "helada"},
    {"id": "R4", "si": {"temp_min": "fria", "nubosidad": "despejado", "viento": "calma"}, "entonces": "alto", "tipo": "helada"},
    {"id": "R5", "si": {"temp_min": "fria", "nubosidad": "despejado", "viento": "brisa"}, "entonces": "moderado", "tipo": "helada"},
    {"id": "R6", "si": {"temp_min": "fria", "nubosidad": "despejado", "viento": "fuerte"}, "entonces": "bajo", "tipo": "helada"},
    {"id": "R7", "si": {"temp_min": "fria", "nubosidad": "parcial"}, "entonces": "moderado", "tipo": "helada"},
    {"id": "R8", "si": {"temp_min": "fria", "nubosidad": "nublado"}, "entonces": "bajo", "tipo": "helada"},
    {"id": "R9", "si": {"temp_min": "fresca"}, "entonces": "bajo", "tipo": "helada"},
    {"id": "R10", "si": {"temp_min": "templada", "temp_max": "moderada"}, "entonces": "bajo", "tipo": "calor"},
    {"id": "R11", "si": {"temp_max": "calida"}, "entonces": "moderado", "tipo": "calor"},
    {"id": "R12", "si": {"temp_max": "muy_calida", "temp_min": "fresca"}, "entonces": "alto", "tipo": "calor"},
    {"id": "R13", "si": {"temp_max": "muy_calida", "temp_min": "templada"}, "entonces": "critico", "tipo": "calor"},
    {"id": "R14", "si": {"temp_max": "muy_calida", "temp_min": "fria"}, "entonces": "alto", "tipo": "calor"},
]

RECOMENDACIONES = {
    ("helada", "moderado"): "Vigile la temperatura nocturna en el lote y tenga listos los materiales de protección (mantas térmicas, plástico). Evite podas y fertilización nitrogenada en las próximas 48 h.",
    ("helada", "alto"): "Proteja los cultivos sensibles antes del anochecer: cubra con mantas térmicas o plástico, riegue el suelo al final de la tarde (el suelo húmedo conserva más calor) y prepare el riego por aspersión antihelada si dispone de él.",
    ("helada", "critico"): "Active el plan antihelada: riego por aspersión continuo o cobertura total desde la madrugada, calefacción o humo controlado si es viable, y posponga siembras y trasplantes. Revise el lote al amanecer para evaluar daños.",
    ("calor", "moderado"): "Programe el riego en las horas frescas (madrugada o tarde), mantenga el suelo con cobertura (mulch) y vigile signos de marchitez en las horas centrales del día.",
    ("calor", "alto"): "Aumente la frecuencia de riego, cubra el suelo, use malla sombra en cultivos sensibles y evite labores de campo entre las 11:00 y las 15:00.",
    ("calor", "critico"): "Aplique riego de emergencia y sombreo inmediato; suspenda podas, trasplantes y aplicaciones foliares en horas de calor y garantice agua para personal y animales.",
}
SIN_RIESGO = "Sin riesgo térmico relevante para esta fecha: mantenga el monitoreo rutinario del lote."
AVISO = "Recomendación general; ajústela al cultivo, la etapa fenológica y consulte a un agrónomo local."


def recomendar(tipo, nivel):
    if nivel == "bajo" or tipo == "ninguno":
        return SIN_RIESGO
    return RECOMENDACIONES.get((tipo, nivel), SIN_RIESGO)


def texto_regla(regla):
    cond = " Y ".join(f"{v} es {c}" for v, c in regla["si"].items())
    return f"SI {cond} ENTONCES riesgo es {regla['entonces']}"


def huella():
    """Huella (hash) de la base de conocimiento para saber con qué versión se tomó cada decisión."""
    carga = json.dumps({"variables": VARIABLES, "salida": SALIDA, "reglas": REGLAS}, sort_keys=True, default=str)
    return hashlib.sha256(carga.encode()).hexdigest()[:16]
