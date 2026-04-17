import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import os
from datetime import datetime
import streamlit as st
from openai import OpenAI

# Esta es la línea segura que debes poner en lugar de la que tiene tu clave 'sk-'
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# ==========================================
# 1. CONFIGURACIÓN - PEGA TU CLAVE AQUÍ
# =====================================

def analizar_datos(archivo_csv):
    # Soporta tanto una ruta de archivo como un archivo subido desde Streamlit.
    if hasattr(archivo_csv, "seek"):
        archivo_csv.seek(0)
    df = pd.read_csv(archivo_csv)
    max_temp = df['Temperatura_C'].max()
    fallos = df[df['Temperatura_C'] > 1.1]
    minutos_fallo = len(fallos)
    veredicto = "APTO" if minutos_fallo == 0 else "RECHAZADO"
    
    return {
        "total_registros": len(df),
        "max_temp": max_temp,
        "minutos_fallo": minutos_fallo,
        "veredicto": veredicto
    }

def obtener_informe_ia(resumen):
    print("Consultando al experto legal de OpenAI...")
    instrucciones = f"""
    Eres un consultor experto en exportaciones. 
    Analiza estos datos de un contenedor hacia Japón:
    - Veredicto: {resumen['veredicto']}
    - Minutos fuera de rango: {resumen['minutos_fallo']}
    - Temperatura máxima: {resumen['max_temp']}°C
    
    Redacta un informe técnico breve y profesional explicando si se cumple el protocolo 
    de tratamiento en frío (límite 1.1°C) y qué debe hacer la cooperativa.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": instrucciones}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error con la IA: {e}"

def generar_pdf(resumen, informe_ia):
    pdf = FPDF()
    pdf.add_page()

    # Encabezado corporativo
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    azul_oscuro = (8, 36, 92)
    pdf.set_draw_color(*azul_oscuro)
    pdf.set_text_color(*azul_oscuro)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, "CERTIFICADO DE AUDITORÍA DE CADENA DE FRÍO", ln=True, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, f"Empresa: ColdChain Audit Pro    Fecha: {fecha_actual}", ln=True, align="C")
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
        ("Minutos de Fallo (> 1.1°C)", str(resumen["minutos_fallo"])),
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

    # Pie de página
    pdf.set_y(-15)
    pdf.set_text_color(90, 90, 90)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(
        0,
        5,
        "Documento generado automáticamente por sistema de auditoría basado en IA. V 2.0",
        ln=True,
        align="C",
    )

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