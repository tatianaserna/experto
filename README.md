# Sistema experto híbrido: riesgo de helada y estrés térmico en cultivos

## Problema
Un productor necesita saber, para un lote y una fecha, si existe **riesgo de helada** o de **estrés por calor**.
El sistema consulta datos meteorológicos reales, los interpreta con **lógica difusa** y **reglas SI-ENTONCES**, y entrega
un índice de riesgo (0-100), su nivel (bajo, moderado, alto, crítico), el tipo de riesgo, una recomendación, una
explicación en lenguaje natural y una notificación cuando el riesgo es alto.

## Arquitectura
```
Open-Meteo (API) -> datos.py (preparación) -> motor.py (fuzzificación -> reglas -> agregación -> centroide)
      -> conocimiento.py (recomendación) -> ia.py (explicación con Claude) -> notificaciones.py -> trazabilidad.py
                                     \-> app.py (Streamlit)  /  notebook .ipynb
```
| Módulo | Función |
|---|---|
| `experto/conocimiento.py` | Variables, conjuntos difusos, 13 reglas, recomendaciones, umbral de alerta |
| `experto/datos.py` | Consumo de Open-Meteo y transformación (mín/máx del día, viento y nubosidad nocturnos) |
| `experto/motor.py` | Motor Mamdani propio con NumPy (mínimo, máximo, centroide) |
| `experto/ia.py` | IA generativa (API de Anthropic): solo redacta la explicación; si falla usa una plantilla |
| `experto/notificaciones.py` | Alerta en la interfaz + archivo `salidas/alertas.jsonl` y `alertas.txt` |
| `experto/trazabilidad.py` | Traza JSON por ejecución y verificación (reproduce la inferencia) |
| `experto/pipeline.py` | Orquesta todo el flujo |
| `app.py` | Interfaz Streamlit |

## API utilizada
**Open-Meteo** (sin clave): `api.open-meteo.com` (pronóstico) y `archive-api.open-meteo.com` (histórico ERA5).
Variables horarias: `temperature_2m`, `cloud_cover`, `wind_speed_10m` (además de humedad relativa y punto de rocío).

## Ejecución
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."     # opcional; sin clave se usa la explicación de plantilla
streamlit run app.py                       # interfaz
jupyter notebook sistema_experto_agricola.ipynb   # notebook con desarrollo y pruebas
```
Salidas generadas en `salidas/`: `trazas/traza_<id>.json`, `trazas.jsonl`, `alertas.jsonl`, `alertas.txt`.

### Ejecución en GitHub
- **Codespaces:** botón verde *Code → Codespaces → Create codespace*. Se instalan las dependencias solas; luego `streamlit run app.py`.
- **Streamlit Community Cloud:** en share.streamlit.io elegir este repositorio y `app.py`. Para la IA, agregar en *Secrets*: `ANTHROPIC_API_KEY = "..."`.

## Evidencias
Ejecute el notebook completo (incluye 4 casos de prueba con datos de la API) y agregue aquí capturas de la interfaz.

## Limitaciones
- Los datos son un modelo de rejilla (pronóstico/reanálisis de ~10-25 km): pueden suavizar heladas locales en valles.
- Los rangos difusos son generales; deben ajustarse al cultivo y a su etapa fenológica.
- La recomendación es orientativa y no reemplaza la asesoría de un agrónomo.
