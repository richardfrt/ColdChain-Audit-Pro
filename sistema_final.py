import os

import pandas as pd
from openai import AuthenticationError, OpenAI
from fpdf import FPDF
import plotly.io as pio

def procesar_archivo_universal(archivo_subido):
    nombre_src = (
        archivo_subido if isinstance(archivo_subido, str) else getattr(archivo_subido, "name", "")
    )
    nombre = str(nombre_src).lower()
    header_idx = 0

    if nombre.endswith((".xlsx", ".xls")):
        df_raw = pd.read_excel(archivo_subido, header=None, nrows=50)
        for i in range(len(df_raw)):
            fila = df_raw.iloc[i].astype(str).str.lower()
            if fila.str.contains(
                r"temp|grados|celsius|time|fecha|date|timestamp", regex=True, na=False
            ).any():
                header_idx = i
                break
    else:
        if isinstance(archivo_subido, str):
            with open(archivo_subido, encoding="utf-8", errors="ignore") as fh:
                lineas = fh.read().splitlines()
        else:
            lineas = archivo_subido.getvalue().decode("utf-8", errors="ignore").splitlines()
        palabras_clave = [
            "temp",
            "grados",
            "celsius",
            "time",
            "fecha",
            "date",
            "timestamp",
        ]
        for i in range(min(100, len(lineas))):
            linea_lower = lineas[i].lower()
            if any(palabra in linea_lower for palabra in palabras_clave):
                header_idx = i
        # La última coincidencia suele ser la cabecera tabular (evita metadatos tipo "Create Time:").

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

    nuevas_columnas = {}
    for col in df.columns:
        col_str = str(col).lower()
        if "temp" in col_str or "grados" in col_str or "celsius" in col_str:
            if "Temperatura_C" not in nuevas_columnas.values():
                nuevas_columnas[col] = "Temperatura_C"
        elif "time" in col_str or "fecha" in col_str or "date" in col_str or "timestamp" in col_str:
            if "Timestamp" not in nuevas_columnas.values():
                nuevas_columnas[col] = "Timestamp"

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
):
    import streamlit as st

    _notas_credenciales = (
        "Análisis de IA no disponible temporalmente por error de credenciales. "
        "Revisa st.secrets."
    )

    print("Consultando al experto legal de OpenAI...")
    destino_txt = organismo or "el destino indicado"
    instrucciones = f"""
    Eres un consultor experto en exportaciones.
    Analiza estos datos de un contenedor (protocolo: {protocolo_seleccionado or 'N/D'}, organismo: {destino_txt}):
    - Veredicto: {resumen['veredicto']}
    - Minutos fuera de rango: {resumen['minutos_fallo']}
    - Temperatura máxima: {resumen['max_temp']}°C
    - Límite térmico de referencia: {limite_temperatura}°C

    Redacta un informe técnico breve y profesional explicando si se cumple el protocolo
    de tratamiento en frío y qué debe hacer la cooperativa.
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


def generar_pdf(
    resumen,
    informe_ia,
    destino=None,
    protocolo=None,
    limite_temperatura=1.1,
    fig=None,
):
    pdf = FPDF()
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
    lim_txt = f"{limite_temperatura:.2f}"
    filas = [
        ("Registros analizados", str(resumen["total_registros"])),
        ("Temperatura máxima detectada (°C)", f"{resumen['max_temp']:.2f}"),
        (f"Minutos fuera de rango (> {lim_txt}°C)", str(resumen["minutos_fallo"])),
    ]
    if protocolo:
        filas.insert(0, ("Protocolo", str(protocolo)))
    if destino:
        filas.insert(0, ("Destino", str(destino)))
    for clave, valor in filas:
        pdf.cell(ancho_clave, alto_fila, clave, border=1)
        pdf.cell(ancho_valor, alto_fila, valor, border=1, ln=True)

    # Veredicto destacado
    pdf.ln(5)
    pdf.set_font("Arial", "B", 13)
    if resumen["veredicto"] == "RECHAZADO":
        pdf.set_text_color(176, 0, 32)
    else:
        pdf.set_text_color(11, 110, 79)
    pdf.cell(0, 10, f"VEREDICTO FINAL: {resumen['veredicto']}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    chart_path = "temp_chart.png"
    try:
        if fig is not None:
            pio.kaleido.scope.default_format = "png"
            fig.write_image(chart_path, engine="kaleido")
            pdf.ln(2)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "2. Gráfica de Telemetría", ln=True)
            pdf.image(chart_path, x=10, y=None, w=190)
    except Exception:
        pass

    # Informe IA
    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "3. Informe de Incidencia (IA)", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, informe_ia)

    nombre_archivo = "Dossier_Fitosanitario_Final.pdf"
    pdf.output(nombre_archivo)

    if os.path.exists(chart_path):
        os.remove(chart_path)

    return nombre_archivo


def generar_informe_pdf(resumen, mercado, fig):
    return generar_pdf(
        resumen,
        informe_ia="Informe generado sin notas adicionales de IA.",
        limite_temperatura=mercado,
        fig=fig,
    )


def main():
    print("Iniciando Proceso de Auditoría...")
    archivo = "datos_sensor.csv"

    if not os.path.exists(archivo):
        print(f"Error: No encuentro el archivo {archivo}")
        return

    resumen = analizar_datos(archivo)
    informe_ia = obtener_informe_ia(resumen)
    pdf_final = generar_pdf(resumen, informe_ia)

    print(f"\n¡ÉXITO!")
    print(f"Archivo generado: {pdf_final}")


if __name__ == "__main__":
    main()
