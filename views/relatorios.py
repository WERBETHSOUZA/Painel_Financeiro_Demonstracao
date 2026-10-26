from datetime import date
import streamlit as st
import pandas as pd
import altair as alt
from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.exporters import exportar_excel


def render(df_relatorio: pd.DataFrame, atualizar=None):
    df_base = df_relatorio.copy()
    # A consulta devolve a organização na coluna ORG (ou ORGANIZACAO, em versões antigas).
    col_org = next((c for c in ("ORG", "ORGANIZACAO") if c in df_base.columns), None)

    if "VENCTO" in df_base.columns:
        df_base["DATA_FILTRO"] = pd.to_datetime(
            df_base["VENCTO"], format="%d/%m/%Y", errors="coerce"
        )

    # Filtros acoplados na barra lateral abaixo do Menu
    with st.sidebar:
        st.write("---")
        orgs_disponiveis = (
            sorted(df_base[col_org].dropna().unique()) if col_org else []
        )
        organizacoes = st.multiselect(
            "Organização",
            orgs_disponiveis,
            help="Selecione uma ou mais organizações",
            key="filtro_rel_org"
        )
        hoje = date.today()
        data_inicio = st.date_input("Data inicial", value=hoje.replace(day=1), format="DD/MM/YYYY", key="filtro_rel_ini")
        data_fim    = st.date_input("Data final", value=hoje, format="DD/MM/YYYY", key="filtro_rel_fim")
        gerar       = st.button("Gerar Relatório", use_container_width=True)

    if gerar:
        st.session_state["_rel_gerou"] = True
        if atualizar and atualizar():
            st.rerun()

    if not st.session_state.get("_rel_gerou"):
        st.title("Relatório de Aprovação")
        st.info("Escolha o período e organização na barra lateral e clique em **Gerar Relatório**.")
        return

    # Conteúdo da Área Principal
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title(f"Relatório de Aprovação — {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="rel_aprov_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Processamento dos dados filtrados
    df_aprovacao = df_base.copy()

    if "DATA_FILTRO" in df_aprovacao.columns:
        df_aprovacao = df_aprovacao[
            (df_aprovacao["DATA_FILTRO"] >= pd.to_datetime(data_inicio)) &
            (df_aprovacao["DATA_FILTRO"] <= pd.to_datetime(data_fim))
        ]

    if organizacoes and col_org:
        df_aprovacao = df_aprovacao[df_aprovacao[col_org].isin(organizacoes)]

    if "DATA_FILTRO" in df_aprovacao.columns:
        df_aprovacao = df_aprovacao.drop(columns=["DATA_FILTRO"])

    colunas_relatorio = [
        "FILIAL", "AP", "STATUS", "APROVADORES",
        "TP DOC", "DOC", "PARC", "FAVORECIDO",
        "SALDO", "VALOR", "EMISSAO", "ENTRADA", "VENCTO",
        "QTD_ANEXOS", "STATUS_ANEXO", "NOME_ANEXO",
    ]
    colunas_relatorio = [c for c in colunas_relatorio if c in df_aprovacao.columns]
    df_exportar = df_aprovacao[colunas_relatorio].copy()

    # Datas como data de verdade (o Excel agrupa por ano/mês no filtro) e valores como número.
    colunas_data = [c for c in ("EMISSAO", "ENTRADA", "VENCTO") if c in df_exportar.columns]
    for c in colunas_data:
        df_exportar[c] = pd.to_datetime(df_exportar[c], errors="coerce", dayfirst=True)
    # Documento como número (formato Geral) quando são só dígitos, sem zeros à esquerda;
    # se houver letras ou zeros à esquerda, continua texto para não perder informação.
    if "DOC" in df_exportar.columns:
        doc_txt = df_exportar["DOC"].astype(str).str.strip()
        so_numeros = doc_txt.str.fullmatch(r"[1-9]\d*").fillna(False)
        vazios = df_exportar["DOC"].isna() | (doc_txt == "")
        if bool((so_numeros | vazios).all()):
            df_exportar["DOC"] = pd.to_numeric(doc_txt.where(~vazios), errors="coerce").astype("Int64")
    colunas_valor = [c for c in ("SALDO", "VALOR") if c in df_exportar.columns]
    for c in colunas_valor:
        df_exportar[c] = pd.to_numeric(df_exportar[c], errors="coerce")

    if len(df_exportar) == 0:
        st.warning("Nenhum registro encontrado para o período e filtros selecionados.")
        return

    # Cards: só quantidade, sem valor.
    render_cards_row([
        card_html("Qtd. em Aprovação", str(len(df_exportar)), cor_borda="#E24B4A"),
        card_html("Filiais", str(df_exportar["FILIAL"].nunique()), cor_borda="#1E88E5"),
    ])

    st.divider()

    # Gráfico e Tabela de Categorias
    resumo_erros = (
        df_exportar
        .groupby("CATEGORIA_ERRO", as_index=False)
        .agg(QTD_AP=("AP", "count"))
        .sort_values("QTD_AP", ascending=False)
    ) if "CATEGORIA_ERRO" in df_exportar.columns else None

    if resumo_erros is not None and not resumo_erros.empty:
        st.subheader("Categoria")
        col_tab, col_chart = st.columns(2)
        
        with col_tab:
            render_tabela_html(resumo_erros)
            
        with col_chart:
            grafico = (
                alt.Chart(resumo_erros)
                .mark_bar(size=4, color="#1E88E5")
                .encode(
                    x=alt.X("QTD_AP:Q", title="Quantidade de APs"),
                    y=alt.Y("CATEGORIA_ERRO:N", title="Categoria", sort="-x")
                )
                .properties(height=260)
            )
            st.altair_chart(grafico, use_container_width=True)
            
        st.divider()

    # Tabela principal e Download
    st.subheader("Relatório para Aprovação")
    df_tela = df_exportar.copy()
    for c in colunas_data:
        df_tela[c] = df_tela[c].dt.strftime("%d/%m/%Y")
    for c in colunas_valor:
        df_tela[c] = df_tela[c].apply(
            lambda v: "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(v) else "")
    render_tabela_html(df_tela, colunas_moeda=colunas_valor)

    arquivo_excel = exportar_excel(df_exportar, "APROVACAO")
    nome_arquivo = f"Relatorio_Aprovacao {data_inicio.strftime('%d-%m-%Y')} a {data_fim.strftime('%d-%m-%Y')}.xlsx"
    botao_exportar_excel(arquivo_excel, nome_arquivo, key="rel_aprov_export")
