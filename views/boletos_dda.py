from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import render_tabela_html
from utils.exporters import exportar_excel


def _formatar_reais(valor: float) -> str:
    formatado = f"{valor:,.2f}"
    return f"R$ {formatado.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def render(df: pd.DataFrame) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Dashboard de Boletos DDA")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="dda_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if df.empty:
        st.warning("Nenhum boleto DDA foi encontrado.")
        return

    dados = df.copy()
    dados["BOL_DT_VENCIMENTO"] = pd.to_datetime(
        dados["BOL_DT_VENCIMENTO"], errors="coerce"
    )
    dados["BOL_RE_VALOR"] = pd.to_numeric(dados["BOL_RE_VALOR"], errors="coerce").fillna(0)
    dados = dados.dropna(subset=["BOL_DT_VENCIMENTO"])

    if dados.empty:
        st.warning("Os boletos não possuem datas de vencimento válidas.")
        return

    dados["MES_VENCIMENTO"] = dados["BOL_DT_VENCIMENTO"].dt.to_period("M").astype(str)
    dados["STATUS"] = dados["BOL_DT_VENCIMENTO"].dt.date.map(
        lambda vencimento: "Vencido" if vencimento < date.today() else "Em dia"
    )

    data_inicial_padrao = dados["BOL_DT_VENCIMENTO"].min().date()
    data_final_padrao = dados["BOL_DT_VENCIMENTO"].max().date()

    with st.sidebar:
        st.markdown("#### Filtros — Boletos DDA")
        data_inicial = st.date_input(
            "Data inicial",
            value=data_inicial_padrao,
            min_value=data_inicial_padrao,
            max_value=data_final_padrao,
            format="DD/MM/YYYY",
            key="dda_data_inicial",
        )
        data_final = st.date_input(
            "Data final",
            value=data_final_padrao,
            min_value=data_inicial_padrao,
            max_value=data_final_padrao,
            format="DD/MM/YYYY",
            key="dda_data_final",
        )
        valor_minimo = st.number_input(
            "Valor mínimo",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key="dda_valor_minimo",
        )
        status = st.multiselect(
            "Status",
            options=["Em dia", "Vencido"],
            default=["Em dia", "Vencido"],
            key="dda_status",
        )
        sacados = sorted(dados["BOL_ST_SACADO"].dropna().astype(str).unique().tolist())
        sacados_selecionados = st.multiselect(
            "Sacado",
            options=sacados,
            key="dda_sacados",
        )

    if data_inicial > data_final:
        st.error("A data inicial não pode ser posterior à data final.")
        return

    filtrado = dados[
        (dados["BOL_DT_VENCIMENTO"].dt.date >= data_inicial)
        & (dados["BOL_DT_VENCIMENTO"].dt.date <= data_final)
        & (dados["BOL_RE_VALOR"] >= valor_minimo)
        & (dados["STATUS"].isin(status))
    ].copy()

    if sacados_selecionados:
        filtrado = filtrado[filtrado["BOL_ST_SACADO"].astype(str).isin(sacados_selecionados)]

    if filtrado.empty:
        st.warning("Nenhum boleto corresponde aos filtros selecionados.")
        return

    with st.container(horizontal=True):
        st.metric("Total de boletos", f"{len(filtrado):,}".replace(",", "."), border=True)
        st.metric("Valor total", _formatar_reais(filtrado["BOL_RE_VALOR"].sum()), border=True)
        st.metric("Valor médio", _formatar_reais(filtrado["BOL_RE_VALOR"].mean()), border=True)
        st.metric("Vencidos", int((filtrado["STATUS"] == "Vencido").sum()), border=True)

    grafico_mes, grafico_status = st.columns(2)

    mensal = filtrado.groupby("MES_VENCIMENTO", as_index=False)["BOL_RE_VALOR"].sum()
    figura_mensal = px.bar(
        mensal,
        x="MES_VENCIMENTO",
        y="BOL_RE_VALOR",
        title="Valor por mês de vencimento",
        labels={"MES_VENCIMENTO": "Mês", "BOL_RE_VALOR": "Valor total"},
    )
    grafico_mes.plotly_chart(figura_mensal, width="stretch")

    quantidades = filtrado["STATUS"].value_counts().rename_axis("STATUS").reset_index(name="QUANTIDADE")
    figura_status = px.pie(
        quantidades,
        names="STATUS",
        values="QUANTIDADE",
        title="Distribuição por status",
        hole=0.4,
    )
    grafico_status.plotly_chart(figura_status, width="stretch")

    st.subheader("Top 10 sacados por maior valor")
    ranking = (
        filtrado.groupby("BOL_ST_SACADO", as_index=False)["BOL_RE_VALOR"]
        .sum()
        .sort_values("BOL_RE_VALOR", ascending=False)
        .head(10)
        .rename(columns={"BOL_ST_SACADO": "Sacado", "BOL_RE_VALOR": "Valor total"})
    )
    ranking["Valor total"] = ranking["Valor total"].apply(_formatar_reais)
    render_tabela_html(ranking, colunas_moeda=["Valor total"])

    st.subheader("Detalhes dos boletos")
    colunas = [
        "BOL_ST_NOSSONUMERO",
        "BOL_ST_SACADO",
        "BOL_ST_CNPJ",
        "BOL_DT_VENCIMENTO",
        "BOL_RE_VALOR",
        "STATUS",
        "BOL_ST_NUMTITULO",
        "BOL_ST_DOCUMENTO",
        "BOL_ST_MOTIVO",
    ]
    detalhes = filtrado[colunas].sort_values("BOL_DT_VENCIMENTO")
    nomes_excel = {
        "BOL_ST_NOSSONUMERO": "Nosso Número",
        "BOL_ST_SACADO": "Sacado",
        "BOL_ST_CNPJ": "CNPJ",
        "BOL_DT_VENCIMENTO": "Vencimento",
        "BOL_RE_VALOR": "Valor",
        "STATUS": "Status",
        "BOL_ST_NUMTITULO": "Número do Título",
        "BOL_ST_DOCUMENTO": "Documento",
        "BOL_ST_MOTIVO": "Motivo",
    }
    df_excel = detalhes.rename(columns=nomes_excel)
    df_excel["Vencimento"] = df_excel["Vencimento"].dt.strftime("%d/%m/%Y")
    _det = detalhes.copy()
    _det["BOL_DT_VENCIMENTO"] = pd.to_datetime(_det["BOL_DT_VENCIMENTO"], errors="coerce").dt.strftime("%d/%m/%Y")
    _det["BOL_RE_VALOR"] = _det["BOL_RE_VALOR"].apply(_formatar_reais)
    render_tabela_html(
        _det,
        colunas_renomear={
            "BOL_ST_NOSSONUMERO": "Nosso Número", "BOL_ST_SACADO": "Sacado",
            "BOL_ST_CNPJ": "CNPJ", "BOL_DT_VENCIMENTO": "Vencimento",
            "BOL_RE_VALOR": "Valor", "STATUS": "Status",
            "BOL_ST_NUMTITULO": "Número do Título", "BOL_ST_DOCUMENTO": "Documento",
            "BOL_ST_MOTIVO": "Motivo",
        },
        colunas_moeda=["BOL_RE_VALOR"],
    )
    botao_exportar_excel(exportar_excel(df_excel, "BOLETOS_DDA"), "Boletos_DDA.xlsx", key="dda_export_excel")
