import streamlit as st
from pathlib import Path


def aplicar_configuracoes():
    st.set_page_config(
        page_title="Painel Financeiro | Demonstração",
        layout="wide",
        page_icon="💰",
        initial_sidebar_state="expanded"
    )
    css_path = Path(__file__).parent.parent / "assets" / "styles.css"
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
