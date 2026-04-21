import streamlit as st
import pandas as pd
import numpy as np
import os
from openai import AuthenticationError, OpenAI
from fpdf import FPDF
import plotly.io as pio

try:
    import plotly.graph_objects as go
    PLOTLY_DISPONIBLE = True
except Exception:
    PLOTLY_DISPONIBLE = False

pio.kaleido.scope.default_format = "png"

AVISO_LEGAL = (
    "AVISO LEGAL: Este informe es generado por inteligencia artificial como herramienta de "
    "análisis técnico y apoyo a la toma de decisiones. No constituye un documento con validez "
    "legal vinculante ni sustituye el peritaje oficial certificado en caso de litigio judicial."
)


class ColumnDetectionError(Exception):
    def __init__(self, message, columns=None):
        super().__init__(message)
        self.columns = columns or []


def limpiar_texto_pdf(texto):
    if not texto:
        return ""
    reemplazos = {
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "•": "-",
    }
    for mal, bien in reemplazos.items():
        texto = texto.replace(mal, bien)
    return texto.encode("latin-1", "replace").decode("latin-1")


def _normalizar_etiqueta(texto):
    texto = str(texto or "").strip().lower()
    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "º": "o",
        "°": "",
        "_": " ",
        "-": " ",
    }
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    return " ".join(texto.split())


def _detectar_columnas_flexible(df):
    candidatos_temp = [
        "temp",
        "t1",
        "t2",
        "°c",
        "c°",
        "celsius",
        "valor",
        "temperatura",
        "temperature",
        "grados",
    ]
    candidatos_time = [
        "time",
        "fecha",
        "date",
        "hora",
        "timestamp",
        "momento",
        "datetime",
        "date time",
    ]
    col_temp = None
    col_time = None
    for col in df.columns:
        col_norm = _normalizar_etiqueta(col)
        if col_temp is None and any(token in col_norm for token in candidatos_temp):
            col_temp = col
        if col_time is None and any(token in col_norm for token in candidatos_time):
            col_time = col
    return col_temp, col_time


def _detectar_fila_inicio_datos_excel(archivo_subido, nrows=20):
    df_preview = pd.read_excel(archivo_subido, header=None, nrows=nrows)
    if df_preview.empty:
        return 0

    def celdas_con_contenido(fila):
        fila_str = fila.astype(str).str.strip()
        return int(((fila.notna()) & (fila_str != "") & (fila_str.str.lower() != "nan")).sum())

    densidades = [celdas_con_contenido(df_preview.iloc[i]) for i in range(len(df_preview))]
    return int(densidades.index(max(densidades)))


def _detectar_fila_cabecera_excel(archivo_subido):
    header_inicio_datos = _detectar_fila_inicio_datos_excel(archivo_subido, nrows=20)
    df_preview = pd.read_excel(archivo_subido, header=None, skiprows=header_inicio_datos, nrows=80)
    for i in range(len(df_preview)):
        fila = [_normalizar_etiqueta(v) for v in df_preview.iloc[i].tolist()]
        tiene_temp = any(
            any(t in celda for t in ["temperatura", "temperature", "temp", "celsius", "grados"])
            for celda in fila
        )
        tiene_time = any(
            any(t in celda for t in ["timestamp", "fecha", "hora", "date", "time", "datetime"])
            for celda in fila
        )
        if tiene_temp or tiene_time:
            return header_inicio_datos + i
    return header_inicio_datos


def _detectar_columna_temperatura_por_datos(df):
    mejor_col = None
    mejor_score = -1
    for col in df.columns:
        serie = pd.to_numeric(df[col], errors="coerce").dropna()
        if serie.empty:
            continue
        dentro_rango = ((serie >= -30) & (serie <= 40)).sum()
        score = int(dentro_rango)
        if score > mejor_score and dentro_rango >= max(3, int(len(serie) * 0.4)):
            mejor_col = col
            mejor_score = score
    return mejor_col


def _detectar_fila_cabecera_texto(lineas):
    palabras_clave = [
        "temp",
        "temperature",
        "temperatura",
        "grados",
        "celsius",
        "timestamp",
        "fecha",
        "hora",
        "date",
        "time",
    ]
    header_idx = 0
    for i in range(min(120, len(lineas))):
        linea_norm = _normalizar_etiqueta(lineas[i])
        if any(p in linea_norm for p in palabras_clave):
            header_idx = i
    return header_idx


