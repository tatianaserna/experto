"""Gráficas (Matplotlib) y mapa (Folium)."""
import matplotlib.pyplot as plt
import numpy as np

from . import conocimiento as K
from .motor import membresia


def _dibujar(ax, definicion, titulo, valor=None):
    lo, hi = definicion["universo"]
    x = np.linspace(lo, hi, 600)
    for nombre, d in definicion["conjuntos"].items():
        ax.plot(x, membresia(x, d), lw=2, label=nombre)
    if valor is not None:
        ax.axvline(valor, color="k", ls="--", lw=1.2, label=f"valor = {valor:g}")
    ax.set_title(titulo, fontsize=10)
    ax.set_ylim(-0.02, 1.08)
    ax.set_ylabel("pertenencia")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper right")


def grafica_variable(nombre, valor=None):
    fig, ax = plt.subplots(figsize=(6, 3))
    _dibujar(ax, K.VARIABLES[nombre], K.VARIABLES[nombre]["etiqueta"], valor)
    fig.tight_layout()
    return fig


def graficas_todas(entradas=None):
    """Las 4 variables de entrada y la de salida en una sola figura."""
    entradas = entradas or {}
    fig, axs = plt.subplots(2, 3, figsize=(16, 7))
    for ax, nombre in zip(axs.flat, K.VARIABLES):
        _dibujar(ax, K.VARIABLES[nombre], K.VARIABLES[nombre]["etiqueta"], entradas.get(nombre))
    _dibujar(axs.flat[4], K.SALIDA, K.SALIDA["etiqueta"])
    axs.flat[5].axis("off")
    fig.tight_layout()
    return fig


def grafica_agregacion(inf):
    x, agg = inf["_curva"]["x"], inf["_curva"]["agg"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for nombre, d in K.SALIDA["conjuntos"].items():
        ax.plot(x, membresia(x, d), color="lightgray", lw=1.2)
        ax.text(float(np.clip(np.mean(d[1][1:3]) if d[0] == "trap" else d[1][1], 3, 97)), 1.03, nombre, ha="center", fontsize=8, color="gray")
    for r in inf["reglas_activas"]:
        recorte = np.minimum(r["fuerza"], membresia(x, K.SALIDA["conjuntos"][r["consecuente"]]))
        ax.fill_between(x, recorte, alpha=0.25, label=f"{r['id']} → {r['consecuente']} ({r['fuerza']:.2f})")
    ax.plot(x, agg, "k", lw=2, label="agregación")
    ax.axvline(inf["resultado"], color="red", ls="--", label=f"centroide = {inf['resultado']:.1f}")
    ax.axvline(K.UMBRAL_NOTIFICACION, color="purple", ls=":", label=f"umbral de alerta = {K.UMBRAL_NOTIFICACION:g}")
    ax.set_ylim(0, 1.12)
    ax.set_xlabel(K.SALIDA["etiqueta"])
    ax.legend(fontsize=7, loc="upper left", ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def mapa_folium(puntos):
    """puntos: lista de dicts con nombre, lat, lon, elevacion, riesgo, nivel, tipo."""
    import folium
    centro = [float(np.mean([p["lat"] for p in puntos])), float(np.mean([p["lon"] for p in puntos]))]
    m = folium.Map(location=centro, zoom_start=2 if len(puntos) > 1 else 8, tiles="OpenStreetMap")
    for p in puntos:
        folium.CircleMarker(
            [p["lat"], p["lon"]], radius=11, color="black", weight=1, fill=True,
            fill_color=K.COLORES_NIVEL[p["nivel"]], fill_opacity=0.9,
            tooltip=f"{p['nombre']}: {p['riesgo']:.0f}/100 ({K.NOMBRES_NIVEL[p['nivel']]})",
            popup=folium.Popup(f"<b>{p['nombre']}</b><br>Elevación: {p.get('elevacion')} m<br>"
                               f"Riesgo: {p['riesgo']:.1f}/100<br>Tipo: {p['tipo']}", max_width=260),
        ).add_to(m)
    return m
