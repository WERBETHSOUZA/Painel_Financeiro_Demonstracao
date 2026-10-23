"""
views/relatorio_desconto_financeiro_pendente.py
==================================================
Relatório "Desconto Financeiros Pendentes": todos os títulos de Mercado
Interno com regra de desconto FINANCEIRO — pendente ou já aplicado, com uma
coluna Status pra diferenciar — usando a mesma base do Contas a Receber
(QUERY_CONTAS_RECEBER.sql).
"""

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.exporters import exportar_excel, REGRAS_STATUS_DESCONTO

# Nomes exatamente como pedido — colunas cruas da consulta, sem "embelezar".
_COLUNAS = {
    "ENTRADA":        "ENTRADA",
    "VENCIMENTO":     "VENCIMENTO",
    "PRORROGADO":     "PRORROGADO",
    "SITUACAO":       "SITUACAO",
    "DIAS":           "DIAS",
    "COD_CLIENTE":    "CÓD_CLIENTE",
    "CLIENTE":        "CLIENTE",
    "PARCELA":        "PARCELA",
    "NF":             "NF",
    "VALOR_FATURADO": "VALOR_TOTAL",
    "TIPO_REGRA":     "TIPO_DESC",
    "PERC_REGRA":     "PERC_REGRA",
    "LIQUIDO_FIN":    "VALOR_LIQUIDO_NF",
    "DESCONTO_A_APLICAR": "DESCONTO_A_APLICAR",
    "VALOR_ATUALIZADO":   "VALOR_ATUALIZADO",
    "STATUS":         "STATUS",
}
# DESC_APLIC_FIN / PERC_APLIC_FIN não entram: este relatório já é só o que está
# pendente, então essas duas colunas viriam sempre em branco — sem sentido mostrar.
# SALDO_EM_ABERTO também sai — no lugar entra VALOR_ATUALIZADO (líquido já com o
# desconto financeiro pendente aplicado).
_COLUNAS_MOEDA = ("VALOR_TOTAL", "VALOR_LIQUIDO_NF", "DESCONTO_A_APLICAR", "VALOR_ATUALIZADO")
_COLUNAS_PERCENTUAL_TEXTO = ("PERC_REGRA",)