def procesar_archivo_universal(archivo_subido):
    nombre_src = (
        archivo_subido if isinstance(archivo_subido, str) else getattr(archivo_subido, "name", "")
    )
    nombre = str(nombre_src).lower()
    header_idx = 0
    if nombre.endswith((".xlsx", ".xls")):
        header_idx = _detectar_fila_cabecera_excel(archivo_subido)
    else:
        if isinstance(archivo_subido, str):
            with open(archivo_subido, encoding="utf-8", errors="ignore") as fh:
                lineas = fh.read().splitlines()
        else:
            lineas = archivo_subido.getvalue().decode("utf-8", errors="ignore").splitlines()
        header_idx = _detectar_fila_cabecera_texto(lineas)

    if hasattr(archivo_subido, "seek"):
        try:
            archivo_subido.seek(0)
        except Exception:
            pass

    if nombre.endswith((".xlsx", ".xls")):
        df = pd.read_excel(archivo_subido, skiprows=header_idx, header=0)
    else:
        df = pd.read_csv(
            archivo_subido,
            skiprows=header_idx,
            header=0,
            sep=None,
            engine="python",
            encoding="utf-8",
            encoding_errors="replace",
            on_bad_lines="skip",
        )

    col_temp_detectada, col_tiempo_detectada = _detectar_columnas_flexible(df)
    nuevas_columnas = {}
    if col_temp_detectada is not None:
        nuevas_columnas[col_temp_detectada] = "Temperatura_C"
    if col_tiempo_detectada is not None:
        nuevas_columnas[col_tiempo_detectada] = "Timestamp"
    df = df.rename(columns=nuevas_columnas)

    if "Temperatura_C" not in df.columns:
        col_plan_b = _detectar_columna_temperatura_por_datos(df)
        if col_plan_b is not None:
            df = df.rename(columns={col_plan_b: "Temperatura_C"})

    if "Temperatura_C" not in df.columns:
        raise ColumnDetectionError(
            "No he podido identificar las columnas automáticamente. Por favor, asegúrate de que el Excel contenga una columna llamada Temperatura o similar.",
            columns=[str(c) for c in df.columns],
        )
    df["Temperatura_C"] = pd.to_numeric(df["Temperatura_C"], errors="coerce")
    df = df.dropna(subset=["Temperatura_C"])
    if df.empty:
        raise ValueError(
            "No quedaron filas válidas: revise que la columna de temperatura sea numérica."
        )
    return df


def cargar_datos_csv(archivo_subido):
    return procesar_archivo_universal(archivo_subido)


def resolver_columnas_telemetria(df):
    col_temp = "Temperatura_C" if "Temperatura_C" in df.columns else None
    col_tiempo = "Timestamp" if "Timestamp" in df.columns else None
    return col_temp, col_tiempo


def analizar_datos(archivo_subido, limite_temperatura=1.1):
    df = procesar_archivo_universal(archivo_subido)
    max_temp = df["Temperatura_C"].max()
    fallos = df[df["Temperatura_C"] > limite_temperatura]
    minutos_fallo = len(fallos)
    veredicto = "APTO" if minutos_fallo == 0 else "RECHAZADO"
    return {
        "total_registros": len(df),
        "max_temp": max_temp,
        "minutos_fallo": minutos_fallo,
        "veredicto": veredicto,
    }


