"""
views/adiantamentos.py
=======================
Painel de Adiantamentos — Demo.

Consome duas queries:
  - QUERY_ADIANTAMENTOS_GERAL.sql        → lançamentos detalhados (df_geral)
  - QUERY_ADIANTAMENTOS_TOTAL_AGENTE.sql → totais agregados por agente (df_total_agente)

Campos da query GERAL (após normalização de colunas em data_service.py):
  ORG_IN_CODIGO, ORGANIZACAO, FIL_IN_CODIGO, AGN_IN_CODIGO, AGENTE, NATUREZA
  ("EFETUADO"/"RECEBIDO"), MOV_ST_DOCUMENTO, MOV_DT_DATADOCTO,
  MOV_RE_VALOR, SALDO, RATEIO_CENTRO_CUSTO, SITUACAO, COMPLEMENTO

Campos da query TOTAL_AGENTE:
  COD_FILIAL, FILIAL, COD_AGENTE, AGENTE, NATUREZA,
  TOTAL_ADIANTADO_AGENTE, TOTAL_EM_ABERTO_AGENTE
"""

from datetime import date
import streamlit as st
import pandas as pd
import plotly.express as px
from components.buttons import botao_exportar_excel, botao_salvar_imagem
from components.cards import card_indicador, render_tabela_html
from utils.exporters import exportar_excel
from utils.imagem_email import gerar_imagem_resumo_titulos, render_botao_copiar_imagem

_gerar_imagem_adto_cached = st.cache_data(show_spinner=False, max_entries=50)(gerar_imagem_resumo_titulos)


# ── Formatação ────────────────────────────────────────────────────────────────

def _formatar_moeda(valor) -> str:
    try:
        v = float(valor)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


# ── Ranking por agente (query TOTAL_AGENTE) ────────────────────────────────────

