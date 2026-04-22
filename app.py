import streamlit as st

st.set_page_config(
    page_title="Buscadores",
    page_icon="🔎",
    layout="centered",
)

st.title("🔎 Buscadores")
st.markdown(
    """
    Usa el menú de la izquierda para navegar:

    - **💼 Empleo** — Busca ofertas de trabajo en Infojobs, Indeed, SEPE y Tecnoempleo
    - **📋 Oposiciones** — Busca convocatorias en el BOE y el Portal de Empleo Público

    ---
    Tus palabras clave se guardan automáticamente en **este dispositivo**.
    Cada persona puede tener las suyas propias desde su móvil o navegador.
    """
)