def obtener_informe_ia(
    resumen,
    protocolo_seleccionado=None,
    organismo=None,
    limite_temperatura=1.1,
    vida_util_consumida=None,
    tipo_mercancia=None,
    indicadores_forenses=None,
    vida_util_restante=None,
    dias_restantes_exactos=None,
    dias_consumidos_exactos=None,
    nivel_riesgo=None,
):
    _notas_credenciales = (
        "Análisis de IA no disponible temporalmente por error de credenciales. "
        "Revisa st.secrets."
    )
    destino_txt = organismo or "el destino indicado"
    indicadores_forenses = indicadores_forenses or {}
    instrucciones = f"""
    Actúa como perito técnico de cadena de frío y consultor logístico.
    Debes producir un informe profesional en español con DOS secciones obligatorias.

    Datos de entrada:
    - Protocolo: {protocolo_seleccionado or 'N/D'}
    - Organismo / destino: {destino_txt}
    - Veredicto actual: {resumen['veredicto']}
    - Registros analizados: {resumen['total_registros']}
    - Minutos fuera de rango: {resumen['minutos_fallo']}
    - Temperatura máxima: {resumen['max_temp']}°C
    - Límite térmico de referencia: {limite_temperatura}°C
    - Número de picos sobre límite: {indicadores_forenses.get('num_picos', 'N/D')}
    - Duración máxima continua de rotura: {indicadores_forenses.get('duracion_max_continua_min', 'N/D')} min
    - Máximo exceso sobre el límite: {indicadores_forenses.get('max_exceso_c', 'N/D')}°C
    - Tipo de mercancía: {tipo_mercancia or 'N/D'}
    - Vida útil consumida calculada matemáticamente: {vida_util_consumida if vida_util_consumida is not None else 'N/D'}%
    - Vida útil restante calculada: {vida_util_restante if vida_util_restante is not None else 'N/D'}%
    - Días de vida útil consumidos (integración tiempo-temperatura): {dias_consumidos_exactos if dias_consumidos_exactos is not None else 'N/D'}
    - Días de vida útil restantes calculados matemáticamente: {dias_restantes_exactos if dias_restantes_exactos is not None else 'N/D'}
    - Nivel de riesgo económico y de rechazo (calculado en Python): {nivel_riesgo if nivel_riesgo is not None else 'N/D'}

    CRÍTICO: Los días de vida útil restantes calculados matemáticamente son EXACTAMENTE {dias_restantes_exactos if dias_restantes_exactos is not None else 'N/D'}.
    BAJO NINGÚN CONCEPTO alteres, estimes o inventes este número.
    Debes usar exactamente esta cifra en tu informe.
    CRÍTICO: El nivel de riesgo económico y de rechazo es ESTRICTAMENTE "{nivel_riesgo if nivel_riesgo is not None else 'N/D'}".
    NO evalúes el riesgo por tu cuenta. Tu única labor es redactar un párrafo profesional explicando este nivel de riesgo exacto a un director de logística, sin contradecirlo.

    Formato obligatorio:
    SECCIÓN 1: Auditoría Técnica
    - Análisis Forense: <explica picos, duración de rotura y severidad térmica>
    - Cumplimiento Normativo: <explica si cumple o incumple y por qué>
    - Impacto Técnico-Legal: <riesgo documental o regulatorio>

    SECCIÓN 2: Inteligencia Predictiva
    - Días estimados de vida útil restantes: <número o rango>
    - Riesgo de rechazo y económico: <usa exactamente "{nivel_riesgo if nivel_riesgo is not None else 'N/D'}">
    - Recomendación logística: <acción concreta>
    - Justificación predictiva: <máximo 2 frases>
    """
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": instrucciones}],
            temperature=0.0,
        )
        return response.choices[0].message.content
    except AuthenticationError:
        return _notas_credenciales
    except Exception:
        return _notas_credenciales


