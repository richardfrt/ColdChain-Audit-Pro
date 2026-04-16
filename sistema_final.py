import pandas as pd
from openai import OpenAI
from fpdf import FPDF
import os
import streamlit as st
from openai import OpenAI

# Esta es la línea segura que debes poner en lugar de la que tiene tu clave 'sk-'
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# ==========================================
# 1. CONFIGURACIÓN - PEGA TU CLAVE AQUÍ
# =====================================

def analizar_datos(archivo_csv):
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
    x0 = pdf.l_margin
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
    filas = [
        ("Registros analizados", str(resumen["total_registros"])),
        ("Temperatura máxima detectada (°C)", f"{resumen['max_temp']:.2f}"),
        ("Minutos fuera de rango (> 1.1°C)", str(resumen["minutos_fallo"])),
    ]
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
    
    # Informe IA
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. Informe de Incidencia (IA)", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, informe_ia)
    
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