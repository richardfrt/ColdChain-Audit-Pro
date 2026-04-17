import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import os
import io
from datetime import datetime
import streamlit as st
from openai import OpenAI

# Esta es la línea segura que debes poner en lugar de la que tiene tu clave 'sk-'
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# ==========================================
# 1. CONFIGURACIÓN - PEGA TU CLAVE AQUÍ
# =====================================

def _obtener_csv_bytes(archivo_csv):
    if isinstance(archivo_csv, (str, os.PathLike)):
        with open(archivo_csv, "rb") as f:
            return f.read()
    if hasattr(archivo_csv, "getvalue"):
        return archivo_csv.getvalue()
    if hasattr(archivo_csv, "seek"):
        archivo_csv.seek(0)
    if hasattr(archivo_csv, "read"):
        return archivo_csv.read()
    raise TypeError("Formato de archivo CSV no soportado.")


@st.cache_data(show_spinner=False)
def _leer_dataframe_desde_bytes(csv_bytes):
    return pd.read_csv(io.BytesIO(csv_bytes), sep=None, engine="python", encoding="utf-8")


def _normalizar_nombre_columna(nombre_columna):
    return str(nombre_columna).strip().lower().replace(" ", "_")


def resolver_columnas_telemetria(df):
    columnas = list(df.columns)
    normalizadas = {col: _normalizar_nombre_columna(col) for col in columnas}

    candidatos_temp = (
        "temperatura_c",
        "temperatura",
        "temperature",
        "temp_c",
        "temp",
    )
    candidatos_tiempo = (
        "timestamp",
        "time",
        "fecha_hora",
        "fecha",
        "datetime",
        "hora",
    )

    col_temp = None
    for col_original, col_norm in normalizadas.items():
        if any(token in col_norm for token in candidatos_temp):
            col_temp = col_original
            break

    col_tiempo = None
    for col_original, col_norm in normalizadas.items():
        if any(token in col_norm for token in candidatos_tiempo):
            col_tiempo = col_original
            break

    return col_temp, col_tiempo


@st.cache_data(show_spinner=False)
def _analizar_resumen_desde_bytes(csv_bytes, limite_temperatura=1.1):
    df = _leer_dataframe_desde_bytes(csv_bytes)

    # Normalización flexible de columnas para ser agnóstico al sensor.
    col_temp = None
    col_tiempo = None
    for col in df.columns:
        col_norm = str(col).strip().lower()
        if col_temp is None and any(k in col_norm for k in ("temp", "grados", "celsius", "temperature")):
            col_temp = col
        if col_tiempo is None and any(k in col_norm for k in ("time", "fecha", "hora", "timestamp")):
            col_tiempo = col
        if col_temp and col_tiempo:
            break

    renombres = {}
    if col_temp and col_temp != "Temperatura_C":
        renombres[col_temp] = "Temperatura_C"
    if col_tiempo and col_tiempo != "Timestamp":
        renombres[col_tiempo] = "Timestamp"
    if renombres:
        df = df.rename(columns=renombres)

    if "Temperatura_C" not in df.columns:
        raise ValueError(
            "No se encontró ninguna columna que parezca temperatura "
            "(temp/grados/celsius/temperature)."
        )

    max_temp = df["Temperatura_C"].max()
    fallos = df[df["Temperatura_C"] > limite_temperatura]
    minutos_fallo = len(fallos)
    veredicto = "APTO" if minutos_fallo == 0 else "RECHAZADO"

    return {
        "total_registros": len(df),
        "max_temp": max_temp,
        "minutos_fallo": minutos_fallo,
        "veredicto": veredicto,
        "limite_temperatura": limite_temperatura,
    }


def cargar_datos_csv(archivo_csv):
    csv_bytes = _obtener_csv_bytes(archivo_csv)
    return _leer_dataframe_desde_bytes(csv_bytes)


def analizar_datos(archivo_csv, limite_temperatura=1.1):
    csv_bytes = _obtener_csv_bytes(archivo_csv)
    return _analizar_resumen_desde_bytes(csv_bytes, limite_temperatura)