def _formatar_numero(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _parse_percentual(texto) -> float:
    """"3.00%" -> 0.03 (fração). Vazio/ inválido -> 0.0."""
    try:
        if pd.isna(texto):
            return 0.0
        return float(str(texto).strip().rstrip("%").replace(",", ".")) / 100
    except (TypeError, ValueError):
        return 0.0


def render(df_cr: pd.DataFrame) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Desconto Financeiros Pendentes")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="dfp_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with st.sidebar:
        st.write("---")
        st.caption("Desconto Financeiros Pendentes")
        status_sel = st.multiselect(
            "Status", ["PENDENTE", "APLICADO"], default=["PENDENTE"], key="rdf_status",
            help="Deixe em branco para trazer os dois.",
        )
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rdf_gerar")

    if gerar:
        st.session_state["_rdf_gerou"] = True

    if not st.session_state.get("_rdf_gerou"):
        st.info("Clique em **Gerar Relatório** na barra lateral para visualizar.")
        return

    if df_cr is None or df_cr.empty:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return

    obrigatorias = {"MERCADO", "TIPO_REGRA", "DESC_APLIC_FIN"}
    if not obrigatorias.issubset(df_cr.columns):
        st.warning("Dados incompletos para montar este relatório.")
        return

    df_filtrado = df_cr[
        (df_cr["MERCADO"] == "MI")
        & (df_cr["TIPO_REGRA"] == "FINANCEIRO")
    ].copy()

    if df_filtrado.empty:
        st.success("Nenhum título com regra de desconto financeiro no Mercado Interno.")
        return

    # A fórmula (Líquido x % da regra) vale pra qualquer título, esteja o desconto
    # já aplicado ou não — ela só calcula o que a regra determina. O que diferencia
    # é a coluna Status: PENDENTE (DESC_APLIC_FIN vazio) ou APLICADO (já preenchido).
    df_filtrado["STATUS"] = df_filtrado["DESC_APLIC_FIN"].apply(lambda v: "PENDENTE" if pd.isna(v) else "APLICADO")
    df_filtrado["DESCONTO_A_APLICAR"] = df_filtrado["LIQUIDO_FIN"] * df_filtrado["PERC_REGRA"].apply(_parse_percentual)
    df_filtrado["VALOR_ATUALIZADO"] = df_filtrado["LIQUIDO_FIN"] - df_filtrado["DESCONTO_A_APLICAR"]

    if status_sel:
        df_filtrado = df_filtrado[df_filtrado["STATUS"].isin(status_sel)]
        if df_filtrado.empty:
            st.info("Nenhum título encontrado para o status selecionado.")
            return

    qtd_pendente = int((df_filtrado["STATUS"] == "PENDENTE").sum())
    qtd_aplicado = int((df_filtrado["STATUS"] == "APLICADO").sum())

    render_cards_row([
        card_html("Qtd. Títulos", str(len(df_filtrado)), cor_borda="#8B5CF6"),
        card_html("Qtd. Pendente", str(qtd_pendente), cor_borda="#E24B4A"),
        card_html("Qtd. Aplicado", str(qtd_aplicado), cor_borda="#22c55e"),
        card_html("Desconto a Aplicar (total)",
                  "R$ " + _formatar_numero(df_filtrado["DESCONTO_A_APLICAR"].sum()), cor_borda="#639922"),
    ])

    st.divider()
    st.caption(f"{len(df_filtrado)} título(s) encontrado(s).")

    colunas_existentes = [c for c in _COLUNAS if c in df_filtrado.columns]
    df_tela = df_filtrado[colunas_existentes].copy()
    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
        if col in df_tela.columns:
            df_tela[col] = pd.to_datetime(df_tela[col], errors="coerce").dt.strftime("%d/%m/%Y")
    for col in ("VALOR_FATURADO", "LIQUIDO_FIN", "DESCONTO_A_APLICAR", "VALOR_ATUALIZADO"):
        if col in df_tela.columns:
            df_tela[col] = df_tela[col].apply(_formatar_numero)
    df_tela = df_tela.rename(columns=_COLUNAS)
    render_tabela_html(df_tela)

    df_excel = df_filtrado[colunas_existentes].copy()
    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
        if col in df_excel.columns:
            df_excel[col] = pd.to_datetime(df_excel[col], errors="coerce")
    for col in ("VALOR_FATURADO", "LIQUIDO_FIN", "DESCONTO_A_APLICAR", "VALOR_ATUALIZADO"):
        if col in df_excel.columns:
            df_excel[col] = pd.to_numeric(df_excel[col], errors="coerce")
    df_excel = df_excel.rename(columns=_COLUNAS)
    # % Regra fica como a consulta já devolve (texto "12.30%"),
    # sem virar percentual nativo — mesmo motivo do Contas a Receber: evita que
    # a formatação de % do Excel multiplique o valor por 100 se reaplicada.
    for col in set(_COLUNAS_PERCENTUAL_TEXTO) & set(df_excel.columns):
        df_excel[col] = (
            df_excel[col].astype(str).str.strip()
            .str.replace("-", "", regex=False)
            .replace({"None": "", "nan": ""})
        )

    arquivo_excel = exportar_excel(
        df_excel, "DESCONTO_FINANCEIRO_PENDENTE",
        colunas_situacao=("SITUACAO",), colunas_moeda=_COLUNAS_MOEDA,
        colunas_destacadas=("DESCONTO_A_APLICAR",),
        colunas_status={"STATUS": REGRAS_STATUS_DESCONTO},
    )
    botao_exportar_excel(arquivo_excel, "Desconto_Financeiros_Pendentes.xlsx", key="rdf_export")
