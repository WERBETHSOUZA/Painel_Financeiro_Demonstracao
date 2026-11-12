import re

import streamlit as st
import pandas as pd
from components.buttons import botao_exportar_excel, botoes_acao_row
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.exporters import exportar_excel
from utils.imagem_email import gerar_imagem_inconsistencias
from services.email_service import obter_obs_inconsistencia

_PALETA_CATEGORIAS = ["#E24B4A", "#BA7517", "#4A7FB5", "#7B68B5", "#2ECC71", "#E8724A"]

_gerar_imagem_cached = st.cache_data(show_spinner=False, max_entries=20)(gerar_imagem_inconsistencias)


def _inteiros_sem_decimal(df: pd.DataFrame) -> pd.DataFrame:
    """Códigos e números (AP, Num_Lancto, Cód_Agente...) chegam do Oracle como decimal (409305.0). Colunas numéricas cujos
    valores são todos inteiros viram inteiro, na tela, no Excel e na imagem. Valores em dinheiro (SALDO) ficam como estão."""
    df = df.copy()
    for c in df.columns:
        if "SALDO" in c or "VALOR" in c or not pd.api.types.is_float_dtype(df[c]):
            continue
        v = df[c].dropna()
        if len(v) and (v % 1 == 0).all():
            df[c] = df[c].astype("Int64").astype(object).where(df[c].notna(), None)
    return df


def render(df_erros: pd.DataFrame):
    df_filtrado = _inteiros_sem_decimal(df_erros)

    if len(df_filtrado) == 0:
        st.title("Inconsistências de Lançamentos")
        st.success("Nenhuma inconsistência encontrada.")
        return

    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Inconsistências de Lançamentos")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="inc_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── Filtro por solicitante (barra lateral): vale para cards, resumo, tabela, Excel e imagem ──────────────
    _col_sol = next((c for c in df_filtrado.columns if "SOLICITANTE" in c), None)
    sol_sel = []
    if _col_sol:
        solicitantes_lista = sorted(df_filtrado[_col_sol].dropna().unique().tolist())
        with st.sidebar:
            st.caption("Inconsistências de Lançamentos")
            sol_sel = st.multiselect("Solicitante", solicitantes_lista, key="inc_filtro_sol",
                                     placeholder="Todos os solicitantes")
        if sol_sel:
            df_filtrado = df_filtrado[df_filtrado[_col_sol].isin(sol_sel)]
            if df_filtrado.empty:
                st.info("Nenhuma inconsistência para os solicitantes selecionados.")
                return

    # Colunas chegam em maiúsculas do data_service (_limpar_colunas faz .upper())
    # Aliases do SQL: Organização→ORGANIZAÇÃO, Cód_Filial→CÓD_FILIAL, Num_Lancto→NUM_LANCTO
    _col_org   = next((c for c in df_filtrado.columns if "ORGANI" in c), None)
    _col_fil   = next((c for c in df_filtrado.columns if "FILIAL" in c and "NOME" not in c), None)
    _col_lanc  = next((c for c in df_filtrado.columns if "LANCTO" in c or "NUMLANCTO" in c), None)

    if _col_org and _col_fil and _col_lanc:
        qtd_lancamentos = (
            df_filtrado[_col_org].astype(str)
            + "-" + df_filtrado[_col_fil].astype(str)
            + "-" + df_filtrado[_col_lanc].astype(str)
        ).nunique()
    else:
        qtd_lancamentos = len(df_filtrado)

    _col_cat = next((c for c in df_filtrado.columns if "CATEGORIA" in c and "ERRO" in c), "CATEGORIA_ERRO")

    df_expandido = df_filtrado.assign(
        **{_col_cat: df_filtrado[_col_cat].str.split(r"\s*\|\s*")}
    ).explode(_col_cat)
    df_expandido[_col_cat] = df_expandido[_col_cat].str.strip()

    resumo_erros = (
        df_expandido
        .groupby(_col_cat, as_index=False)
        .agg(QTD_ERROS=(_col_cat, "count"))
        .sort_values("QTD_ERROS", ascending=False)
    )

    render_cards_row([
        card_html(
            "Lançamentos com Erro", str(qtd_lancamentos),
            "Total identificado", cor_borda="#E24B4A", largura="280px",
        ),
        card_html(
            "Categorias de Erro", str(df_filtrado[_col_cat].nunique()),
            "Tipos distintos identificados", cor_borda="#BA7517", largura="280px",
        ),
    ])

    st.divider()

    st.subheader("Resumo por Categoria de Erro")

    render_cards_row([
        card_html(
            f"{row[_col_cat]}", str(row["QTD_ERROS"]),
            cor_borda=_PALETA_CATEGORIAS[i % len(_PALETA_CATEGORIAS)],
            truncar_label=True,
        )
        for i, row in resumo_erros.reset_index(drop=True).iterrows()
    ])

    st.divider()

    col_titulo, col_qtd = st.columns([6, 1], vertical_alignment="center")
    with col_titulo:
        st.subheader("Inconsistências de Lançamentos")

    df_exib = df_filtrado.copy()

    # Coluna Observação calculada a partir da categoria de erro
    df_exib = df_exib.copy()
    df_exib["Observação"] = df_exib[_col_cat].apply(obter_obs_inconsistencia)

    with col_qtd:
        st.caption(f"{len(df_exib)} registro(s)")

    # Na tela cada lançamento ocupa uma linha só: quebras de linha dentro da célula (ex.: rateio de centros
    # de custo) viram " | ". Excel e PNG seguem com o texto original.
    df_tela = df_exib.copy()
    for _c in df_tela.columns:
        if pd.api.types.is_datetime64_any_dtype(df_tela[_c]):     # datas na tela: dd/mm/aaaa
            df_tela[_c] = df_tela[_c].dt.strftime("%d/%m/%Y").fillna("")
            continue
        if pd.api.types.is_string_dtype(df_tela[_c]):
            df_tela[_c] = df_tela[_c].map(
                lambda v: re.sub(r"\s*[\r\n]+\s*", " | ", v) if isinstance(v, str) else v
            )
    render_tabela_html(df_tela)

    # ── Excel ─────────────────────────────────────────────────────────────────
    arquivo_excel = exportar_excel(df_exib, "LANCAMENTOS_ERRO")

    # ── PNG ───────────────────────────────────────────────────────────────────
    titulo_png = "Inconsistências de Lançamentos"
    if sol_sel:
        titulo_png += " — " + ", ".join(sol_sel)
    imagem_bytes = _gerar_imagem_cached(df_exib, titulo=titulo_png)

    botoes_acao_row(
        excel={"data": arquivo_excel, "file_name": "Inconsistencias_Lancamento.xlsx", "key": "inc_excel"},
        imagem={"data": imagem_bytes, "file_name": "Inconsistencias_Lancamento.png", "key": "inc_png"},
        copiar={"data": imagem_bytes, "key": "inc_copiar"},
    )
