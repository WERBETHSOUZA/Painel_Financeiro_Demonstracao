"""
views/relatorio_contas_receber_mi.py
=====================================
Relatório "Contas a Receber - MI": títulos do Mercado Interno pagos, vencidos e a vencer, com a data do pagamento, o
valor pago, o desconto e a baixa de adiantamento (carregar_contas_receber_com_pagos). O período de Vencimento é
obrigatório e é o único que vai ao banco: só os títulos desse período são buscados. O status é pelo vencimento
(PAGO quando o saldo está zerado). Os cards só contam títulos, sem valor.
"""

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from config.pdd import COR_PDD_TEXTO, classificar_vencidos
from services.data_service import carregar_contas_receber_com_pagos
from utils.exporters import exportar_excel
from utils.prazos import calcular_dias_prazo, formatar_dias_unificado_html
from views.relatorio_contas_receber import _com_grupo, _formatar_numero, _SEM_GRUPO

# Colunas mostradas na tela — um resumo legível.
_COLUNAS_TELA = {
    "CLIENTE":         "Cliente",
    "NF":              "NF",
    "PARCELA":         "Parcela",
    "VALOR_FATURADO":  "Valor Faturado",
    "VALOR_PARCELA":   "Valor Parcela",
    "LIQUIDO_FIN":     "Líquido Financeiro",
    "VALOR_PAGO":      "Valor Pago",
    "DESCONTO":        "Desconto",
    "BAIXA_ADIANT":    "Baixa Adiant",
    "SALDO_EM_ABERTO": "Saldo em Aberto",
    "DATA_PAGAMENTO":  "Data Pagamento",
    "ENTRADA":         "Entrada",
    "VENCIMENTO":      "Vencimento",
    "PRORROGADO":      "Prorrogado",
    "DIAS_VENCIDO":    "Dias Vencto.",
    "SITUACAO":        "Situação Vencto.",
    "CLASSIF_VENCIDO": "Classif. Vencto.",
}

# Colunas do Excel, na ordem pedida (Valor Parcela entra depois do Líquido Financeiro: o Valor Faturado é o total da NF).
_COLUNAS_EXCEL = {
    "ENTRADA":         "Entrada",
    "VENCIMENTO":      "Vencimento",
    "PRORROGADO":      "Prorrogado",
    "DIAS":            "Dias Vencto.",
    "SITUACAO":        "Situação Vencto.",
    "CLASSIF_VENCIDO": "Classif. Vencto.",
    "CLASSIFICACAO":   "Classificação",
    "COD_CLIENTE":     "Cód. Cliente",
    "CLIENTE":         "Cliente",
    "PARCELA":         "Parcela",
    "TIPO_DOC":        "Tipo Doc.",
    "NF":              "NF",
    "VALOR_FATURADO":  "Valor Faturado",
    "TIPO_REGRA":      "Tipo Regra",
    "PERC_REGRA":      "% Regra",
    "DESC_APLIC_NF":   "Desc. Aplic. NF",
    "LIQUIDO_FIN":     "Líquido Financeiro",
    "VALOR_PARCELA":   "Valor Parcela",
    "ACRESCIMOS":      "Acréscimos",
    "DESCONTO":        "Desconto",
    "BAIXA_ADIANT":    "Baixa Adiant",
    "SALDO_EM_ABERTO": "Saldo em Aberto",
    "VALOR_PAGO":      "Valor Pago",
    "DATA_PAGAMENTO":  "Data Pagamento",
    "COMPLEMENTO":     "Complemento",
    "FAIXA_DIAS":      "Faixa de Dias",
}

_COLUNAS_MOEDA = (
    "Valor Faturado", "Desc. Aplic. NF", "Líquido Financeiro", "Valor Parcela", "Acréscimos", "Desconto",
    "Baixa Adiant", "Saldo em Aberto", "Valor Pago",
)