def generar_pdf(resumen, mercado, informe_ia, figura, figura_predictiva=None):
    informe_ia = limpiar_texto_pdf(informe_ia)
    if not informe_ia.strip():
        informe_ia = "No se generaron notas de IA"

    class PDFConAviso(FPDF):
        def footer(self):
            self.set_y(-16)
            self.set_font("Arial", "I", 8)
            self.set_text_color(90, 90, 90)
            self.multi_cell(0, 4, limpiar_texto_pdf(AVISO_LEGAL), align="C")

    pdf = PDFConAviso()
    pdf.add_page()
    azul_oscuro = (8, 36, 92)
    pdf.set_fill_color(*azul_oscuro)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 14, "INFORME DE AUDITORÍA COLD-CHAIN PRO", ln=True, align="C", fill=True)
    pdf.ln(6)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Resumen Técnico del Análisis", ln=True)
    pdf.ln(2)
    ancho_total = pdf.w - pdf.l_margin - pdf.r_margin
    ancho_clave = ancho_total * 0.55
    ancho_valor = ancho_total - ancho_clave
    alto_fila = 8
    pdf.set_fill_color(240, 245, 255)
    pdf.set_draw_color(180, 190, 210)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(ancho_clave, alto_fila, "Dato", border=1, fill=True)
    pdf.cell(ancho_valor, alto_fila, "Valor", border=1, ln=True, fill=True)
    pdf.set_font("Arial", "", 11)
    lim_txt = f"{float(mercado):.2f}"
    filas = [
        ("Mercado/Límite (°C)", limpiar_texto_pdf(str(mercado))),
        ("Registros analizados", str(resumen["total_registros"])),
        ("Temperatura máxima detectada (°C)", f"{resumen['max_temp']:.2f}"),
        (f"Minutos fuera de rango (> {lim_txt}°C)", str(resumen["minutos_fallo"])),
    ]
    for clave, valor in filas:
        pdf.cell(ancho_clave, alto_fila, limpiar_texto_pdf(clave), border=1)
        pdf.cell(ancho_valor, alto_fila, limpiar_texto_pdf(valor), border=1, ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(176, 0, 32) if resumen["veredicto"] == "RECHAZADO" else pdf.set_text_color(11, 110, 79)
    pdf.cell(0, 10, limpiar_texto_pdf(f"VEREDICTO FINAL: {resumen['veredicto']}"), ln=True)
    pdf.set_text_color(0, 0, 0)
    chart_path = "temp_chart.png"
    chart_predictivo_path = "predictivo_chart.png"
    try:
        if figura is not None:
            pio.write_image(figura, chart_path, engine="kaleido", width=800, height=450)
            pdf.ln(2)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "2. Gráfica de Telemetría", ln=True)
            pdf.image(chart_path, x=10, y=None, w=190)
        if figura_predictiva is not None:
            pio.write_image(figura_predictiva, chart_predictivo_path, engine="kaleido", width=800, height=360)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "3. Gráfica Predictiva de Vida Útil", ln=True)
            pdf.image(chart_predictivo_path, x=10, y=None, w=190)
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "4. Informe Integrado IA", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 5, limpiar_texto_pdf(informe_ia))
        try:
            pdf_bytes = bytes(pdf.output(dest="S"))
        except Exception:
            pdf_bytes = pdf.output(dest="S").encode("latin-1", errors="replace")
        return pdf_bytes
    finally:
        if os.path.exists(chart_path):
            os.remove(chart_path)
        if os.path.exists(chart_predictivo_path):
            os.remove(chart_predictivo_path)

PROTOCOLOS = {
    "UE - Estándar General (4.0°C)": {"limite": 4.0, "organismo": "Estándar General UE", "destino": "UE"},
    "USA - USDA T103-a-1 (1.1°C)": {"limite": 1.1, "organismo": "USDA T103-a-1", "destino": "USA"},
    "USA - USDA T103-a-2 (2.2°C)": {"limite": 2.2, "organismo": "USDA T103-a-2", "destino": "USA"},
    "China - Protocolo GACC (0.0°C)": {"limite": 0.0, "organismo": "GACC", "destino": "China"},
    "Japón - MAFF Protocol (1.1°C)": {"limite": 1.1, "organismo": "MAFF", "destino": "Japón"},
}

PARAMETROS_VIDA_UTIL = {
    "Pescado y Marisco": {"base_dias": 12, "temp_ideal": 2.0, "q10": 3.0},
    "Carne": {"base_dias": 20, "temp_ideal": 4.0, "q10": 2.5},
    "Frutas y Verduras": {"base_dias": 30, "temp_ideal": 8.0, "q10": 2.0},
    "Lácteos": {"base_dias": 25, "temp_ideal": 4.0, "q10": 2.0},
    "Farmacéutico": {"base_dias": 365, "temp_ideal": 5.0, "q10": 4.0},
}


def calcular_vida_util_restante(df, col_tiempo, col_temp, tipo_producto):
    params = PARAMETROS_VIDA_UTIL.get(tipo_producto, PARAMETROS_VIDA_UTIL["Frutas y Verduras"])
    df_calc = df.copy()
    df_calc[col_tiempo] = pd.to_datetime(df_calc[col_tiempo], errors="coerce")
    df_calc[col_temp] = pd.to_numeric(df_calc[col_temp], errors="coerce")
    df_calc = df_calc.dropna(subset=[col_tiempo, col_temp]).sort_values(by=col_tiempo)

    if len(df_calc) < 2:
        return round(float(params["base_dias"]), 2), 0.0, 0.0

    df_calc["delta_dias"] = df_calc[col_tiempo].diff().dt.total_seconds() / 86400.0
    df_calc["delta_dias"] = df_calc["delta_dias"].fillna(0).clip(lower=0)
    df_calc["multiplicador"] = np.where(
        df_calc[col_temp] > params["temp_ideal"],
        params["q10"] ** ((df_calc[col_temp] - params["temp_ideal"]) / 10.0),
        1.0,
    )

    dano_total = float((df_calc["delta_dias"] * df_calc["multiplicador"]).sum())
    dias_restantes = max(0.0, params["base_dias"] - dano_total)
    porcentaje_consumido = min((dano_total / params["base_dias"]) * 100.0, 100.0)

    return round(dias_restantes, 2), round(dano_total, 2), round(porcentaje_consumido, 2)


