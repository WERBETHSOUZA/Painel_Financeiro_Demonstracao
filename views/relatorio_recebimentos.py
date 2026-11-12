"""
views/relatorio_recebimentos.py
================================
Relatório "Recebimento por Banco": tudo que foi baixado e entrou no banco, do Mercado Interno (MI) e do Externo (ME) numa só
lista, das organizações escolhidas, com a coluna Mercado (ações 196, 953 e a baixa de ND 434; QUERY_RECEBIMENTOS.sql), por período da data do banco,
com o banco que recebeu cada baixa.
"""

import datetime

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from services.data_service import carregar_organizacoes_recebimentos, carregar_recebimentos
from utils.exporters import _FORMATO_CONTABIL, adicionar_aba_resumo_recebimentos, exportar_excel

# Larguras mínimas (com folga para o botão de filtro do cabeçalho); os identificadores ficam no formato Geral.
_LARGURAS = {"Organização": 42, "Cód. Filial": 13, "Ação": 48, "Cód_Banco": 14, "Documento": 17, "Cód. Agente": 14, "Mercado": 11, "Parcela": 10, "Valor Baixa": 16}
_COLUNAS_GERAL = ("Cód_Banco", "Documento", "Cód. Filial")

# coluna da consulta (já normalizada pelo data_service) -> título exibido
_COLUNAS = {
    "ORGANIZACAO": "Organização",
    "COD. FILIAL": "Cód. Filial",
    "ACAO": "Ação",
    "DATA BAIXA": "Data Baixa",
    "COD_BANCO": "Cód_Banco",
    "BANCO": "Banco",
    "DOCUMENTO": "Documento",
    "COD. AGENTE": "Cód. Agente",
    "NOME AGENTE": "Nome Agente",
    "MERCADO": "Mercado",
    "PARCELA": "Parcela",
    "VALOR BAIXA": "Valor Baixa",
}


