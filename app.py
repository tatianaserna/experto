"""Interfaz Streamlit: datos utilizados -> resultado -> reglas activadas -> recomendación -> explicación."""
import json
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from experto import conocimiento as K
from experto import notificaciones, pipeline, trazabilidad, visual

SALIDAS = "salidas"
PRESETS = {
    "Mendoza, Argentina": (-32.89, -68.84),
    "Sabana de Bogotá (Funza), Colombia": (4.72, -74.21),
    "Altiplano de Boyacá (Tunja), Colombia": (5.54, -73.36),
    "Pasto (Nariño), Colombia": (1.21, -77.28),
    "Valledupar, Colombia": (10.46, -73.25),
    "Medellín, Colombia": (6.25, -75.57),
}

st.set_page_config(page_title="Riesgo de helada y estrés térmico", page_icon="🌾", layout="wide")
st.title("🌾 Sistema experto híbrido: riesgo de helada y estrés térmico")
st.caption("Datos: Open-Meteo · Decisión: motor difuso Mamdani propio · IA generativa: solo redacta la explicación")

with st.sidebar:
    st.header("Parámetros")
    nombre = st.selectbox("Ubicación", list(PRESETS) + ["Personalizada"])
    lat0, lon0 = PRESETS.get(nombre, (4.71, -74.07))
    lat = st.number_input("Latitud", -90.0, 90.0, float(lat0), 0.01, format="%.4f", key=f"lat_{nombre}")
    lon = st.number_input("Longitud", -180.0, 180.0, float(lon0), 0.01, format="%.4f", key=f"lon_{nombre}")
    fecha = st.date_input("Fecha a evaluar", value=date.today(), max_value=date.today() + timedelta(days=7))
    st.divider()
    usar_ia = st.toggle("Explicación con IA generativa", value=True)
    api_key = st.text_input("ANTHROPIC_API_KEY", type="password", value=os.getenv("ANTHROPIC_API_KEY", ""))
    modelo = st.text_input("Modelo", value=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    evaluar = st.button("Evaluar riesgo", type="primary", width="stretch")
    st.caption("Sin API key se usa una explicación de plantilla (la decisión no cambia).")

if evaluar:
    try:
        with st.spinner("Consultando la API y ejecutando el motor difuso..."):
            st.session_state["r"] = pipeline.evaluar(
                lat, lon, fecha, nombre=nombre, usar_ia=usar_ia, api_key=api_key or None,
                modelo=modelo or None, carpeta=SALIDAS)
    except Exception as exc:
        st.session_state.pop("r", None)
        st.error(f"No se pudo completar la evaluación: {exc}")

r = st.session_state.get("r")
if r is None:
    st.info("Elija una ubicación y una fecha en la barra lateral y pulse **Evaluar riesgo**.")
    st.stop()

inf, ex, notif = r["inferencia"], r["explicacion"], r["notificacion"]
if notif:
    st.error(f"🔔 **{notif['titulo']}**\n\n{notif['mensaje']}")
else:
    st.success(f"Sin notificación: el índice ({inf['resultado']:.0f}) está por debajo del umbral de alerta ({K.UMBRAL_NOTIFICACION:.0f}).")

tabs = st.tabs(["1 · Datos", "2 · Resultado", "3 · Reglas", "4 · Recomendación", "5 · Explicación", "Mapa", "Trazabilidad"])

with tabs[0]:
    e = inf["entradas_usadas"]
    c = st.columns(4)
    c[0].metric("Temp. mínima", f"{e['temp_min']} °C")
    c[1].metric("Temp. máxima", f"{e['temp_max']} °C")
    c[2].metric("Viento nocturno", f"{e['viento']} km/h")
    c[3].metric("Nubosidad nocturna", f"{e['nubosidad']:.0f} %")
    st.subheader("Transformaciones aplicadas a los datos de la API")
    st.dataframe(pd.DataFrame(r["prep"]["transformaciones"]), width="stretch", hide_index=True)
    if inf["recortes_universo"]:
        st.warning(f"Valores ajustados al universo de discurso: {inf['recortes_universo']}")
    dia = r["prep"]["horario_dia"].set_index("time")
    st.line_chart(dia[["temperature_2m"]], height=220)
    st.caption(f"Fuente: {r['consulta']['fuente']} · {r['consulta']['url']}")

with tabs[1]:
    c = st.columns(3)
    c[0].metric("Índice de riesgo", f"{inf['resultado']:.1f} / 100")
    c[1].metric("Nivel", K.NOMBRES_NIVEL[inf["nivel"]])
    c[2].metric("Tipo de riesgo", {"helada": "Helada", "calor": "Estrés por calor", "ninguno": "Ninguno"}[inf["tipo"]])
    st.progress(min(int(inf["resultado"]), 100))
    st.pyplot(visual.grafica_agregacion(inf))
    st.subheader("Grados de pertenencia (fuzzificación)")
    st.dataframe(pd.DataFrame(inf["fuzzificacion"]).T.round(3), width="stretch")
    with st.expander("Funciones de pertenencia y su justificación"):
        st.pyplot(visual.graficas_todas(inf["entradas_usadas"]))
        for v, d in K.VARIABLES.items():
            st.markdown(f"**{d['etiqueta']}** — {d['justificacion']}")

with tabs[2]:
    st.subheader(f"Reglas activadas ({len(inf['reglas_activas'])} de {len(K.REGLAS)})")
    tabla = pd.DataFrame([{"Regla": x["id"], "Condición": x["texto"], "Fuerza": round(x["fuerza"], 3),
                           "Condición limitante": x["limitante"], "Consecuente": x["consecuente"]}
                          for x in inf["reglas_activas"]])
    st.dataframe(tabla, width="stretch", hide_index=True)
    with st.expander("Base de conocimiento completa"):
        st.dataframe(pd.DataFrame([{"ID": x["id"], "Regla": K.texto_regla(x), "Tipo": x["tipo"]} for x in K.REGLAS]),
                     width="stretch", hide_index=True)

with tabs[3]:
    st.info(r["recomendacion"])
    st.caption(K.AVISO)

with tabs[4]:
    if ex["fuente"] == "ia_generativa":
        st.caption(f"Redactada por IA generativa ({ex['modelo']}) a partir del resultado del sistema experto.")
        if not ex["coherente_con_nivel"]:
            st.warning("La explicación no menciona el nivel calculado; prevalece el resultado del motor experto.")
    else:
        st.caption(f"Explicación de plantilla (IA no utilizada: {ex['error']}).")
    st.write(ex["texto"])
    with st.expander("Prompt enviado a la IA (construido solo con la salida del motor experto)"):
        st.code(ex["prompt"])

with tabs[5]:
    u = r["ubicacion"]
    st.map(pd.DataFrame([{"lat": u["lat"], "lon": u["lon"], "color": K.COLORES_NIVEL[inf["nivel"]]}]),
           latitude="lat", longitude="lon", color="color", size=4000, zoom=8)
    st.write(f"**{u['nombre']}** · lat {u['lat']:.4f}, lon {u['lon']:.4f} · elevación {u['elevacion']} m. "
             f"Las coordenadas determinan la consulta a la API y el color del punto indica el nivel de riesgo.")

with tabs[6]:
    st.code(trazabilidad.cadena(r["traza"]), language="text")
    st.json(trazabilidad.verificar(r["traza"]))
    st.download_button("Descargar traza (JSON)", json.dumps(r["traza"], ensure_ascii=False, indent=2),
                       file_name=f"traza_{r['traza']['id']}.json", mime="application/json")
    st.subheader("Historial de alertas")
    alertas = notificaciones.leer_alertas(SALIDAS)
    if alertas:
        st.dataframe(pd.DataFrame(alertas)[["momento_utc", "titulo", "riesgo", "id_traza"]],
                     width="stretch", hide_index=True)
    else:
        st.caption("Aún no hay alertas registradas.")
