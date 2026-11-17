import streamlit as st
from pathlib import Path


def aplicar_configuracoes():
    st.set_page_config(
        page_title="BI Financeiro - Demo",
        layout="wide",
        page_icon=str(Path(__file__).parent.parent / "assets" / "demo_icone.png"),   # esfera da logo, legível no tamanho da aba
        initial_sidebar_state="expanded"
    )
    css_path = Path(__file__).parent.parent / "assets" / "styles.css"
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