def _formatar_numero(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _ajustar_aba_baixas(xlsx: bytes) -> bytes:
    """Aba BAIXAS: código do banco e documento em formato Geral (sem separador de milhar), valor em formato
    contábil e larguras que não cortam o título da coluna."""
    from io import BytesIO
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    wb = load_workbook(BytesIO(xlsx))
    ws = wb["BAIXAS"]
    for idx, cel in enumerate(ws[1], start=1):
        letra = get_column_letter(idx)
        if cel.value in _LARGURAS:
            ws.column_dimensions[letra].width = max(ws.column_dimensions[letra].width or 0, _LARGURAS[cel.value])
        if cel.value in _COLUNAS_GERAL:
            for linha in range(2, ws.max_row + 1):
                ws.cell(linha, idx).number_format = "General"
        if cel.value == "Valor Baixa":
            for linha in range(2, ws.max_row + 1):
                ws.cell(linha, idx).number_format = _FORMATO_CONTABIL
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def _periodo(dt_ini: datetime.date, dt_fim: datetime.date) -> str:
    return f"{dt_ini:%d/%m/%Y}" if dt_ini == dt_fim else f"{dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}"


def render() -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Recebimento por Banco")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="rrm_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    hoje = datetime.date.today()
    with st.sidebar:
        st.caption("Recebimento por Banco")
        orgs_df = carregar_organizacoes_recebimentos()
        rotulos = {f"{int(r.ORG)} - {r.NOME or 'Org. ' + str(int(r.ORG))}": int(r.ORG) for r in orgs_df.itertuples()} \
            if not orgs_df.empty else {"6 - DEMO AGRICOLA COMERCIO E EXPORTACAO LTDA": 6}
        orgs_sel = st.multiselect("Organização", list(rotulos), default=[], key="rrm_org",
                                  placeholder="Selecione a organização",
                                  help="Escolha uma ou mais organizações para gerar o relatório.")
        dt_ini = st.date_input("Data inicial", value=hoje.replace(day=1), format="DD/MM/YYYY", key="rrm_ini")
        dt_fim = st.date_input("Data final", value=hoje, format="DD/MM/YYYY", key="rrm_fim")
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rrm_gerar")

    if gerar:
        st.session_state["_rrm_gerou"] = True

    if not st.session_state.get("_rrm_gerou"):
        st.info("Selecione a organização e clique em **Gerar Relatório** na barra lateral para visualizar.")
        return

    if dt_ini > dt_fim:
        st.warning("A data inicial é maior que a data final.")
        return

    if not orgs_sel:
        st.info("Selecione ao menos uma organização na barra lateral.")
        return
    with st.spinner("Carregando dados..."):
        df = carregar_recebimentos(dt_ini.strftime("%d/%m/%Y"), dt_fim.strftime("%d/%m/%Y"),
                                   tuple(sorted(rotulos[o] for o in orgs_sel)))

    if df is None or df.empty:
        st.info("Nenhuma baixa no período.")
        return
    if not set(_COLUNAS).issubset(df.columns):
        st.warning("Dados incompletos para montar este relatório.")
        return

    with st.sidebar:
        mercados = st.multiselect("Mercado", ["MI", "ME"], default=[], key="rrm_mercado",
                                  placeholder="Todos os mercados", help="Vazio traz MI e ME.")
        bancos = st.multiselect("Banco", sorted(df["BANCO"].dropna().unique()), default=[], key="rrm_banco",
                                placeholder="Todos os bancos", help="Vazio traz todos os bancos.")
    if mercados:
        df = df[df["MERCADO"].isin(mercados)]
    if bancos:
        df = df[df["BANCO"].isin(bancos)]
    if df.empty:
        st.info("Nenhuma baixa com os filtros selecionados.")
        return

    colunas = dict(_COLUNAS)
    df = df[list(colunas)].rename(columns=colunas)
    df["Data Baixa"] = pd.to_datetime(df["Data Baixa"], errors="coerce")
    df["Valor Baixa"] = pd.to_numeric(df["Valor Baixa"], errors="coerce")
    # Cód_Banco e Documento como número; o documento da baixa de ND tem 20 dígitos e fica como texto
    _banco = pd.to_numeric(df["Cód_Banco"], errors="coerce")
    if _banco.notna().all():
        df["Cód_Banco"] = _banco.astype("int64")
    df["Cód. Filial"] = pd.to_numeric(df["Cód. Filial"], errors="coerce").astype("Int64")
    df["Documento"] = df["Documento"].map(lambda d: int(d) if str(d).isdigit() and len(str(d)) <= 15 else d)

    render_cards_row([
        card_html("Qtd. Baixas", str(len(df)), cor_borda="#8B5CF6"),
        card_html("Valor Total", "R$ " + _formatar_numero(df["Valor Baixa"].sum()), cor_borda="#2ECC71"),
        card_html("Bancos", str(df["Banco"].nunique()), cor_borda="#378ADD"),
    ])

    st.divider()
    st.caption(f"{len(df)} baixa(s) encontrada(s).")
    df_tela = df.copy()
    df_tela["Data Baixa"] = df_tela["Data Baixa"].dt.strftime("%d/%m/%Y")
    df_tela["Valor Baixa"] = df_tela["Valor Baixa"].apply(_formatar_numero)
    df_tela = df_tela.fillna("")
    render_tabela_html(df_tela, colunas_centralizar=["Documento", "Parcela", "Mercado"])

    arquivo = exportar_excel(
        df, "BAIXAS", colunas_moeda=("Valor Baixa",), colunas_centralizar=("Documento", "Parcela", "Mercado"),
    )
    arquivo = _ajustar_aba_baixas(arquivo)
    arquivo = adicionar_aba_resumo_recebimentos(
        arquivo, df, f"Recebimento por Banco - {_periodo(dt_ini, dt_fim)}",
        organizacoes=" | ".join(o.split(" - ", 1)[1] if " - " in o else o for o in orgs_sel),
    )
    botao_exportar_excel(
        arquivo, f"Recebimento_por_Banco_{dt_ini.strftime('%d-%m-%Y')}_a_{dt_fim.strftime('%d-%m-%Y')}.xlsx",
        key="rrm_export",
    )
