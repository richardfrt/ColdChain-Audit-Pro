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
    limite_temperatura = PROTOCOLOS[protocolo_seleccionado]["limite"]
    st.caption(f"Límite activo: {limite_temperatura:.2f}°C")
    ejecutar_ia = st.toggle("Generar informe con IA", value=True)
    btn_analizar = st.button("Ejecutar auditoría", type="primary", use_container_width=True)
    st.caption(
        "Aviso legal: Esta herramienta es de carácter informativo y no sustituye la inspección oficial de las autoridades fitosanitarias."
    )


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
