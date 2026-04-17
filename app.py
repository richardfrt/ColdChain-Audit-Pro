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
    ejecutar_ia = st.toggle("Generar informe con IA", value=True)
    btn_analizar = st.button("Ejecutar auditoría", type="primary", use_container_width=True)


st.header("Auditoría de Tratamiento en Frío")
st.caption("Resultados técnicos + informe de incidencia + PDF final.")


if btn_analizar:
    if archivo_subido is None:
        st.warning("Por favor, sube un registro de temperaturas (CSV) para comenzar")
        st.stop()

    try:
        with st.spinner("Analizando CSV..."):
            resumen = analizar_datos(archivo_subido)
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

        # Muestreo agresivo: nunca enviar más de 1.000 puntos al gráfico.
        serie_temp = df_telemetria[col_temp]
        paso = max(1, len(serie_temp) // 1000)
        serie_temp_grafico = serie_temp.iloc[::paso]
        eje_x = serie_temp_grafico.index

        if col_tiempo:
            serie_tiempo = (
                df_telemetria[col_tiempo]
                .astype(str)
                .pipe(lambda s: s.str.strip())
            )
            tiempo_parseado = pd.to_datetime(serie_tiempo, errors="coerce")
            if tiempo_parseado.notna().sum() > 0:
                df_plot = (
                    df_telemetria.assign(_tiempo=tiempo_parseado)
                    .dropna(subset=["_tiempo"])
                    .set_index("_tiempo")
                    [[col_temp]]
                )
                paso_df_plot = max(1, len(df_plot) // 1000)
                df_plot = df_plot.iloc[::paso_df_plot]
                serie_temp_grafico = df_plot[col_temp]
                eje_x = df_plot.index

        with st.container():
            if (serie_temp > 1.1).any():
                st.warning("⚠️ Se han detectado picos de temperatura por encima del límite legal")

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
                    y0=1.1,
                    y1=max(float(serie_temp_grafico.max()), 1.1),
                    fillcolor="red",
                    opacity=0.08,
                    line_width=0,
                    annotation_text="LÍMITE TRATAMIENTO FRÍO",
                    annotation_position="top left",
                )
                figura.add_hline(
                    y=1.1,
                    line_color="red",
                    line_width=2,
                    line_dash="dash",
                )
                figura.update_layout(
                    xaxis_title="Registro",
                    yaxis_title="Temperatura (°C)",
                    template="plotly_white",
                    margin=dict(l=20, r=20, t=20, b=20),
                    transition=dict(duration=0),
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
                        "Línea Crítica (1.1°C)": [1.1] * len(serie_temp_grafico),
                    }
                )

            if paso > 1:
                st.caption(
                    f"Visualización optimizada: {len(serie_temp_grafico)} puntos mostrados de {len(serie_temp)}."
                )

        st.subheader("Veredicto")
        if resumen["veredicto"] == "RECHAZADO":
            st.error("CARGAMENTO RECHAZADO")
        else:
            st.success("APTO PARA EXPORTACIÓN")

        informe_ia = ""
        if ejecutar_ia:
            with st.spinner("Consultando al agente legal (IA)..."):
                informe_ia = obtener_informe_ia(resumen)
        else:
            informe_ia = (
                "Informe IA deshabilitado por configuración. "
                "Activa 'Generar informe con IA' para incluirlo en el dossier."
            )

        st.subheader("Informe de Incidencia (IA)")
        st.write(informe_ia)

        with st.spinner("Generando PDF..."):
            nombre_pdf = generar_pdf(resumen, informe_ia)

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

