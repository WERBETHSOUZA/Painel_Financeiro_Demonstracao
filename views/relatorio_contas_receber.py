"""
views/relatorio_contas_receber.py
===================================
Relatório "Contas a Receber - Exportação": exportação completa dos títulos em
aberto (Mercado Interno + Externo), usando a mesma base do Contas a Receber
(QUERY_CONTAS_RECEBER.sql). Filtros de data, mercado, status e grupo
econômico são opcionais e ficam na barra lateral; sem nenhum filtro, mostra
tudo que está em aberto. Pensado para exportação: os cards só contam
títulos, sem valor.
"""

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.prazos import calcular_dias_prazo, formatar_dias_html, formatar_dias_unificado_html, nullar_zeros_dias, VERDE_DIAS, VERMELHO_DIAS
from utils.exporters import exportar_excel

_SEM_GRUPO = "— sem grupo —"

# Colunas mostradas na tela — um resumo legível, não a consulta inteira.
_COLUNAS_TELA = {
    "CLIENTE":          "Cliente",
    "PAIS":             "País",
    "NF":               "NF",
    "CONTAINER":        "Container",
    "PARCELA":          "Parcela",
    "VALOR_FATURADO":   "Valor Faturado",
    "SALDO_EM_ABERTO":  "Saldo em Aberto",
    "MOEDA":            "Moeda",
    "COTACAO":          "Cotação",
    "SALDO_MOEDA":      "Saldo (Moeda)",
    "ENTRADA":          "Entrada",
    "VENCIMENTO":       "Vencimento",
    "PRORROGADO":       "Prorrogado",
    "DIAS_VENCIDO":     "Dias Vencto.",
    "SITUACAO":         "Situação Vencto.",
    "MERCADO":          "Mercado",
    "VENDEDOR":         "Vendedor",
}

# Colunas do Excel — a consulta inteira (QUERY_CONTAS_RECEBER.sql), com nomes legíveis.
_COLUNAS_EXCEL = {
    "SEMANA":            "Semana",
    "ANO":               "Ano",
    "ENTRADA":           "Entrada",
    "VENCIMENTO":        "Vencimento",
    "PRORROGADO":        "Prorrogado",
    "DIAS":              "Dias Vencto.",
    "SITUACAO":          "Situação Vencto.",
    "MERCADO":           "Mercado",
    "CLASSIFICACAO":     "Classificação",
    "COD_CLIENTE":       "Cód. Cliente",
    "CLIENTE":           "Cliente",
    "PAIS":              "País",
    "PARCELA":           "Parcela",
    "TIPO_DOC":          "Tipo Doc.",
    "NF":                "NF",
    "CONTAINER":         "Container",
    "VALOR_FATURADO":    "Valor Faturado",
    "TIPO_REGRA":        "Tipo Regra",
    "PERC_REGRA":        "% Regra",
    "DESC_APLIC_NF":     "Desc. Aplic. NF",
    "PERC_APLIC_NF":     "% Aplic. NF",
    "LIQUIDO_FIN":       "Líquido Financeiro",
    "DESC_APLIC_FIN":    "Desc. Aplic. Financeiro",
    "PERC_APLIC_FIN":    "% Aplic. Financeiro",
    "ACRESCIMOS":        "Acréscimos",
    "DEVOLUCAO":         "Devolução",
    "SALDO_EM_ABERTO":   "Saldo em Aberto",
    "MOEDA":             "Moeda",
    "VLR_PARCELA_MOEDA": "Valor da Parcela (Moeda)",
    "COTACAO":           "Cotação",
    "SALDO_MOEDA":       "Saldo em Aberto (Moeda)",
    "COMPLEMENTO":       "Complemento",
    "ACAO":              "Ação",
    "CENTRO_CUSTO":      "Centro de Custo",
    "NOSSO_NUMERO":      "Nosso Número",
    "LINHA_DIGITAVEL":   "Linha Digitável",
    "BANCO_NOME":        "Banco",
    "SITUACAO_BOLETO":   "Situação Boleto",
    "VENDEDOR":          "Vendedor",
    "EMAIL_CLIENTE":     "E-mail Cliente",
    "FAIXA_DIAS":        "Faixa de Dias",
}

