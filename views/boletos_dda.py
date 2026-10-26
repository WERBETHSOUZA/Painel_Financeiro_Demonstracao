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
    dados["DT_VENCIMENTO"] = pd.to_datetime(
        dados["DT_VENCIMENTO"], errors="coerce"
    )
    dados["VALOR"] = pd.to_numeric(dados["VALOR"], errors="coerce").fillna(0)
    dados = dados.dropna(subset=["DT_VENCIMENTO"])

    if dados.empty:
        st.warning("Os boletos não possuem datas de vencimento válidas.")
        return

    dados["MES_VENCIMENTO"] = dados["DT_VENCIMENTO"].dt.to_period("M").astype(str)
    dados["STATUS"] = dados["DT_VENCIMENTO"].dt.date.map(
        lambda vencimento: "Vencido" if vencimento < date.today() else "Em dia"
    )

    data_inicial_padrao = dados["DT_VENCIMENTO"].min().date()
    data_final_padrao = dados["DT_VENCIMENTO"].max().date()

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
        sacados = sorted(dados["SACADO"].dropna().astype(str).unique().tolist())
        sacados_selecionados = st.multiselect(
            "Sacado",
            options=sacados,
            key="dda_sacados",
        )

    if data_inicial > data_final:
        st.error("A data inicial não pode ser posterior à data final.")
        return

    filtrado = dados[
        (dados["DT_VENCIMENTO"].dt.date >= data_inicial)
        & (dados["DT_VENCIMENTO"].dt.date <= data_final)
        & (dados["VALOR"] >= valor_minimo)
        & (dados["STATUS"].isin(status))
    ].copy()

    if sacados_selecionados:
        filtrado = filtrado[filtrado["SACADO"].astype(str).isin(sacados_selecionados)]

    if filtrado.empty:
        st.warning("Nenhum boleto corresponde aos filtros selecionados.")
        return

    with st.container(horizontal=True):
        st.metric("Total de boletos", f"{len(filtrado):,}".replace(",", "."), border=True)
        st.metric("Valor total", _formatar_reais(filtrado["VALOR"].sum()), border=True)
        st.metric("Valor médio", _formatar_reais(filtrado["VALOR"].mean()), border=True)
        st.metric("Vencidos", int((filtrado["STATUS"] == "Vencido").sum()), border=True)

    grafico_mes, grafico_status = st.columns(2)

    mensal = filtrado.groupby("MES_VENCIMENTO", as_index=False)["VALOR"].sum()
    figura_mensal = px.bar(
        mensal,
        x="MES_VENCIMENTO",
        y="VALOR",
        title="Valor por mês de vencimento",
        labels={"MES_VENCIMENTO": "Mês", "VALOR": "Valor total"},
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
        filtrado.groupby("SACADO", as_index=False)["VALOR"]
        .sum()
        .sort_values("VALOR", ascending=False)
        .head(10)
        .rename(columns={"SACADO": "Sacado", "VALOR": "Valor total"})
    )
    ranking["Valor total"] = ranking["Valor total"].apply(_formatar_reais)
    render_tabela_html(ranking, colunas_moeda=["Valor total"])

    st.subheader("Detalhes dos boletos")
    colunas = [
        "NOSSO_NUMERO",
        "SACADO",
        "CNPJ",
        "DT_VENCIMENTO",
        "VALOR",
        "STATUS",
        "NUM_TITULO",
        "DOCUMENTO",
        "MOTIVO",
    ]
    detalhes = filtrado[colunas].sort_values("DT_VENCIMENTO")
    nomes_excel = {
        "NOSSO_NUMERO": "Nosso Número",
        "SACADO": "Sacado",
        "CNPJ": "CNPJ",
        "DT_VENCIMENTO": "Vencimento",
        "VALOR": "Valor",
        "STATUS": "Status",
        "NUM_TITULO": "Número do Título",
        "DOCUMENTO": "Documento",
        "MOTIVO": "Motivo",
    }
    df_excel = detalhes.rename(columns=nomes_excel)
    df_excel["Vencimento"] = df_excel["Vencimento"].dt.strftime("%d/%m/%Y")
    _det = detalhes.copy()
    _det["DT_VENCIMENTO"] = pd.to_datetime(_det["DT_VENCIMENTO"], errors="coerce").dt.strftime("%d/%m/%Y")
    _det["VALOR"] = _det["VALOR"].apply(_formatar_reais)
    render_tabela_html(
        _det,
        colunas_renomear={
            "NOSSO_NUMERO": "Nosso Número", "SACADO": "Sacado",
            "CNPJ": "CNPJ", "DT_VENCIMENTO": "Vencimento",
            "VALOR": "Valor", "STATUS": "Status",
            "NUM_TITULO": "Número do Título", "DOCUMENTO": "Documento",
            "MOTIVO": "Motivo",
        },
        colunas_moeda=["VALOR"],
    )
    botao_exportar_excel(exportar_excel(df_excel, "BOLETOS_DDA"), "Boletos_DDA.xlsx", key="dda_export_excel")
