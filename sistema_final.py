import os

import pandas as pd
from openai import OpenAI
from fpdf import FPDF

# ==========================================
# 1. CONFIGURACIÓN - PEGA TU CLAVE AQUÍ
# ==========================================
TU_API_KEY = "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"
client = OpenAI(api_key=TU_API_KEY)

# --- Motor de ingesta universal ---
_CABECERA_KEYWORDS = ("temp", "time", "fecha", "date", "timestamp")
_SUBS_TEMP = ("temp", "grados", "celsius")
_SUBS_TIEMPO = ("time", "fecha", "date", "timestamp")


def _archivo_nombre(archivo_subido):
    if isinstance(archivo_subido, str):
        return archivo_subido
    return getattr(archivo_subido, "name", "") or ""


def _stream_rewind(archivo_subido):
    if hasattr(archivo_subido, "seek"):
        try:
            archivo_subido.seek(0)
        except Exception:
            pass


def _fila_parece_cabecera(row) -> bool:
    partes = []
    for v in row:
        if pd.isna(v):
            continue
        partes.append(str(v).strip().lower())
    texto = " ".join(partes)
    return any(kw in texto for kw in _CABECERA_KEYWORDS)


def _indice_fila_cabecera(peek_df: pd.DataFrame) -> int:
    n = min(50, len(peek_df))
    for i in range(n):
        if _fila_parece_cabecera(peek_df.iloc[i].values):
            return i
    return 0


def _read_csv_flexible(archivo_subido, **kwargs):
    kwargs.setdefault("encoding_errors", "replace")
    kwargs.setdefault("engine", "python")
    kwargs.setdefault("sep", None)
    return pd.read_csv(archivo_subido, **kwargs)


def procesar_archivo_universal(archivo_subido):
    """
    Lee CSV/TXT/XLS/XLSX, detecta la fila de cabecera entre metadatos,
    normaliza columnas Temperatura_C y Timestamp y devuelve solo esas columnas
    (temperatura numérica, filas con NaN en temperatura eliminadas).
    """
    _stream_rewind(archivo_subido)
    nombre = _archivo_nombre(archivo_subido)
    ext = os.path.splitext(nombre)[1].lower()

    if ext in (".xlsx", ".xls"):
        peek = pd.read_excel(archivo_subido, header=None, nrows=50)
        header_row = _indice_fila_cabecera(peek)
        _stream_rewind(archivo_subido)
        df = pd.read_excel(archivo_subido, header=header_row)
    elif ext in (".csv", ".txt") or ext == "":
        peek = _read_csv_flexible(archivo_subido, header=None, nrows=50)
        header_row = _indice_fila_cabecera(peek)
        _stream_rewind(archivo_subido)
        df = _read_csv_flexible(archivo_subido, header=header_row)
    else:
        raise ValueError(
            f"Formato no soportado ({ext or 'sin extensión'}). Use .csv, .txt, .xlsx o .xls."
        )

    def primera_columna_por_substrings(columnas, substrings):
        for col in columnas:
            base = str(col).lower()
            for s in substrings:
                if s in base:
                    return col
        return None

    col_temp_orig = primera_columna_por_substrings(df.columns, _SUBS_TEMP)
    cols_sin_temp = [c for c in df.columns if c != col_temp_orig]
    col_tiempo_orig = primera_columna_por_substrings(cols_sin_temp, _SUBS_TIEMPO)

    if col_temp_orig is None:
        raise ValueError(
            "No se encontró columna de temperatura reconocible "
            "(busque 'temp', 'grados' o 'celsius' en la cabecera)."
        )

    rename = {col_temp_orig: "Temperatura_C"}
    if col_tiempo_orig is not None:
        rename[col_tiempo_orig] = "Timestamp"

    df = df.rename(columns=rename)
    columnas_finales = ["Temperatura_C"]
    if "Timestamp" in df.columns:
        columnas_finales.append("Timestamp")
    df = df[columnas_finales].copy()

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
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": instrucciones}],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error con la IA: {e}"


def generar_pdf(
    resumen,
    informe_ia,
    destino=None,
    protocolo=None,
    limite_temperatura=1.1,
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