# Colunas de percentual: a consulta já devolve como TEXTO formatado ("12.30%", com
# ponto) — extraímos o número (12.3) para virar percentual de verdade no Excel,
# exibido como "12,30%" (formato, não texto).
_COLUNAS_PERCENTUAL = ("% Regra", "% Aplic. NF", "% Aplic. Financeiro")

# Colunas de valor (R$): sempre "#.##0,00", mesmo que o nome não bata com os padrões
# genéricos do exportador (aqui os nomes têm acento/espaço próprios do relatório).
_COLUNAS_MOEDA = (
    "Valor Faturado", "Desc. Aplic. NF", "Líquido Financeiro", "Desc. Aplic. Financeiro",
    "Acréscimos", "Devolução", "Saldo em Aberto", "Valor da Parcela (Moeda)",
    "Saldo em Aberto (Moeda)",
)

_MERCADOS = {"Mercado Interno": "MI", "Mercado Externo": "ME"}


def _formatar_numero(valor, casas: int = 2) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _com_grupo(df_cr: pd.DataFrame, df_grupo_agentes: pd.DataFrame, df_grupo_geral: pd.DataFrame) -> pd.DataFrame:
    """Junta o nome do grupo econômico (Grupo de Crédito) em cada título pelo
    código do cliente. Cliente sem grupo cadastrado vira "— sem grupo —"."""
    df = df_cr.copy()
    df["GRUPO"] = _SEM_GRUPO
    if (
        df_grupo_agentes is None or df_grupo_agentes.empty
        or not {"COD_AGENTE", "COD_GRUPO"}.issubset(df_grupo_agentes.columns)
        or df_grupo_geral is None or df_grupo_geral.empty
        or not {"GRUPO_CODIGO", "NOME_GRUPO"}.issubset(df_grupo_geral.columns)
        or "COD_CLIENTE" not in df.columns
    ):
        return df

    grupo_por_codigo = df_grupo_geral.drop_duplicates("GRUPO_CODIGO").set_index("GRUPO_CODIGO")["NOME_GRUPO"]
    agente_para_grupo = (
        df_grupo_agentes.drop_duplicates("COD_AGENTE")
        .set_index(df_grupo_agentes["COD_AGENTE"].astype(str))["COD_GRUPO"]
        .map(grupo_por_codigo)
    )
    nomes = df["COD_CLIENTE"].astype(str).map(agente_para_grupo)
    df["GRUPO"] = nomes.fillna(_SEM_GRUPO)
    return df


