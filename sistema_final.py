import os

import pandas as pd
from openai import AuthenticationError, OpenAI
from fpdf import FPDF
import plotly.io as pio

pio.kaleido.scope.default_format = "png"

AVISO_LEGAL = (
    "AVISO LEGAL: Este informe es generado por inteligencia artificial como herramienta de "
    "análisis técnico y apoyo a la toma de decisiones. No constituye un documento con validez "
    "legal vinculante ni sustituye el peritaje oficial certificado en caso de litigio judicial."
)


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
        "temperatura",
        "temperature",
        "temp",
        "celsius",
        "grados",
        "c",
    ]
    candidatos_time = [
        "timestamp",
        "fecha hora",
        "fecha",
        "hora",
        "date time",
        "datetime",
        "date",
        "time",
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


def _detectar_fila_cabecera_excel(archivo_subido):
    df_preview = pd.read_excel(archivo_subido, header=None, nrows=80)
    for i in range(len(df_preview)):
        fila = [_normalizar_etiqueta(v) for v in df_preview.iloc[i].tolist()]
        tiene_temp = any(
            any(t in celda for t in ["temperatura", "temperature", "temp", "celsius", "grados", " c "])
            for celda in fila
        )
        tiene_time = any(
            any(t in celda for t in ["timestamp", "fecha", "hora", "date", "time", "datetime"])
            for celda in fila
        )
        if tiene_temp or tiene_time:
            return i
    return 0


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
        raise ValueError("No se encontró la columna de temperatura.")

    df["Temperatura_C"] = pd.to_numeric(df["Temperatura_C"], errors="coerce")
    df = df.dropna(subset=["Temperatura_C"])

    if df.empty:
        raise ValueError(
            "No quedaron filas válidas: revise que la columna de temperatura sea numérica."
        )

    return df


def cargar_datos_csv(archivo_subido):
    """Alias usado por la app: misma ingesta que el motor universal."""
    return procesar_archivo_universal(archivo_subido)


def resolver_columnas_telemetria(df):
    """Devuelve nombres de columnas canónicas si existen en el DataFrame."""
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
):
    import streamlit as st

    _notas_credenciales = (
        "Análisis de IA no disponible temporalmente por error de credenciales. "
        "Revisa st.secrets."
    )

    print("Consultando al experto legal de OpenAI...")
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

    Formato obligatorio:
    SECCIÓN 1: Auditoría Técnica
    - Análisis Forense: <explica picos, duración de rotura y severidad térmica>
    - Cumplimiento Normativo: <explica si cumple o incumple y por qué>
    - Impacto Técnico-Legal: <riesgo documental o regulatorio>

    SECCIÓN 2: Inteligencia Predictiva
    - Días estimados de vida útil restantes: <número o rango>
    - Riesgo de rechazo: <Bajo|Medio|Alto>
    - Riesgo de pérdida económica: <Bajo|Medio|Alto>
    - Recomendación logística: <acción concreta>
    - Justificación predictiva: <máximo 2 frases>
    """
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": instrucciones}],
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

    # Encabezado profesional (azul oscuro)
    azul_oscuro = (8, 36, 92)
    pdf.set_fill_color(*azul_oscuro)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 14, "INFORME DE AUDITORÍA COLD-CHAIN PRO", ln=True, align="C", fill=True)
    pdf.ln(6)

    # Sección 1: Datos técnicos en tabla
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Resumen Técnico del Análisis", ln=True)
    pdf.ln(2)

    # Tabla (clave/valor)
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
        ("Registros analizados", str(resumen["total_registros"])),
        ("Temperatura máxima detectada (°C)", f"{resumen['max_temp']:.2f}"),
        (f"Minutos fuera de rango (> {lim_txt}°C)", str(resumen["minutos_fallo"])),
    ]
    filas.insert(0, ("Mercado/Límite (°C)", limpiar_texto_pdf(str(mercado))))
    for clave, valor in filas:
        pdf.cell(ancho_clave, alto_fila, limpiar_texto_pdf(clave), border=1)
        pdf.cell(ancho_valor, alto_fila, limpiar_texto_pdf(valor), border=1, ln=True)

    # Veredicto destacado
    pdf.ln(5)
    pdf.set_font("Arial", "B", 13)
    if resumen["veredicto"] == "RECHAZADO":
        pdf.set_text_color(176, 0, 32)
    else:
        pdf.set_text_color(11, 110, 79)
    pdf.cell(0, 10, limpiar_texto_pdf(f"VEREDICTO FINAL: {resumen['veredicto']}"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

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
            pio.write_image(
                figura_predictiva,
                chart_predictivo_path,
                engine="kaleido",
                width=800,
                height=360,
            )
            pdf.ln(3)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "3. Gráfica Predictiva de Vida Útil", ln=True)
            pdf.image(chart_predictivo_path, x=10, y=None, w=190)

        # Informe IA completo de doble sección
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "4. Informe Integrado IA", ln=True)
        pdf.set_font("Arial", "", 10)
        informe_limpio = limpiar_texto_pdf(informe_ia)
        seccion_1 = "SECCION 1: AUDITORIA TECNICA"
        seccion_2 = "SECCION 2: INTELIGENCIA PREDICTIVA"
        texto_upper = informe_limpio.upper()

        idx_s1 = texto_upper.find(seccion_1)
        idx_s2 = texto_upper.find(seccion_2)

        if idx_s1 >= 0 and idx_s2 > idx_s1:
            bloque_1 = informe_limpio[idx_s1:idx_s2].strip()
            bloque_2 = informe_limpio[idx_s2:].strip()
            pdf.set_font("Arial", "B", 11)
            pdf.multi_cell(0, 6, "SECCIÓN 1: Auditoría Técnica")
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 5, limpiar_texto_pdf(bloque_1.replace("SECCIÓN 1: Auditoría Técnica", "").strip()))
            pdf.ln(2)
            pdf.set_font("Arial", "B", 11)
            pdf.multi_cell(0, 6, "SECCIÓN 2: Inteligencia Predictiva")
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 5, limpiar_texto_pdf(bloque_2.replace("SECCIÓN 2: Inteligencia Predictiva", "").strip()))
        else:
            pdf.multi_cell(0, 5, informe_limpio)

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


def generar_informe_pdf(resumen, mercado, fig):
    return generar_pdf(resumen, mercado, "Informe generado sin notas adicionales de IA.", fig)


def main():
    print("Iniciando Proceso de Auditoría...")
    archivo = "datos_sensor.csv"

    if not os.path.exists(archivo):
        print(f"Error: No encuentro el archivo {archivo}")
        return

    resumen = analizar_datos(archivo)
    informe_ia = obtener_informe_ia(resumen)
    pdf_data = generar_pdf(resumen, 1.1, informe_ia, None)
    with open("Dossier_Fitosanitario_Final.pdf", "wb") as fh:
        fh.write(pdf_data)

    print("\n¡ÉXITO!")
    print("Archivo generado: Dossier_Fitosanitario_Final.pdf")


if __name__ == "__main__":
    main()
