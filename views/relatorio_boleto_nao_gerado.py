"""
views/relatorio_boleto_nao_gerado.py
======================================
Relatório "Boleto Não Gerado": TODOS os títulos de Mercado Interno, Pessoa
Jurídica, sem boleto gerado (A Vencer/Vencido) — com uma coluna Status:
BLOQUEADO (desconto da regra ainda não aplicado — Faturamento/DESC_APLIC_NF
ou Financeiro/DESC_APLIC_FIN) ou LIBERADO (nada travando, pronto pra gerar).
Usa a mesma base do Contas a Receber (QUERY_CONTAS_RECEBER.sql).
"""

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.exporters import exportar_excel, REGRAS_STATUS_BOLETO

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
    "DESC_APLIC_NF":  "DESCONTO_NF",
    "DESC_APLIC_FIN": "DESCONTO_FINANC",
    "SALDO_EM_ABERTO": "SALDO_EM_ABERTO",
    "STATUS":         "STATUS",
}
# SITUACAO_BOLETO não entra: o filtro já garante que nunca tem boleto gerado,
# então sempre viria "-" — sem sentido mostrar.
_COLUNAS_MOEDA = ("VALOR_TOTAL", "VALOR_LIQUIDO_NF", "DESCONTO_NF", "DESCONTO_FINANC", "SALDO_EM_ABERTO")
_COLUNAS_PERCENTUAL_TEXTO = ("PERC_REGRA",)


def _status_boleto(row) -> str:
    if row["TIPO_REGRA"] == "FATURAMENTO" and pd.isna(row["DESC_APLIC_NF"]):
        return "BLOQUEADO - Desconto Faturamento pendente"
    if row["TIPO_REGRA"] == "FINANCEIRO" and pd.isna(row["DESC_APLIC_FIN"]):
        return "BLOQUEADO - Desconto Financeiro pendente"
    return "LIBERADO"


def _formatar_numero(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def render(df_cr: pd.DataFrame) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Boleto Não Gerado")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="bng_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with st.sidebar:
        st.write("---")
        st.caption("Boleto Não Gerado")
        status_sel = st.multiselect(
            "Status", ["LIBERADO", "BLOQUEADO"], default=["LIBERADO"], key="rbn_status",
            help="Deixe em branco para trazer os dois.",
        )
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rbn_gerar")

    if gerar:
        st.session_state["_rbn_gerou"] = True

    if not st.session_state.get("_rbn_gerou"):
        st.info("Clique em **Gerar Relatório** na barra lateral para visualizar.")
        return

    if df_cr is None or df_cr.empty:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return

    obrigatorias = {"MERCADO", "SITUACAO_BOLETO", "SITUACAO", "TIPO_REGRA", "DESC_APLIC_NF", "DESC_APLIC_FIN"}
    if not obrigatorias.issubset(df_cr.columns):
        st.warning("Dados incompletos para montar este relatório.")
        return

    df_base = df_cr[
        (df_cr["MERCADO"] == "MI")
        & (df_cr["SITUACAO_BOLETO"] != "BOLETO GERADO")
        & (df_cr["SITUACAO"].isin(["A VENCER", "VENCIDO"]))
    ].copy()
    # Cliente Pessoa Física não precisa de boleto — não entra no relatório.
    if "TIPO_PESSOA" in df_base.columns:
        df_base = df_base[df_base["TIPO_PESSOA"] != "F"]

    if df_base.empty:
        st.success("Todos os títulos em aberto do Mercado Interno já têm boleto gerado.")
        return

    df_filtrado = df_base.copy()
    df_filtrado["STATUS"] = df_filtrado.apply(_status_boleto, axis=1)

    if status_sel:
        mascara = pd.Series(False, index=df_filtrado.index)
        if "LIBERADO" in status_sel:
            mascara |= df_filtrado["STATUS"] == "LIBERADO"
        if "BLOQUEADO" in status_sel:
            mascara |= df_filtrado["STATUS"].str.startswith("BLOQUEADO")
        df_filtrado = df_filtrado[mascara]
        if df_filtrado.empty:
            st.info("Nenhum título encontrado para o status selecionado.")
            return

    qtd_bloqueado = int(df_filtrado["STATUS"].str.startswith("BLOQUEADO").sum())
    qtd_liberado = int((df_filtrado["STATUS"] == "LIBERADO").sum())

    render_cards_row([
        card_html("Qtd. Total", str(len(df_filtrado)), cor_borda="#8B5CF6"),
        card_html("Liberado (pode gerar)", str(qtd_liberado), cor_borda="#22c55e"),
        card_html("Bloqueado (desconto pendente)", str(qtd_bloqueado), cor_borda="#E24B4A"),
        card_html("Saldo em Aberto (total)",
                  "R$ " + _formatar_numero(df_filtrado["SALDO_EM_ABERTO"].sum()), cor_borda="#639922"),
    ])

    st.divider()
    st.caption(f"{len(df_filtrado)} título(s) encontrado(s).")

    colunas_existentes = [c for c in _COLUNAS if c in df_filtrado.columns]
    df_tela = df_filtrado[colunas_existentes].copy()
    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
        if col in df_tela.columns:
            df_tela[col] = pd.to_datetime(df_tela[col], errors="coerce").dt.strftime("%d/%m/%Y")
    for col in ("VALOR_FATURADO", "LIQUIDO_FIN", "DESC_APLIC_NF", "DESC_APLIC_FIN", "SALDO_EM_ABERTO"):
        if col in df_tela.columns:
            df_tela[col] = df_tela[col].apply(_formatar_numero)
    df_tela = df_tela.rename(columns=_COLUNAS)
    render_tabela_html(df_tela)

    df_excel = df_filtrado[colunas_existentes].copy()
    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
        if col in df_excel.columns:
            df_excel[col] = pd.to_datetime(df_excel[col], errors="coerce")
    for col in ("VALOR_FATURADO", "LIQUIDO_FIN", "DESC_APLIC_NF", "DESC_APLIC_FIN", "SALDO_EM_ABERTO"):
        if col in df_excel.columns:
            df_excel[col] = pd.to_numeric(df_excel[col], errors="coerce")
    df_excel = df_excel.rename(columns=_COLUNAS)
    for col in set(_COLUNAS_PERCENTUAL_TEXTO) & set(df_excel.columns):
        df_excel[col] = (
            df_excel[col].astype(str).str.strip()
            .str.replace("-", "", regex=False)
            .replace({"None": "", "nan": ""})
        )

    arquivo_excel = exportar_excel(
        df_excel, "BOLETO_NAO_GERADO",
        colunas_situacao=("SITUACAO",), colunas_moeda=_COLUNAS_MOEDA,
        colunas_status={"STATUS": REGRAS_STATUS_BOLETO},
    )
    botao_exportar_excel(arquivo_excel, "Boleto_Nao_Gerado.xlsx", key="rbn_export")