def render(df_grupo_agentes: pd.DataFrame = None, df_grupo_geral: pd.DataFrame = None) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Contas a Receber - MI")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        # Callback: com st.rerun no meio da página os filtros da barra lateral seriam esquecidos
        st.button("🔄 Atualizar", key="rcmi_atualizar", use_container_width=True, on_click=st.cache_data.clear)

    grupos_disponiveis = []
    if (df_grupo_geral is not None and not df_grupo_geral.empty and "NOME_GRUPO" in df_grupo_geral.columns):
        grupos_disponiveis = sorted(df_grupo_geral["NOME_GRUPO"].dropna().unique())

    # ── Filtros na barra lateral: o período é obrigatório e só ele vai ao banco ─────────────────────────────────
    with st.sidebar:
        st.caption("Contas a Receber - MI")
        vencimento = st.date_input(
            "Vencimento (período)", value=(), format="DD/MM/YYYY", key="rcmi_vencimento",
            help="Obrigatório. Só os títulos com vencimento neste período são buscados no banco.",
        )
        status_sel = st.multiselect("Status", ["VENCIDO", "A VENCER", "PAGO"], key="rcmi_status")
        grupo_sel = st.multiselect("Grupo", grupos_disponiveis, key="rcmi_grupo")
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rcmi_gerar")

    if gerar:
        if isinstance(vencimento, (tuple, list)) and len(vencimento) == 2:
            st.session_state["_rcmi_periodo"] = (vencimento[0], vencimento[1])
        else:
            st.session_state.pop("_rcmi_periodo", None)
            st.warning("Selecione o período de vencimento (data inicial e final) na barra lateral e clique em Gerar Relatório.")
            return

    periodo_sel = st.session_state.get("_rcmi_periodo")
    if not periodo_sel:
        st.info(
            "Escolha o **período de vencimento** na barra lateral e clique em **Gerar Relatório**. "
            "Só esse período é buscado no banco. Mercado Interno: títulos pagos, vencidos e a vencer. "
            "O status é pelo vencimento."
        )
        return
    data_de, data_ate = periodo_sel

    with st.spinner("Carregando títulos pagos e em aberto do período..."):
        df_base = carregar_contas_receber_com_pagos(data_de, data_ate)
    if df_base.empty:
        st.info("Nenhum título encontrado para o período selecionado.")
        return
    df_base = _com_grupo(df_base, df_grupo_agentes, df_grupo_geral)
    df_base = classificar_vencidos(df_base)    # CLASSIF_VENCIDO: VENCIDO ou PDD nos vencidos
    st.caption(f"Vencimento de {data_de:%d/%m/%Y} a {data_ate:%d/%m/%Y}")

    def _qtd_sit(sit: str) -> int:
        return int((df_base["SITUACAO"] == sit).sum())

    render_cards_row([
        card_html("Qtd. A Vencer — MI", str(_qtd_sit("A VENCER")), cor_borda="#22c55e"),
        card_html("Qtd. Vencidos — MI", str(_qtd_sit("VENCIDO")), cor_borda="#E24B4A"),
        card_html("Qtd. Pagos — MI", str(_qtd_sit("PAGO")), cor_borda="#4fa3e0"),
        card_html("Qtd. Total — MI", str(len(df_base)), cor_borda="#6366F1"),
    ])

    st.divider()

    df_filtrado = df_base.copy()
    if status_sel:
        df_filtrado = df_filtrado[df_filtrado["SITUACAO"].isin(status_sel)]
    if grupo_sel:
        df_filtrado = df_filtrado[df_filtrado["GRUPO"].isin(grupo_sel)]

    if df_filtrado.empty:
        st.info("Nenhum título encontrado para os filtros selecionados.")
        return

    st.caption(f"{len(df_filtrado)} título(s) encontrado(s).")

    # ── Tabela (resumo legível) ────────────────────────────────────────────────
    df_filtrado = calcular_dias_prazo(df_filtrado)
    colunas_tela = [c for c in _COLUNAS_TELA if c in df_filtrado.columns]
    df_tela = df_filtrado[colunas_tela].copy()

    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO", "DATA_PAGAMENTO"):
        if col in df_tela.columns:
            df_tela[col] = pd.to_datetime(df_tela[col], errors="coerce").dt.strftime("%d/%m/%y").fillna("")
    for col in ("VALOR_FATURADO", "VALOR_PARCELA", "LIQUIDO_FIN", "VALOR_PAGO", "DESCONTO", "BAIXA_ADIANT", "SALDO_EM_ABERTO"):
        if col in df_tela.columns:
            df_tela[col] = df_tela[col].apply(_formatar_numero)
    if "DIAS_VENCIDO" in df_tela.columns and "SITUACAO" in df_tela.columns:
        df_tela["DIAS_VENCIDO"] = df_tela.apply(formatar_dias_unificado_html, axis=1)

    if "CLASSIF_VENCIDO" in df_tela.columns:
        df_tela["CLASSIF_VENCIDO"] = df_tela["CLASSIF_VENCIDO"].map(
            lambda v: f'<span style="color:{COR_PDD_TEXTO};font-weight:700">PDD</span>' if v == "PDD"
            else ('<span style="color:#E24B4A;font-weight:700">VENCIDO</span>' if v == "VENCIDO" else ""))
    render_tabela_html(df_tela, colunas_renomear=_COLUNAS_TELA, coluna_situacao="SITUACAO",
                       colunas_centralizar=["CLASSIF_VENCIDO"])

    st.markdown("&nbsp;", unsafe_allow_html=True)

    # ── Excel: valores/datas reais ────────────────────────────────────────────
    colunas_excel = [c for c in _COLUNAS_EXCEL if c in df_filtrado.columns]
    df_excel = df_filtrado[colunas_excel].rename(columns=_COLUNAS_EXCEL)
    # % Regra fica como a consulta devolve (texto "10.00%"), sem valor negativo — igual ao Contas a Receber - Exportação.
    if "% Regra" in df_excel.columns:
        df_excel["% Regra"] = (
            df_excel["% Regra"].astype(str).str.strip().str.replace("-", "", regex=False)
            .replace({"None": "", "nan": ""})
        )
    # Dias fica negativo quando vencido (convenção da consulta); os valores não ficam negativos.
    for col in df_excel.select_dtypes("number").columns:
        if col != "Dias Vencto.":
            df_excel[col] = df_excel[col].abs()
    arquivo_excel = exportar_excel(
        df_excel, "CONTAS_A_RECEBER_MI",
        colunas_moeda=_COLUNAS_MOEDA,
        colunas_verde_vermelho=("Dias Vencto.",),
        colunas_situacao_sem_fundo=("Situação Vencto.", "Classif. Vencto."),
    )
    periodo = f"{data_de:%d-%m-%Y} a {data_ate:%d-%m-%Y}"
    botao_exportar_excel(arquivo_excel, f"Contas_a_Receber_MI {periodo}.xlsx", key="rcmi_export")