def calcular_nivel_riesgo(porcentaje_consumido):
    if porcentaje_consumido <= 5:
        return "Riesgo Bajo (Apto para venta normal)"
    if porcentaje_consumido <= 25:
        return "Riesgo Medio (Requiere venta prioritaria - FEFO)"
    return "Riesgo Alto (Peligro de rechazo, liquidación o merma)"


def calcular_indicadores_forenses(serie_temperaturas, limite_temperatura):
    mascara_fallo = serie_temperaturas > limite_temperatura
    num_picos = int(((mascara_fallo) & (~mascara_fallo.shift(fill_value=False))).sum())
    duracion_total_min = int(mascara_fallo.sum())

    duracion_max_continua_min = 0
    duracion_actual = 0
    for en_fallo in mascara_fallo:
        if bool(en_fallo):
            duracion_actual += 1
            duracion_max_continua_min = max(duracion_max_continua_min, duracion_actual)
        else:
            duracion_actual = 0

    exceso_max = float((serie_temperaturas - limite_temperatura).clip(lower=0).max())
    return {
        "num_picos": num_picos,
        "duracion_total_min": duracion_total_min,
        "duracion_max_continua_min": int(duracion_max_continua_min),
        "max_exceso_c": round(exceso_max, 2),
    }


def construir_informe_tecnico_local(resumen, indicadores_forenses, limite_temperatura):
    cumplimiento = (
        "Cumple el protocolo de cadena de frío."
        if resumen["veredicto"] == "APTO"
        else "Incumple el protocolo de cadena de frío."
    )
    return (
        f"Análisis forense: Se detectaron {indicadores_forenses['num_picos']} picos por encima de "
        f"{limite_temperatura:.2f}°C, con {indicadores_forenses['duracion_total_min']} min fuera de rango, "
        f"una rotura continua máxima de {indicadores_forenses['duracion_max_continua_min']} min y un exceso pico de "
        f"{indicadores_forenses['max_exceso_c']:.2f}°C sobre el límite. "
        f"Cumplimiento normativo: {cumplimiento}"
    )


def extraer_panel_predictivo(texto_ia):
    panel = {
        "dias": "No disponible",
        "riesgo": "No disponible",
        "riesgo_economico": "No disponible",
        "recomendacion": "No disponible",
    }
    if not (texto_ia or "").strip():
        return panel

    for linea in texto_ia.splitlines():
        linea_limpia = linea.strip()
        if ":" not in linea_limpia:
            continue
        etiqueta, valor = linea_limpia.split(":", 1)
        etiqueta = etiqueta.strip().lower()
        valor = valor.strip() or "No disponible"
        if "días estimados de vida útil restantes" in etiqueta:
            panel["dias"] = valor
        elif "riesgo de rechazo" in etiqueta:
            panel["riesgo"] = valor
        elif "riesgo de pérdida económica" in etiqueta:
            panel["riesgo_economico"] = valor
        elif "recomendación logística" in etiqueta or "recomendación de negocio" in etiqueta:
            panel["recomendacion"] = valor
    return panel


