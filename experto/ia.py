"""IA generativa (Anthropic API): SOLO redacta la explicación. No decide ni modifica el resultado."""
import os

from . import conocimiento as K

MODELO_POR_DEFECTO = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SYSTEM = (
    "Eres un asistente que redacta explicaciones para productores agrícolas. Recibes el resultado ya calculado por un "
    "sistema experto difuso. Tu única tarea es explicarlo en español claro (máximo 180 palabras): qué datos se usaron, "
    "qué reglas pesaron más y por qué se recomienda lo indicado. NO cambies, recalcules ni cuestiones el nivel de riesgo "
    "ni la recomendación. No inventes datos ni reglas que no estén en el contexto."
)


def construir_prompt(ctx):
    e = ctx["entradas"]
    lineas_mem = []
    for var, conj in ctx["fuzzificacion"].items():
        vivos = ", ".join(f"{c}={g:.2f}" for c, g in conj.items() if g > 0) or "ninguna"
        lineas_mem.append(f"- {K.VARIABLES[var]['etiqueta']}: {e[var]} -> pertenencia: {vivos}")
    lineas_reglas = [f"- {r['id']} (fuerza {r['fuerza']:.2f}): {r['texto']}" for r in ctx["reglas_activas"]]
    u = ctx["ubicacion"]
    return "\n".join([
        "RESULTADO DEL SISTEMA EXPERTO (ya decidido):",
        f"Ubicación: {u['nombre']} (lat {u['lat']}, lon {u['lon']}, elevación {u.get('elevacion')} m). Fecha: {ctx['fecha']}.",
        f"Índice de riesgo: {ctx['riesgo']:.1f}/100. Nivel: {K.NOMBRES_NIVEL[ctx['nivel']]}. Tipo de riesgo: {ctx['tipo']}.",
        "", "Variables y grados de pertenencia:", *lineas_mem,
        "", "Reglas activadas:", *lineas_reglas,
        "", f"Recomendación del sistema: {ctx['recomendacion']}",
        "", "Redacta la explicación para el productor.",
    ])


def plantilla(ctx):
    """Explicación determinista (respaldo cuando no hay IA generativa disponible)."""
    e = ctx["entradas"]
    top = ", ".join(f"{r['id']} (fuerza {r['fuerza']:.2f})" for r in ctx["reglas_activas"][:3]) or "ninguna"
    tipo = {"helada": "helada", "calor": "estrés por calor", "ninguno": "ningún riesgo térmico relevante"}[ctx["tipo"]]
    return (
        f"El sistema experto estimó un índice de riesgo de {ctx['riesgo']:.0f}/100 (nivel {K.NOMBRES_NIVEL[ctx['nivel']].lower()}), "
        f"asociado a {tipo}. Datos usados: Tmín {e['temp_min']} °C, Tmáx {e['temp_max']} °C, viento nocturno {e['viento']} km/h "
        f"y nubosidad nocturna {e['nubosidad']:.0f}%. Reglas más influyentes: {top}. Recomendación: {ctx['recomendacion']}"
    )


def explicar(ctx, usar_ia=True, api_key=None, modelo=None):
    prompt = construir_prompt(ctx)
    modelo = modelo or MODELO_POR_DEFECTO
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    error = None
    if usar_ia and key:
        try:
            import anthropic
            cliente = anthropic.Anthropic(api_key=key)
            msg = cliente.messages.create(
                model=modelo, max_tokens=600, system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            texto = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
            coherente = K.NOMBRES_NIVEL[ctx["nivel"]].lower() in texto.lower()
            return {"texto": texto, "fuente": "ia_generativa", "modelo": modelo, "prompt": prompt,
                    "coherente_con_nivel": coherente, "error": None}
        except Exception as exc:  # red, clave inválida, modelo no disponible...
            error = f"{type(exc).__name__}: {exc}"
    return {"texto": plantilla(ctx), "fuente": "plantilla", "modelo": None, "prompt": prompt,
            "coherente_con_nivel": True,
            "error": error or ("IA desactivada" if not usar_ia else "Sin API key")}
