import streamlit as st

from sistema_final import analizar_datos, obtener_informe_ia, generar_pdf


ARCHIVO_CSV = "datos_sensor.csv"


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
    archivo = st.text_input("Archivo CSV", value=ARCHIVO_CSV)
    ejecutar_ia = st.toggle("Generar informe con IA", value=True)
    btn_analizar = st.button("Ejecutar auditoría", type="primary", use_container_width=True)


st.header("Auditoría de Tratamiento en Frío")
st.caption("Resultados técnicos + informe de incidencia + PDF final.")


if btn_analizar:
    try:
        with st.spinner("Analizando CSV..."):
            resumen = analizar_datos(archivo)

        c1, c2, c3 = st.columns(3)
        c1.metric("Registros", f"{resumen['total_registros']:,}".replace(",", "."))
        c2.metric("Temperatura Máxima (°C)", f"{resumen['max_temp']:.2f}")
        c3.metric("Fallos (min)", str(resumen["minutos_fallo"]))

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