def _ranking_agentes(df_total_agente: pd.DataFrame, natureza_filtro: str):
    if df_total_agente.empty or "COD_AGENTE" not in df_total_agente.columns:
        st.info("Sem dados de ranking por agente.")
        return

    # A query traz uma linha por (agente, natureza) distintos, mas os totais
    # já vêm somados por agente (window function) — removemos duplicidade
    # de agente para não contar o mesmo total mais de uma vez no ranking.
    df_rank = (
        df_total_agente[df_total_agente["NATUREZA"].str.upper() == natureza_filtro]
        .drop_duplicates(subset="COD_AGENTE")
        .sort_values("TOTAL_EM_ABERTO_AGENTE", ascending=True)
        .tail(10)
    )

    if df_rank.empty:
        st.info("Sem dados de ranking para esta situação.")
        return

    max_val = df_rank["TOTAL_EM_ABERTO_AGENTE"].max()
    fig = px.bar(
        df_rank,
        x="TOTAL_EM_ABERTO_AGENTE",
        y="AGENTE",
        orientation="h",
        color="TOTAL_EM_ABERTO_AGENTE",
        color_continuous_scale="Blues",
        labels={"TOTAL_EM_ABERTO_AGENTE": "", "AGENTE": ""},
        text=df_rank["TOTAL_EM_ABERTO_AGENTE"].apply(_formatar_moeda),
    )
    fig.update_traces(textposition="outside", textfont=dict(size=13, color="#e0e0e0"))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e0e0e0",
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=0, b=0),
        height=max(280, len(df_rank) * 36),
        xaxis=dict(showgrid=False, showticklabels=False, range=[0, max_val * 1.4]),
    )
    fig.update_yaxes(tickfont=dict(size=12), automargin=True)
    st.plotly_chart(fig, use_container_width=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def render(df_geral: pd.DataFrame, df_total_agente: pd.DataFrame) -> None:
    if df_geral.empty:
        st.title("Adiantamentos")
        st.info(
            "Nenhum dado disponível. Se você viu um aviso de **ORA-20003** acima, "
            "o problema está em registros com Movimento Original ausente no Oracle — "
            "solicite correção ao DBA.",
            icon="ℹ️",
        )
        return

    df_base = df_geral.copy()
    if "MOV_DT_DATADOCTO" in df_base.columns:
        df_base["MOV_DT_DATADOCTO"] = pd.to_datetime(df_base["MOV_DT_DATADOCTO"], errors="coerce")

    # Período padrão: 1º dia do mês vigente até hoje.
    hoje = date.today()
    data_min = hoje.replace(day=1)
    data_max = hoje

    # ── Filtros na barra lateral (período + organização) ─────────────────────
    with st.sidebar:
        orgs_disponiveis = (
            sorted(df_base["ORGANIZACAO"].dropna().unique())
            if "ORGANIZACAO" in df_base.columns else []
        )
        orgs_selecionadas = st.multiselect(
            "Organização",
            orgs_disponiveis,
            help="Selecione uma ou mais organizações",
            key="adto_orgs",
        )
        data_de = st.date_input("Data inicial", value=data_min, format="DD/MM/YYYY", key="adto_data_de")
        data_ate = st.date_input("Data final", value=data_max, format="DD/MM/YYYY", key="adto_data_ate")
        gerar = st.button("Gerar Relatório", use_container_width=True, key="adto_gerar")

    if gerar:
        st.session_state["_adto_gerou"] = True

    if not st.session_state.get("_adto_gerou"):
        st.title("Adiantamentos")
        st.info("Escolha o período e organização na barra lateral e clique em **Gerar Relatório**.")
        return

    periodo = f"{data_de.strftime('%d/%m/%Y')} a {data_ate.strftime('%d/%m/%Y')}" if data_de and data_ate else ""
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title(f"Adiantamentos — {periodo}" if periodo else "Adiantamentos")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="adto_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    cards_box = st.container()
    st.divider()

    df_geral_dt = df_base
    if orgs_selecionadas and "ORGANIZACAO" in df_geral_dt.columns:
        df_geral_dt = df_geral_dt[df_geral_dt["ORGANIZACAO"].isin(orgs_selecionadas)]

    if "MOV_DT_DATADOCTO" in df_geral_dt.columns and data_de and data_ate:
        df_geral_dt = df_geral_dt[
            (df_geral_dt["MOV_DT_DATADOCTO"].dt.date >= data_de)
            & (df_geral_dt["MOV_DT_DATADOCTO"].dt.date <= data_ate)
        ]

    if df_geral_dt.empty:
        st.warning("Nenhum adiantamento para o período/organização selecionados.")
        return

    # ── Toggle Todos / Efetuado / Recebido ───────────────────────────────────
    situacao_sel = st.radio(
        "Natureza:",
        options=["Todos", "Efetuado", "Recebido"],
        horizontal=True,
        key="adto_natureza",
    )
    natureza_filtro = situacao_sel.upper()

    busca_agente = st.text_input(
        "Buscar agente", placeholder="Nome ou código do agente...", key="adto_busca"
    )

    if natureza_filtro == "TODOS":
        df_filtrado = df_geral_dt.copy()
    else:
        df_filtrado = df_geral_dt[df_geral_dt["NATUREZA"].str.upper() == natureza_filtro].copy()

    if busca_agente:
        termo = busca_agente.strip().upper()
        df_filtrado = df_filtrado[
            df_filtrado["AGENTE"].str.upper().str.contains(termo, na=False)
            | df_filtrado["AGN_IN_CODIGO"].astype(str).str.contains(termo, na=False)
        ]

    # ── Cards (renderizados no topo via cards_box) ─────────────────────────
    total_lancado = df_filtrado["MOV_RE_VALOR"].sum() if "MOV_RE_VALOR" in df_filtrado.columns else 0
    total_saldo   = df_filtrado["SALDO"].sum() if "SALDO" in df_filtrado.columns else 0
    qtd_lancamentos = len(df_filtrado)
    qtd_agentes  = df_filtrado["AGN_IN_CODIGO"].nunique() if "AGN_IN_CODIGO" in df_filtrado.columns else 0

    cores_natureza = {"Todos": "#6366f1", "Efetuado": "#4A7FB5", "Recebido": "#2ECC71"}
    cor_situacao = cores_natureza.get(situacao_sel, "#6366f1")

    with cards_box:
        col_a, col_b, col_c, _ = st.columns([1, 1, 1, 1.6])
        with col_a:
            st.markdown(
                card_indicador(
                    titulo=f"Total {situacao_sel}",
                    valor=_formatar_moeda(total_lancado),
                    cor=cor_situacao,
                    subtitulo=f"{qtd_lancamentos} lançamento(s)",
                    icone="",
                    delay=0.0,
                ),
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown(
                card_indicador(
                    titulo="Saldo em Aberto",
                    valor=_formatar_moeda(total_saldo),
                    cor="#E8724A",
                    subtitulo="saldo pendente no período",
                    icone="⏳",
                    delay=0.05,
                ),
                unsafe_allow_html=True,
            )
        with col_c:
            st.markdown(
                card_indicador(
                    titulo="Agentes no período",
                    valor=str(qtd_agentes),
                    cor="#6366f1",
                    subtitulo="agentes com adiantamento",
                    icone="",
                    delay=0.1,
                ),
                unsafe_allow_html=True,
            )

    st.divider()

    # Ranking por agente desativado por enquanto (a pedido).
    # Para reativar: descomentar as duas linhas abaixo.
    # st.markdown("#### Ranking — Saldo em Aberto por Agente")
    # _ranking_agentes(df_total_agente, natureza_filtro)

    # ── Exportação ─────────────────────────────────────────────────────────
    colunas_origem = {
        "ORGANIZACAO": "Organização",
        "AGN_IN_CODIGO": "Cód. Agente",
        "AGENTE": "Agente",
        "NATUREZA": "Natureza",
        "MOV_ST_DOCUMENTO": "Documento",
        "MOV_DT_DATADOCTO": "Data",
        "MOV_RE_VALOR": "Valor Lançado",
        "SALDO": "Saldo em Aberto",
        "SITUACAO": "Situação",
        "COMPLEMENTO": "Complemento",
    }
    colunas_existentes = [c for c in colunas_origem if c in df_filtrado.columns]

    # df_excel: valores numéricos crus (moeda como número real) — vai para o Excel.
    df_excel = df_filtrado[colunas_existentes].copy()
    if "NATUREZA" in df_excel.columns:
        df_excel["NATUREZA"] = df_excel["NATUREZA"].astype(str).str.title()
    if "COMPLEMENTO" in df_excel.columns:
        df_excel["COMPLEMENTO"] = df_excel["COMPLEMENTO"].fillna("-").replace("", "-")
    df_excel = df_excel.rename(columns=colunas_origem)

    # df_img: valores formatados como texto — vai para a imagem PNG e a tela.
    df_img = df_filtrado[colunas_existentes].copy()
    if "NATUREZA" in df_img.columns:
        df_img["NATUREZA"] = df_img["NATUREZA"].astype(str).str.title()
    if "MOV_RE_VALOR" in df_img.columns:
        df_img["MOV_RE_VALOR"] = df_img["MOV_RE_VALOR"].apply(_formatar_moeda)
    if "SALDO" in df_img.columns:
        df_img["SALDO"] = df_img["SALDO"].apply(_formatar_moeda)
    if "MOV_DT_DATADOCTO" in df_img.columns:
        df_img["MOV_DT_DATADOCTO"] = pd.to_datetime(
            df_img["MOV_DT_DATADOCTO"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")
    if "COMPLEMENTO" in df_img.columns:
        df_img["COMPLEMENTO"] = df_img["COMPLEMENTO"].fillna("-").replace("", "-")
    df_img = df_img.rename(columns=colunas_origem)

    st.markdown(f"#### Adiantamentos — {situacao_sel}")

    _adto_img_key = (situacao_sel, busca_agente, str(sorted(orgs_selecionadas)),
                     str(data_de), str(data_ate), len(df_filtrado))
    _img_cache  = st.session_state.get("_adto_img_cache", {})
    _img_pronta = _img_cache.get("key") == _adto_img_key

    def _gerar_e_cachear():
        _cards = [
            {"label": f"Total {situacao_sel}", "valor": _formatar_moeda(total_lancado), "cor": (74, 127, 181)},
            {"label": "Saldo em Aberto",       "valor": _formatar_moeda(total_saldo),   "cor": (232, 114, 74)},
            {"label": "Agentes no período",    "valor": str(qtd_agentes),               "cor": (99, 102, 241)},
        ]
        with st.spinner("Gerando imagem…"):
            _img = _gerar_imagem_adto_cached(
                titulo_principal=f"Adiantamentos — {situacao_sel}",
                cards_resumo=_cards,
                df_titulos=df_img,
                titulo_tabela=f"Adiantamentos — {situacao_sel}",
                destacar_vencidos=False,
                ordem_colunas=list(colunas_origem.values()),
                largura_imagem=1700,
            )
        st.session_state["_adto_img_cache"] = {"key": _adto_img_key, "img": _img}
        return _img

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    col1, col2, col3, _ = st.columns([1, 1, 1, 3], gap="small")
    with col1:
        arquivo_excel = exportar_excel(df_excel, "ADIANTAMENTOS")
        botao_exportar_excel(
            arquivo_excel,
            f"Adiantamentos_{situacao_sel}.xlsx",
            key="adto_export_excel",
            use_container_width=True,
            label="Excel",
        )

    with col2:
        if _img_pronta:
            botao_salvar_imagem(
                _img_cache["img"],
                f"Adiantamentos_{situacao_sel}.png",
                key="adto_export_imagem",
            )
        else:
            if st.button("Salvar Imagem", key="adto_btn_salvar",
                         use_container_width=True, icon=":material/image:"):
                _gerar_e_cachear()
                st.rerun()

    with col3:
        if _img_pronta:
            render_botao_copiar_imagem(_img_cache["img"], key="adto_copiar")
        else:
            if st.button("Copiar Imagem", key="adto_btn_copiar",
                         use_container_width=True, icon=":material/content_copy:"):
                _gerar_e_cachear()
                st.rerun()

    # ── Tabela ────────────────────────────────────────────────────────────
    render_tabela_html(df_img)
