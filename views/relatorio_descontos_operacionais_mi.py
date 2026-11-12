"""
views/relatorio_descontos_operacionais_mi.py
=============================================
Relatório "Descontos Realizados": descontos já REALIZADOS (ação 948) do Mercado Interno e do Externo (coluna Mercado),
de todos os tipos (contratual, operacional e concedidos; QUERY_DESCONTOS_OPERACIONAIS_MI.sql), por período de prorrogação. Os descontos a realizar ficam em Contas a Receber (Descontos Contratuais Pendentes MI).
"""

import datetime

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from services.data_service import carregar_descontos_operacionais_mi
from utils.exporters import _FORMATO_CONTABIL, exportar_excel

# coluna da consulta (já normalizada pelo data_service) -> título exibido
_COLUNAS = {
    "COD. AGENTE": "Cód. Agente",
    "NOME AGENTE": "Nome Agente",
    "MERCADO": "Mercado",
    "PARCELA": "Parcela",
    "DATA": "Data",
    "DOCUMENTO": "NF",
    "VALOR MOVIMENTO": "Valor Movimento",
    "CLASSE LANCAMENTO (DESCONTO)": "Classe Lançamento (Desconto)",
    "COMPLEMENTO": "Observação",
    "DATA INCLUSAO": "Data Inclusão",
    "USUARIO INCLUSAO": "Usuário Inclusão",
}
# Larguras do Excel (iguais à planilha de referência).
_LARGURAS = {
    "Cód. Agente": 11.9, "Nome Agente": 40.1, "Mercado": 11, "Parcela": 7.4, "Data": 11.3, "NF": 14.1,
    "Valor Movimento": 16.7, "Classe Lançamento (Desconto)": 77.9, "Data Inclusão": 19, "Usuário Inclusão": 28, "Observação": 92.3,
}


_TIPOS = ["Contratual", "Operacional", "Concedidos"]


def _formatar_numero(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _ajustar_larguras(xlsx: bytes) -> bytes:
    from io import BytesIO
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    wb = load_workbook(BytesIO(xlsx))
    ws = wb.active
    for idx, cel in enumerate(ws[1], start=1):
        if cel.value in _LARGURAS:
            ws.column_dimensions[get_column_letter(idx)].width = _LARGURAS[cel.value]
        if cel.value == "NF":          # número em formato geral, sem separador de milhar
            for linha in range(2, ws.max_row + 1):
                ws.cell(linha, idx).number_format = "General"
        if cel.value == "Data Inclusão":
            for linha in range(2, ws.max_row + 1):
                ws.cell(linha, idx).number_format = "dd/mm/yyyy hh:mm:ss"
        if cel.value == "Valor Movimento":
            for linha in range(2, ws.max_row + 1):
                ws.cell(linha, idx).number_format = _FORMATO_CONTABIL
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def render() -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Descontos Realizados")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="rdo_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    hoje = datetime.date.today()
    with st.sidebar:
        st.caption("Descontos Realizados")
        dt_ini = st.date_input("Data inicial", value=hoje.replace(month=1, day=1), format="DD/MM/YYYY", key="rdo_ini")
        dt_fim = st.date_input("Data final", value=hoje, format="DD/MM/YYYY", key="rdo_fim")
        tipos = st.multiselect("Tipo", _TIPOS, default=[], key="rdo_tipo", placeholder="Todos os tipos",
                               help="Vazio traz todos os descontos. Escolha um ou mais tipos para filtrar.")
        mercados = st.multiselect("Mercado", ["MI", "ME"], default=[], key="rdo_mercado", placeholder="Todos os mercados",
                                  help="Vazio traz MI e ME.")
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rdo_gerar")

    if gerar:
        st.session_state["_rdo_gerou"] = True

    if not st.session_state.get("_rdo_gerou"):
        st.info("Clique em **Gerar Relatório** na barra lateral para visualizar.")
        return

    if dt_ini > dt_fim:
        st.warning("A data inicial é maior que a data final.")
        return

    with st.spinner("Carregando dados..."):
        df = carregar_descontos_operacionais_mi(dt_ini.strftime("%d/%m/%Y"), dt_fim.strftime("%d/%m/%Y"))

    if df is None or df.empty:
        st.info("Nenhum desconto no período.")
        return
    if not set(_COLUNAS).issubset(df.columns):
        st.warning("Dados incompletos para montar este relatório.")
        return

    if tipos and "TIPO" in df.columns:
        df = df[df["TIPO"].isin([t.upper() for t in tipos])]
        if df.empty:
            st.info("Nenhum desconto do tipo selecionado no período.")
            return
    if mercados:
        df = df[df["MERCADO"].isin(mercados)]
        if df.empty:
            st.info("Nenhum desconto do mercado selecionado no período.")
            return
    df = df[list(_COLUNAS)].rename(columns=_COLUNAS)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Data Inclusão"] = pd.to_datetime(df["Data Inclusão"], errors="coerce")
    df["Valor Movimento"] = pd.to_numeric(df["Valor Movimento"], errors="coerce")
    # NF como número (a consulta devolve o documento como texto); se algum documento não for numérico, mantém o texto
    _nf = pd.to_numeric(df["NF"], errors="coerce")
    if _nf.notna().all():
        df["NF"] = _nf.astype("int64")

    render_cards_row([
        card_html("Qtd. Movimentos", str(len(df)), cor_borda="#8B5CF6"),
        card_html("Valor Total", "R$ " + _formatar_numero(df["Valor Movimento"].sum()), cor_borda="#E24B4A"),
        card_html("Qtd. Notas", str(df["NF"].nunique()), cor_borda="#378ADD"),
    ])

    st.divider()
    st.caption(f"{len(df)} movimento(s) encontrado(s).")

    df_tela = df.copy()
    df_tela["Data"] = df_tela["Data"].dt.strftime("%d/%m/%Y")
    df_tela["Data Inclusão"] = df_tela["Data Inclusão"].dt.strftime("%d/%m/%Y %H:%M:%S").fillna("")
    df_tela["Valor Movimento"] = df_tela["Valor Movimento"].apply(_formatar_numero)
    # a classe pode vir com várias linhas (uma por classe): na tela ficam separadas por " | "
    df_tela["Classe Lançamento (Desconto)"] = (
        df_tela["Classe Lançamento (Desconto)"].fillna("").astype(str).str.replace("\n", " | ", regex=False)
    )
    df_tela["Observação"] = df_tela["Observação"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    render_tabela_html(df_tela, colunas_centralizar=["NF", "Mercado"])

    arquivo = exportar_excel(
        df, "DESCONTOS_OPERACIONAIS_MI",
        colunas_moeda=("Valor Movimento",), colunas_centralizar=("NF", "Mercado"),
    )
    arquivo = _ajustar_larguras(arquivo)
    botao_exportar_excel(
        arquivo, f"Descontos_Realizados_{dt_ini.strftime('%d-%m-%Y')}_a_{dt_fim.strftime('%d-%m-%Y')}.xlsx",
        key="rdo_export",
    )
