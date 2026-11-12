import streamlit as st
import pandas as pd
import plotly.express as px
from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from services.data_service import aplicar_filtros_comuns
from utils.exporters import exportar_excel


def render(df_vencidas: pd.DataFrame, atualizar=None):
    df_filtrado = aplicar_filtros_comuns(df_vencidas, chave="vencidas", atualizar=atualizar)

    if len(df_filtrado) == 0:
        st.markdown("### APs Vencidas — Contas a Pagar")
        st.info("Selecione os filtros na barra lateral e clique em **Filtrar**.")
        return

    # Calcular total ANTES de formatar
    total = pd.to_numeric(df_filtrado["SALDO"], errors="coerce").sum() if "SALDO" in df_filtrado.columns else 0
    total_fmt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Ordenar por data
    if "PRORROGADO" in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values("PRORROGADO")

    # Formatar datas
    for col in ["EMISSAO", "PRORROGADO"]:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")

    # Formatar valores
    for col in ["VALOR", "SALDO"]:
        if col in df_filtrado.columns:
            df_filtrado[col] = pd.to_numeric(df_filtrado[col], errors="coerce").apply(
                lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else ""
            )

    # ── Título + botão ocultar ────────────────────────────────────────────────
    if "vencidas_ocultar" not in st.session_state:
        st.session_state["vencidas_ocultar"] = False

    _oc_v = st.session_state["vencidas_ocultar"]
    col_t, col_btn, col_atualizar = st.columns([9, 1.4, 1.4])
    with col_t:
        st.title("APs Vencidas — Contas a Pagar")
    with col_btn:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button(
            "Ocultar" if not _oc_v else "Exibir",
            icon=":material/visibility_off:" if not _oc_v else ":material/visibility:",
            key="btn_ocultar_vencidas", use_container_width=True,
            help="Ocultar/exibir valores",
        ):
            st.session_state["vencidas_ocultar"] = not _oc_v
            st.rerun()
    with col_atualizar:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="vencidas_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    ocultar = st.session_state["vencidas_ocultar"]
    valor_exibir = "••••••" if ocultar else total_fmt

    # ── Cards ─────────────────────────────────────────────────────────────────
    filiais = df_filtrado["FILIAL"].nunique() if "FILIAL" in df_filtrado.columns else "-"

    render_cards_row([
        card_html("Qtd. APs Vencidas", len(df_filtrado), cor_borda="#E24B4A"),
        card_html("Total Vencido", valor_exibir, cor_borda="#BA7517"),
        card_html("Filiais com Vencidos", filiais, cor_borda="#1E88E5"),
    ])

    st.divider()

    # ── Resumo por Filial (substituindo ORGANIZACAO) ──────────────────────────
    if "FILIAL" in df_filtrado.columns:
        resumo = (
            df_filtrado
            .groupby("FILIAL", as_index=False)
            .agg(qtd_vencidos=("AP", "count"))
            .rename(columns={"qtd_vencidos": "Quantidade de Vencidos"})
            .sort_values("Quantidade de Vencidos", ascending=False)
        )

        st.subheader("Resumo por Filial")
        render_tabela_html(resumo)

        def _grafico(df_chart, col_y, col_x, titulo):
            df_chart = df_chart.sort_values(col_x, ascending=True)
            max_val = df_chart[col_x].max()
            fig = px.bar(
                df_chart, x=col_x, y=col_y, orientation="h",
                color=col_x,
                color_continuous_scale="Reds",
                labels={col_x: "Quantidade", col_y: ""},
                text=col_x,
            )
            fig.update_traces(textposition="outside", textfont=dict(size=13, color="#e0e0e0"))
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e0e0",
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=0, b=0),
                height=max(300, len(df_chart) * 36),
                xaxis=dict(showgrid=False, showticklabels=False, range=[0, max_val * 1.4]),
            )
            fig.update_yaxes(tickfont=dict(size=12), automargin=True)
            st.caption(titulo)
            st.plotly_chart(fig, use_container_width=True)

        if "TIPO_DOCTO" in df_filtrado.columns:
            resumo_tipo = (
                df_filtrado
                .groupby("TIPO_DOCTO", as_index=False)
                .agg(Quantidade=("AP", "count"))
            )
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                _grafico(resumo_tipo, "TIPO_DOCTO", "Quantidade", "Quantidade por Tipo de Documento")
            with col_g2:
                _grafico(resumo, "FILIAL", "Quantidade de Vencidos", "Quantidade por Filial")

    st.divider()

    colunas_visuais = [
        "FILIAL", "AP", "DOCTO", "PARC", "TIPO_DOCTO",
        "FAVORECIDO", "VALOR", "SALDO", "DIAS",
        "EMISSAO", "PRORROGADO", "SOLICITANTE"
    ]
    colunas_visuais = [c for c in colunas_visuais if c in df_filtrado.columns]

    st.subheader("APs Vencidas")
    _df_vis = df_filtrado[colunas_visuais].copy()
    for _col in ("VALOR", "SALDO"):
        if _col in _df_vis.columns:
            _df_vis[_col] = _df_vis[_col].apply(
                lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(v) else "—"
            )
    render_tabela_html(_df_vis, coluna_dias="DIAS", colunas_moeda=["VALOR", "SALDO"])

    arquivo_excel = exportar_excel(df_filtrado[colunas_visuais], "APS_VENCIDAS")
    botao_exportar_excel(arquivo_excel, "APs_Vencidas.xlsx", key="venc_export")