st.set_page_config(
    page_title="ColdChain Audit Pro | Telemetría",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');
      html, body, [class*="css"]  {
        font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
      }
      .block-container { padding-top: 1.25rem; padding-bottom: 2.5rem; max-width: min(1600px, 98vw); }
      [data-testid="stMetric"] {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 0.85rem 1rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
      }
      [data-testid="stMetric"] label { color: #64748b !important; font-weight: 600; letter-spacing: 0.02em; }
      [data-testid="stMetric"] [data-testid="stMetricValue"] { color: #0f172a !important; }
      [data-testid="stPlotlyChart"] {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
      }
      [data-testid="stDataFrame"], [data-testid="stTable"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
      }
      section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
      }
      section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] label,
      section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span {
        color: #e2e8f0 !important;
      }
      section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: #334155 !important;
        border-color: #475569 !important;
      }
      .cc-sidebar-brand {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #f8fafc !important;
        margin-bottom: 0.25rem;
      }
      /* Alertas en el área principal: bordes redondeados y lectura clara */
      section.main [data-testid="stAlert"] {
        width: 100%;
        border-radius: 14px;
        padding: 1rem 1.15rem;
        font-size: 1.02rem;
        font-weight: 600;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
      }
      .cc-hero-title { font-size: 2.15rem; font-weight: 800; color: #0f172a; letter-spacing: -0.03em; line-height: 1.15; }
      .cc-hero-sub { color: #475569; font-size: 1.05rem; margin-top: 0.5rem; font-weight: 500; max-width: 42rem; line-height: 1.5; }
      .cc-hero-badge { display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.12em; color: #0369a1; background: linear-gradient(90deg, #e0f2fe 0%, #f0f9ff 100%); padding: 0.35rem 0.75rem; border-radius: 999px; margin-bottom: 0.65rem; border: 1px solid #bae6fd; }
      .cc-panel-title { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.14em; color: #64748b; text-transform: uppercase; margin-bottom: 0.75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    # INSERTAR LOGO AQUÍ
    # Ejemplo: st.image("assets/logo.png", use_container_width=True)
    st.markdown('<p class="cc-sidebar-brand">❄️ COLDCHAIN AUDIT PRO</p>', unsafe_allow_html=True)
    st.divider()
    st.markdown("**Configuración de auditoría**")
    st.caption(
        "Panel corporativo para telemetría, informe asistido y dossier PDF."
    )
    archivo_subido = st.file_uploader(
        "Registro de temperaturas (CSV, TXT o Excel)",
        type=["csv", "txt", "xlsx", "xls"],
    )
    protocolo_seleccionado = st.selectbox("Protocolo de destino", options=list(PROTOCOLOS.keys()))
    tipo_mercancia = st.selectbox("Tipo de Mercancía", options=list(PARAMETROS_VIDA_UTIL.keys()))
    limite_temperatura = PROTOCOLOS[protocolo_seleccionado]["limite"]
    st.caption(f"Límite activo: {limite_temperatura:.2f}°C")
    ejecutar_ia = st.toggle("Generar informe con IA", value=True)
    btn_analizar = st.button("Ejecutar auditoría", type="primary", use_container_width=True)
    st.caption(
        "Aviso legal: Esta herramienta es de carácter informativo y no sustituye la inspección oficial de las autoridades fitosanitarias."
    )
    st.info(AVISO_LEGAL)


# INSERTAR LOGO AQUÍ (cabecera principal)
# st.image("assets/logo.png", width=220)

st.markdown(
    """
    <div style="margin-bottom: 0.25rem;">
      <span class="cc-hero-badge">LOGÍSTICA · COLD CHAIN · B2B</span>
    </div>
    <p class="cc-hero-title">📦 ColdChain Audit Pro</p>
    <p class="cc-hero-sub">Dashboard de telemetría, cumplimiento normativo y trazabilidad térmica para exportación.
    Un solo flujo: auditoría, veredicto y dossier PDF con soporte opcional de IA.</p>
    """,
    unsafe_allow_html=True,
)


if btn_analizar:
    if archivo_subido is None:
        st.warning("Por favor, sube un registro de temperaturas (CSV, TXT o Excel) para comenzar")
        st.stop()

    try:
        with st.spinner("Analizando registro..."):
            resumen = analizar_datos(archivo_subido, limite_temperatura)
            df_telemetria = cargar_datos_csv(archivo_subido)

        col_temp, col_tiempo = resolver_columnas_telemetria(df_telemetria)
        if not col_temp:
            st.error(
                "No se encontró una columna de temperatura compatible "
                "(ej: Temperatura_C, Temperature, temp)."
            )
            st.stop()

        serie_temp = df_telemetria[col_temp]
        max_temp_archivo = float(serie_temp.max())
        min_temp_archivo = float(serie_temp.min())
        indicadores_forenses = calcular_indicadores_forenses(serie_temp, limite_temperatura)
        informe_tecnico_local = construir_informe_tecnico_local(
            resumen, indicadores_forenses, limite_temperatura
        )
        # Sincronización de tiempo para el eje X.
        if col_tiempo:
            serie_tiempo = df_telemetria[col_tiempo].astype(str).str.strip()
            tiempo_parseado = pd.to_datetime(serie_tiempo, errors="coerce")
            if tiempo_parseado.notna().sum() > 0:
                eje_x_base = tiempo_parseado
                tiempo_para_vida = tiempo_parseado
            else:
                eje_x_base = pd.Series(range(len(serie_temp)), index=serie_temp.index)
                tiempo_para_vida = pd.Series([pd.NaT] * len(serie_temp), index=serie_temp.index)
        else:
            eje_x_base = pd.Series(range(len(serie_temp)), index=serie_temp.index)
            tiempo_para_vida = pd.Series([pd.NaT] * len(serie_temp), index=serie_temp.index)

        if col_tiempo:
            dias_restantes_exactos, dias_consumidos_exactos, vida_util_consumida = (
                calcular_vida_util_restante(df_telemetria, col_tiempo, col_temp, tipo_mercancia)
            )
        else:
            base_dias = float(PARAMETROS_VIDA_UTIL[tipo_mercancia]["base_dias"])
            dias_restantes_exactos, dias_consumidos_exactos, vida_util_consumida = (
                round(base_dias, 2),
                0.0,
                0.0,
            )
        vida_util_restante = round(max(0.0, 100.0 - vida_util_consumida), 2)
        nivel_riesgo = calcular_nivel_riesgo(vida_util_consumida)

        # Preservación de picos: dividir en bloques y tomar el máximo de cada bloque.
        total_puntos = len(serie_temp)
        block_size = max(1, (total_puntos + 999) // 1000)
        puntos_x = []
        puntos_y = []

        for inicio in range(0, total_puntos, block_size):
            fin = min(inicio + block_size, total_puntos)
            bloque_temp = serie_temp.iloc[inicio:fin]
            if bloque_temp.empty:
                continue
            idx_max = bloque_temp.idxmax()
            puntos_x.append(eje_x_base.loc[idx_max])
            puntos_y.append(float(bloque_temp.max()))

        df_grafico = pd.DataFrame(
            {
                "x": puntos_x,
                "Temperatura (°C)": puntos_y,
            }
        )
        serie_temp_grafico = df_grafico["Temperatura (°C)"]
        eje_x = df_grafico["x"]

        figura = None
        if PLOTLY_DISPONIBLE:
            figura = go.Figure()
            figura.add_trace(
                go.Scattergl(
                    x=eje_x,
                    y=serie_temp_grafico,
                    mode="lines",
                    name="Temperatura (°C)",
                    line=dict(color="#38bdf8", width=2.2),
                )
            )
            figura.add_hrect(
                y0=limite_temperatura,
                y1=max(float(serie_temp_grafico.max()), limite_temperatura),
                fillcolor="#ef4444",
                opacity=0.12,
                line_width=0,
                annotation_text="LÍMITE TRATAMIENTO FRÍO",
                annotation_position="top left",
            )
            figura.add_hline(
                y=limite_temperatura,
                line_color="#fb7185",
                line_width=2,
                line_dash="dash",
            )
            y_min = min(float(serie_temp_grafico.min()), limite_temperatura)
            y_max = max(max_temp_archivo, limite_temperatura)
            margen = max(0.05, (y_max - y_min) * 0.08)
            figura.update_layout(
                template="plotly_dark",
                xaxis_title="Registro",
                yaxis_title="Temperatura (°C)",
                margin=dict(l=20, r=20, t=36, b=20),
                transition=dict(duration=0),
                yaxis=dict(range=[y_min - margen, y_max + margen]),
            )

        figura_predictiva = None
        if PLOTLY_DISPONIBLE:
            figura_predictiva = go.Figure()
            figura_predictiva.add_trace(
                go.Bar(
                    x=["Vida consumida", "Vida restante"],
                    y=[vida_util_consumida, vida_util_restante],
                    marker_color=["#ef4444", "#22c55e"],
                )
            )
            figura_predictiva.update_layout(
                template="plotly_white",
                yaxis_title="Porcentaje (%)",
                margin=dict(l=20, r=20, t=30, b=20),
                yaxis=dict(range=[0, 100]),
            )

        informe_ia = ""
        if ejecutar_ia:
            with st.spinner("Consultando al agente legal (IA)..."):
                informe_ia = obtener_informe_ia(
                    resumen,
                    protocolo_seleccionado,
                    PROTOCOLOS[protocolo_seleccionado]["organismo"],
                    limite_temperatura,
                    vida_util_consumida,
                    tipo_mercancia,
                    indicadores_forenses,
                    vida_util_restante,
                    dias_restantes_exactos,
                    dias_consumidos_exactos,
                    nivel_riesgo,
                )
        else:
            informe_ia = (
                "Informe IA deshabilitado por configuración. "
                "Activa 'Generar informe con IA' para incluirlo en el dossier."
            )
        notas_ia = informe_ia
        panel_predictivo = extraer_panel_predictivo(informe_ia)
        fig = figura

        col_grafica, col_datos = st.columns([7, 3])

        with col_grafica:
            if (serie_temp > limite_temperatura).any():
                st.warning("⚠️ Se han detectado picos de temperatura por encima del límite legal")
                st.markdown(
                    "<h3 style='color:#d00000;'>⚠️ ALERTA: INCUMPLIMIENTO DE PROTOCOLO DETECTADO EN GRÁFICA</h3>",
                    unsafe_allow_html=True,
                )

            st.subheader("Análisis de Telemetría: Curva de Temperatura")
            if PLOTLY_DISPONIBLE and figura is not None:
                st.plotly_chart(
                    figura,
                    use_container_width=True,
                    config={"displaylogo": False, "staticPlot": False},
                )
            else:
                st.line_chart(
                    {
                        "Temperatura (°C)": serie_temp_grafico,
                        f"Línea Crítica ({limite_temperatura:.1f}°C)": [limite_temperatura] * len(serie_temp_grafico),
                    }
                )

            if block_size > 1:
                st.caption(
                    f"Visualización optimizada con preservación de picos: {len(serie_temp_grafico)} puntos mostrados de {len(serie_temp)}."
                )

        with col_datos:
            st.markdown('<p class="cc-panel-title">Panel de control</p>', unsafe_allow_html=True)
            st.metric("Temp. Máx (°C)", f"{resumen['max_temp']:.2f}")
            st.metric("Temp. Mín (°C)", f"{min_temp_archivo:.2f}")
            st.metric("Fallos (min)", str(resumen["minutos_fallo"]))
            st.caption(f"Registros analizados: **{resumen['total_registros']:,}**".replace(",", "."))
            st.markdown("### Veredicto")
            if resumen["veredicto"] == "RECHAZADO":
                st.error(
                    "**RECHAZADO** — El cargamento no cumple el límite térmico del protocolo seleccionado."
                )
            else:
                st.success(
                    "**APTO** — El cargamento cumple el límite térmico del protocolo seleccionado."
                )
            st.markdown("##### Notas de la IA")
            st.info(informe_ia)

        st.markdown("### Informe Técnico (Peritaje)")
        st.info(informe_tecnico_local)

        st.markdown("### Panel Predictivo")
        p1, p2, p3, p4, p5 = st.columns(5)
        with p1:
            st.metric("Vida útil consumida", f"{vida_util_consumida:.2f}%")
        with p2:
            st.metric("Vida útil restante", f"{vida_util_restante:.2f}%")
        with p3:
            st.metric(
                "Días restantes exactos",
                f"{dias_restantes_exactos} días",
            )
        with p4:
            st.metric("Riesgo de rechazo", nivel_riesgo)
        with p5:
            st.metric("Riesgo económico", nivel_riesgo)

        st.markdown(
            f"**Recomendación de negocio:** {panel_predictivo['recomendacion']}"
        )

        if ejecutar_ia and not (notas_ia or "").strip():
            st.warning(
                "La IA aún no terminó de procesar. Espera unos segundos antes de descargar el PDF."
            )
            st.stop()
        nombre_pdf = "Dossier_Fitosanitario_Final.pdf"
        st.success("PDF listo para descargar.")

        st.download_button(
            "Descargar Dossier (PDF)",
            data=generar_pdf(resumen, limite_temperatura, notas_ia, fig, figura_predictiva),
            file_name=nombre_pdf,
            mime="application/pdf",
            use_container_width=True,
        )
    except ColumnDetectionError as e:
        st.error(
            "No he podido identificar las columnas automáticamente. Por favor, asegúrate de que el Excel contenga una columna llamada Temperatura o similar."
        )
        if e.columns:
            st.info(f"Columnas detectadas en el archivo: {', '.join(e.columns)}")
    except Exception as e:
        st.exception(e)