def render(df_cr: pd.DataFrame, df_grupo_agentes: pd.DataFrame = None, df_grupo_geral: pd.DataFrame = None) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Contas a Receber - Exportação")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="rcr_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if df_cr.empty:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return

    df_cr = _com_grupo(df_cr, df_grupo_agentes, df_grupo_geral)
    grupos_disponiveis = sorted(g for g in df_cr["GRUPO"].dropna().unique() if g != _SEM_GRUPO)

    # ── Filtros (opcionais) na barra lateral ─────────────────────────────────
    with st.sidebar:
        st.write("---")
        st.caption("Contas a Receber - Exportação")
        entrada = st.date_input(
            "Entrada (opcional)", value=(), format="DD/MM/YYYY", key="rcr_entrada",
            help="Deixe em branco para não filtrar por data de entrada.",
        )
        vencimento = st.date_input(
            "Vencimento (opcional)", value=(), format="DD/MM/YYYY", key="rcr_vencimento",
            help="Deixe em branco para não filtrar por data de vencimento.",
        )
        mercado_sel = st.multiselect("Mercado", list(_MERCADOS), key="rcr_mercado")
        status_sel = st.multiselect("Status", ["VENCIDO", "A VENCER"], key="rcr_status")
        grupo_sel = st.multiselect("Grupo", grupos_disponiveis, key="rcr_grupo")
        gerar = st.button("Gerar Relatório", use_container_width=True)

    if gerar:
        st.session_state["_rcr_gerou"] = True

    if not st.session_state.get("_rcr_gerou"):
        st.info(
            "Ajuste os filtros na barra lateral (todos opcionais) e clique em "
            "**Gerar Relatório**. Sem nenhum filtro, mostra tudo que está em aberto hoje."
        )
        return

    # ── Filtro de data (opcional) ─────────────────────────────────────────────
    df_base = df_cr.copy()
    if isinstance(entrada, (tuple, list)) and len(entrada) == 2:
        df_base = df_base[
            (df_base["ENTRADA"] >= pd.to_datetime(entrada[0]))
            & (df_base["ENTRADA"] <= pd.to_datetime(entrada[1]))
        ]
    if isinstance(vencimento, (tuple, list)) and len(vencimento) == 2:
        df_base = df_base[
            (df_base["VENCIMENTO"] >= pd.to_datetime(vencimento[0]))
            & (df_base["VENCIMENTO"] <= pd.to_datetime(vencimento[1]))
        ]

    if df_base.empty:
        st.info("Nenhum título encontrado para o período selecionado.")
        return

    # ── Cards: só quantidade de títulos, por mercado (sempre sobre a base
    # já filtrada por data, antes do filtro de Mercado/Status da tabela) ──────
    df_mi = df_base[df_base["MERCADO"] == "MI"] if "MERCADO" in df_base.columns else df_base.iloc[0:0]
    df_me = df_base[df_base["MERCADO"] == "ME"] if "MERCADO" in df_base.columns else df_base.iloc[0:0]

    def _qtd_sit(d: pd.DataFrame, sit: str) -> int:
        return int((d["SITUACAO"] == sit).sum()) if "SITUACAO" in d.columns else 0

    df_todos = pd.concat([df_mi, df_me], ignore_index=True)
    render_cards_row([
        card_html("Qtd. A Vencer — MI", str(_qtd_sit(df_mi, "A VENCER")), cor_borda="#22c55e"),
        card_html("Qtd. Vencidos — MI", str(_qtd_sit(df_mi, "VENCIDO")), cor_borda="#E24B4A"),
        card_html("Qtd. A Vencer — ME", str(_qtd_sit(df_me, "A VENCER")), cor_borda="#22c55e"),
        card_html("Qtd. Vencidos — ME", str(_qtd_sit(df_me, "VENCIDO")), cor_borda="#E24B4A"),
        card_html("Qtd. Total — MI + ME", str(len(df_todos)), cor_borda="#6366F1"),
    ])

    st.divider()

    # ── Filtro de Mercado / Status (opcionais, aplicados só na tabela/Excel) ──
    df_filtrado = df_base.copy()
    if mercado_sel and "MERCADO" in df_filtrado.columns:
        codigos = [_MERCADOS[m] for m in mercado_sel]
        df_filtrado = df_filtrado[df_filtrado["MERCADO"].isin(codigos)]
    if status_sel and "SITUACAO" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["SITUACAO"].isin(status_sel)]
    if grupo_sel:
        df_filtrado = df_filtrado[df_filtrado["GRUPO"].isin(grupo_sel)]

    if df_filtrado.empty:
        st.info("Nenhum título encontrado para os filtros selecionados.")
        return

    st.caption(f"{len(df_filtrado)} título(s) encontrado(s).")

    # Colunas de moeda estrangeira (Moeda/Cotação/Saldo em Moeda) só fazem sentido
    # quando há título de Mercado Externo na seleção — em Mercado Interno puro elas
    # vêm sempre vazias (a consulta zera esses campos quando Cotação = 1).
    tem_me = "MERCADO" in df_filtrado.columns and (df_filtrado["MERCADO"] == "ME").any()
    colunas_moeda_tela = ("MOEDA", "COTACAO", "SALDO_MOEDA", "CONTAINER", "PAIS")   # container e país só existem no mercado externo
    colunas_moeda_excel = ("MOEDA", "VLR_PARCELA_MOEDA", "COTACAO", "SALDO_MOEDA", "CONTAINER", "PAIS")

    # ── Tabela (resumo legível) ────────────────────────────────────────────────
    df_filtrado = calcular_dias_prazo(df_filtrado)
    colunas_tela = [c for c in _COLUNAS_TELA if c in df_filtrado.columns]
    if not tem_me:
        colunas_tela = [c for c in colunas_tela if c not in colunas_moeda_tela]
    df_tela = df_filtrado[colunas_tela].copy()

    for col in ("CONTAINER", "PAIS"):
        if col in df_tela.columns:
            df_tela[col] = df_tela[col].fillna("").replace({"nan": "", "None": ""})
    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
        if col in df_tela.columns:
            df_tela[col] = pd.to_datetime(df_tela[col], errors="coerce").dt.strftime("%d/%m/%y")
    if "DIAS" in df_tela.columns:
        # Negativo quando vencido (mesma convenção da consulta), positivo quando a vencer.
        df_tela["DIAS"] = pd.to_numeric(df_tela["DIAS"], errors="coerce").apply(
            lambda v: str(int(v)) if pd.notna(v) else "")
    if "COTACAO" in df_tela.columns:
        df_tela["COTACAO"] = df_tela["COTACAO"].apply(lambda v: _formatar_numero(v, 4))
    for col in ("VALOR_FATURADO", "SALDO_EM_ABERTO", "SALDO_MOEDA"):
        if col in df_tela.columns:
            df_tela[col] = df_tela[col].apply(_formatar_numero)

    if "DIAS_VENCIDO" in df_tela.columns and "SITUACAO" in df_tela.columns:
        df_tela["DIAS_VENCIDO"] = df_tela.apply(formatar_dias_unificado_html, axis=1)

    render_tabela_html(df_tela, colunas_renomear=_COLUNAS_TELA, coluna_situacao="SITUACAO")

    st.markdown("&nbsp;", unsafe_allow_html=True)

    # ── Excel: a consulta inteira (todas as colunas), valores/datas reais ─────
    colunas_excel = [c for c in _COLUNAS_EXCEL if c in df_filtrado.columns]
    if not tem_me:
        colunas_excel = [c for c in colunas_excel if c not in colunas_moeda_excel]
    df_excel = df_filtrado[colunas_excel].rename(columns=_COLUNAS_EXCEL)
    # % Regra / % Aplic. NF / % Aplic. Financeiro ficam como a consulta já devolve:
    # texto "10.00%" (com ponto), sem virar número formatado. Isso evita que alguém
    # aplique a formatação de % nativa do Excel em cima e multiplique o valor por 100
    # (10,00% x formato % = 1000%). Nenhuma porcentagem fica negativa (a consulta às
    # vezes devolve "-10.00%" quando o desconto aplicado é negativo).
    for col in set(_COLUNAS_PERCENTUAL) & set(df_excel.columns):
        df_excel[col] = (
            df_excel[col].astype(str).str.strip()
            .str.replace("-", "", regex=False)
            .replace({"None": "", "nan": ""})
        )
    # Dias fica negativo quando vencido (mesma convenção da consulta) — as demais
    # colunas numéricas (valores) não ficam negativas.
    for col in df_excel.select_dtypes("number").columns:
        if col != "Dias Vencto.":
            df_excel[col] = df_excel[col].abs()
    arquivo_excel = exportar_excel(
        df_excel, "CONTAS_A_RECEBER",
        colunas_moeda=_COLUNAS_MOEDA,
        colunas_verde_vermelho=("Dias Vencto.",),
        colunas_situacao_sem_fundo=("Situação Vencto.",),
    )
    botao_exportar_excel(arquivo_excel, "Contas_a_Receber.xlsx", key="rcr_export")
