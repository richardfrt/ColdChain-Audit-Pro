import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    PLOTLY_DISPONIBLE = True
except Exception:
    PLOTLY_DISPONIBLE = False

from sistema_final import (
    analizar_datos,
    obtener_informe_ia,
    generar_pdf,
    cargar_datos_csv,
    resolver_columnas_telemetria,
)

PROTOCOLOS = {
    "UE - Estándar General (4.0°C)": {"limite": 4.0, "organismo": "Estándar General UE", "destino": "UE"},
    "USA - USDA T103-a-1 (1.1°C)": {"limite": 1.1, "organismo": "USDA T103-a-1", "destino": "USA"},
    "USA - USDA T103-a-2 (2.2°C)": {"limite": 2.2, "organismo": "USDA T103-a-2", "destino": "USA"},
    "China - Protocolo GACC (0.0°C)": {"limite": 0.0, "organismo": "GACC", "destino": "China"},
    "Japón - MAFF Protocol (1.1°C)": {"limite": 1.1, "organismo": "MAFF", "destino": "Japón"},
}


st.set_page_config(
    page_title="Cold-Chain Auditoría",
    page_icon="🧊",
    layout="wide",
)


with st.sidebar:
    st.title("Configuración de Auditoría")
    st.write(
        "Bienvenido al panel de auditoría Cold-Chain. "
        "Aquí podrás analizar el registro de temperaturas, generar el informe legal con IA "
        "y construir el dossier fitosanitario en PDF para el lote."
    )
    archivo_subido = st.file_uploader(
        "Registro de temperaturas (CSV)",
        type=["csv"],
    )
    protocolo_seleccionado = st.selectbox("Protocolo de destino", options=list(PROTOCOLOS.keys()))
    limite_temperatura = PROTOCOLOS[protocolo_seleccionado]["limite"]
    st.caption(f"Límite activo: {limite_temperatura:.2f}°C")
    ejecutar_ia = st.toggle("Generar informe con IA", value=True)
    btn_analizar = st.button("Ejecutar auditoría", type="primary", use_container_width=True)
    st.caption(
        "Aviso legal: Esta herramienta es de carácter informativo y no sustituye la inspección oficial de las autoridades fitosanitarias."
    )


st.header("Auditoría de Tratamiento en Frío")
st.caption("Resultados técnicos + informe de incidencia + PDF final.")


if btn_analizar:
    if archivo_subido is None:
        st.warning("Por favor, sube un registro de temperaturas (CSV) para comenzar")
        st.stop()

    try:
        with st.spinner("Analizando CSV..."):
            resumen = analizar_datos(archivo_subido, limite_temperatura)
            df_telemetria = cargar_datos_csv(archivo_subido)

        c1, c2, c3 = st.columns(3)
        c1.metric("Registros", f"{resumen['total_registros']:,}".replace(",", "."))
        c2.metric("Temperatura Máxima (°C)", f"{resumen['max_temp']:.2f}")
        c3.metric("Fallos (min)", str(resumen["minutos_fallo"]))

        col_temp, col_tiempo = resolver_columnas_telemetria(df_telemetria)
        if not col_temp:
            st.error(
                "No se encontró una columna de temperatura compatible "
                "(ej: Temperatura_C, Temperature, temp)."
            )
            st.stop()

        serie_temp = df_telemetria[col_temp]
        max_temp_archivo = float(serie_temp.max())

        # Sincronización de tiempo para el eje X.
        if col_tiempo:
            serie_tiempo = df_telemetria[col_tiempo].astype(str).str.strip()
            tiempo_parseado = pd.to_datetime(serie_tiempo, errors="coerce")
            if tiempo_parseado.notna().sum() > 0:
                eje_x_base = tiempo_parseado
            else:
                eje_x_base = pd.Series(range(len(serie_temp)), index=serie_temp.index)
        else:
            eje_x_base = pd.Series(range(len(serie_temp)), index=serie_temp.index)

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

        with st.container():
            if (serie_temp > limite_temperatura).any():
                st.warning("⚠️ Se han detectado picos de temperatura por encima del límite legal")
                st.markdown(
                    "<h3 style='color:#d00000;'>⚠️ ALERTA: INCUMPLIMIENTO DE PROTOCOLO DETECTADO EN GRÁFICA</h3>",
                    unsafe_allow_html=True,
                )

            st.subheader("Análisis de Telemetría: Curva de Temperatura")
            if PLOTLY_DISPONIBLE:
                figura = go.Figure()
                figura.add_trace(
                    go.Scattergl(
                        x=eje_x,
                        y=serie_temp_grafico,
                        mode="lines",
                        name="Temperatura (°C)",
                        line=dict(color="#1f77b4", width=2),
                    )
                )
                figura.add_hrect(
                    y0=limite_temperatura,
                    y1=max(float(serie_temp_grafico.max()), limite_temperatura),
                    fillcolor="red",
                    opacity=0.08,
                    line_width=0,
                    annotation_text="LÍMITE TRATAMIENTO FRÍO",
                    annotation_position="top left",
                )
                figura.add_hline(
                    y=limite_temperatura,
                    line_color="red",
                    line_width=2,
                    line_dash="dash",
                )
                y_min = min(float(serie_temp_grafico.min()), limite_temperatura)
                y_max = max(max_temp_archivo, limite_temperatura)
                margen = max(0.05, (y_max - y_min) * 0.08)
                figura.update_layout(
                    xaxis_title="Registro",
                    yaxis_title="Temperatura (°C)",
                    template="plotly_white",
                    margin=dict(l=20, r=20, t=20, b=20),
                    transition=dict(duration=0),
                    yaxis=dict(range=[y_min - margen, y_max + margen]),
                )
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

        st.subheader("Veredicto")
        if resumen["veredicto"] == "RECHAZADO":
            st.error("CARGAMENTO RECHAZADO")
        else:
            st.success("APTO PARA EXPORTACIÓN")

        informe_ia = ""
        if ejecutar_ia:
            with st.spinner("Consultando al agente legal (IA)..."):
                informe_ia = obtener_informe_ia(
                    resumen,
                    protocolo_seleccionado,
                    PROTOCOLOS[protocolo_seleccionado]["organismo"],
                    limite_temperatura,
                )
        else:
            informe_ia = (
                "Informe IA deshabilitado por configuración. "
                "Activa 'Generar informe con IA' para incluirlo en el dossier."
            )

        st.subheader("Informe de Incidencia (IA)")
        st.write(informe_ia)

        with st.spinner("Generando PDF..."):
            nombre_pdf = generar_pdf(
                resumen,
                informe_ia,
                destino=PROTOCOLOS[protocolo_seleccionado]["destino"],
                protocolo=protocolo_seleccionado,
                limite_temperatura=limite_temperatura,
            )

        st.success(f"PDF generado: {nombre_pdf}")
        with open(nombre_pdf, "rb") as f:
            st.download_button(
                "Descargar Dossier (PDF)",
                data=f.read(),
                file_name=nombre_pdf,
                mime="application/pdf",
                use_container_width=True,
            )
    except Exception as e:
        st.exception(e)