def obtener_informe_ia(
    resumen,
    pais="Japón (MAFF)",
    organismo="MAFF",
    limite_temperatura=1.1,
):
    print("Consultando al experto legal de OpenAI...")
    margen_limite = float(limite_temperatura) - float(resumen["max_temp"])
    instrucciones = f"""
    Actúa como un inspector de {pais} bajo la normativa {organismo}.
    Analiza estos datos de un contenedor:
    - Veredicto: {resumen['veredicto']}
    - Minutos fuera de rango: {resumen['minutos_fallo']}
    - Temperatura máxima: {resumen['max_temp']}°C
    - Límite normativo: {limite_temperatura}°C
    - Proximidad al límite: {margen_limite:.2f}°C
    
    Redacta un informe técnico breve y profesional explicando si se cumple el protocolo 
    de tratamiento en frío (límite {limite_temperatura}°C) y qué debe hacer la cooperativa.
    Evalúa explícitamente la "Proximidad al Límite". Si la temperatura máxima está a menos de
    0.2°C del límite, incluye literalmente esta advertencia:
    "RIESGO ELEVADO: La temperatura se mantuvo muy cerca del límite crítico".
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": instrucciones}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error con la IA: {e}"

def generar_pdf(resumen, informe_ia, destino="UE", protocolo="UE - Estándar General (4.0°C)", limite_temperatura=1.1):
    class PDFConDisclaimer(FPDF):
        def __init__(self, destino_pdf, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.destino_pdf = destino_pdf

        def footer(self):
            self.set_y(-25)
            self.set_text_color(110, 110, 110)
            self.set_font("Arial", "I", 8)
            disclaimer_base = (
                "AVISO LEGAL: Este documento es un análisis automatizado basado en datos de telemetría "
                "y tiene carácter exclusivamente informativo. No constituye un certificado oficial de "
                "exportación ni sustituye la inspección obligatoria de las autoridades fitosanitarias "
                "competentes (USDA, GACC, MAFF, etc.). El usuario es responsable de verificar la "
                "integridad de la carga."
            )
            if self.destino_pdf in ("USA", "China"):
                disclaimer_base = (
                    "NOTA DE ALTA PRIORIDAD: Este informe se rige por protocolos de exportación críticos. "
                    + disclaimer_base
                )
            self.multi_cell(0, 3.4, disclaimer_base, align="J")

    pdf = PDFConDisclaimer(destino)
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.add_page()

    # Encabezado corporativo
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    azul_oscuro = (8, 36, 92)
    pdf.set_draw_color(*azul_oscuro)
    pdf.set_text_color(*azul_oscuro)
    titulo_certificado = "CERTIFICADO DE AUDITORÍA DE CADENA DE FRÍO"
    if destino == "USA":
        titulo_certificado = "CERTIFICADO DE CUMPLIMIENTO USDA-APHIS"
    elif destino == "UE":
        titulo_certificado = "AUDITORÍA DE CALIDAD ALIMENTARIA UE"
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, titulo_certificado, ln=True, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, f"Empresa: ColdChain Audit Pro    Fecha: {fecha_actual}", ln=True, align="C")
    pdf.cell(0, 7, f"Protocolo aplicado: {protocolo} (Límite {limite_temperatura:.2f}°C)", ln=True, align="C")
    pdf.ln(4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    # Resumen técnico estructurado
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 9, "RESUMEN TÉCNICO", ln=True)

    ancho_total = pdf.w - pdf.l_margin - pdf.r_margin
    ancho_clave = ancho_total * 0.62
    ancho_valor = ancho_total - ancho_clave
    alto_fila = 9

    pdf.set_fill_color(240, 245, 255)
    pdf.set_draw_color(130, 145, 180)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(ancho_clave, alto_fila, "Parámetro", border=1, fill=True)
    pdf.cell(ancho_valor, alto_fila, "Valor", border=1, ln=True, fill=True)

    pdf.set_font("Arial", "", 11)
    filas = [
        ("Total de registros", str(resumen["total_registros"])),
        ("Temperatura Máxima (°C)", f"{resumen['max_temp']:.2f}"),
        (f"Minutos de Fallo (> {limite_temperatura:.2f}°C)", str(resumen["minutos_fallo"])),
    ]
    for clave, valor in filas:
        pdf.cell(ancho_clave, alto_fila, clave, border=1)
        pdf.cell(ancho_valor, alto_fila, valor, border=1, ln=True)

    # Veredicto destacado con borde grueso
    pdf.ln(8)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "VEREDICTO FINAL", ln=True)
    pdf.set_line_width(1.2)
    if resumen["veredicto"] == "RECHAZADO":
        pdf.set_text_color(176, 0, 32)
    else:
        pdf.set_text_color(11, 110, 79)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 14, resumen["veredicto"], border=1, ln=True, align="C")
    pdf.set_line_width(0.2)
    pdf.set_text_color(0, 0, 0)

    # Informe IA en bloque corporativo
    pdf.ln(8)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 9, "ANÁLISIS LEGAL Y DE INCIDENCIAS", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, informe_ia, align="J")

    nombre_archivo = "Dossier_Fitosanitario_Final.pdf"
    pdf.output(nombre_archivo)
    return nombre_archivo

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