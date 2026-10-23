import html as _html
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.exporters import exportar_excel_contas_pagar


_COLUNAS_RATEIO_CAP = ("RATEIO_CLASSES", "RATEIO_CENTRO_CUSTO", "RATEIO_PROJETO")


def _separa_favorecido(df: pd.DataFrame) -> pd.DataFrame:
    """Divide "123 - NOME" em duas colunas: CÓD_FORNEC (123) e FORNECEDOR (NOME)."""
    if "FAVORECIDO" not in df.columns:
        return df
    partes = df["FAVORECIDO"].astype(str).str.extract(r"^\s*(\d+)\s-\s(.*)$")
    df = df.copy()
    pos = list(df.columns).index("FAVORECIDO")
    df.insert(pos, "CÓD_FORNEC", partes[0].fillna(""))
    df["FAVORECIDO"] = partes[1].fillna(df["FAVORECIDO"])
    return df.rename(columns={"FAVORECIDO": "FORNECEDOR"})


def _rateio_clicavel(valor) -> str:
    """Rateio em uma linha só (como no Excel). Com mais de uma linha, clicar expande e mostra cada uma."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    partes = [p.strip() for p in str(valor).split(chr(10)) if p.strip()]
    if not partes:
        return ""
    if len(partes) == 1:
        return _html.escape(partes[0])
    resumo = _html.escape("  ".join(partes)).replace("  ", "&nbsp;&nbsp;")
    lista = "<br>".join(_html.escape(p) for p in partes)
    return (
        '<details><summary style="display:block;max-width:420px;white-space:nowrap;overflow:hidden;'
        'text-overflow:ellipsis;cursor:pointer;list-style:none">' + resumo + '</summary>'
        '<div style="margin-top:4px">' + lista + '</div></details>'
    )


def formatar_moeda(valor) -> str:
    try:
        v = float(valor)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def render(df: pd.DataFrame, carregar_desde=None, data_corte=None, atualizar=None):
    if df.empty:
        st.warning("Nenhum dado encontrado para Contas a Pagar.")
        return

    df = df.copy()

    # ── Filtros na barra lateral (organização, status e período) ──────────────────────
    with st.sidebar:
        orgs = st.multiselect(
            "Organização",
            sorted(df["ORG"].dropna().unique()) if "ORG" in df.columns else [],
            key="cap_org",
        )
        tipos_sel = st.multiselect(
            "Tipo de classificação",
            ["Produtor", "Fornecedor"],
            default=["Produtor", "Fornecedor"],
            key="cap_tipo_classif",
        )
        opcoes_status = sorted(df["STATUS"].dropna().unique()) if "STATUS" in df.columns else []
        status_sel = st.multiselect(
            "Status",
            opcoes_status,
            default=[s for s in ("VENCIDO", "A VENCER") if s in opcoes_status],
            key="cap_status",
        )
        hoje = date.today()
        data_inicio = st.date_input(
            "Data inicial", value=hoje.replace(day=1), format="DD/MM/YYYY", key="cap_data_ini"
        )
        data_fim = st.date_input(
            "Data final", value=hoje, format="DD/MM/YYYY", key="cap_data_fim"
        )
        gerar = st.button("Gerar Relatório", width="stretch", key="cap_btn_gerar")

    if gerar:
        st.session_state["_cap_gerou"] = True
        if atualizar and atualizar():
            st.rerun()

    if not st.session_state.get("_cap_gerou"):
        st.markdown("### Contas a Pagar")
        st.info("Escolha os filtros na barra lateral e clique em **Gerar Relatório**.")
        return

    # ── Cabeçalho + ocultar ───────────────────────────────────────────────────
    if "cap_ocultar" not in st.session_state:
        st.session_state["cap_ocultar"] = False

    _oc_cap = st.session_state["cap_ocultar"]
    col_t, col_btn, col_atualizar = st.columns([9, 1.4, 1.4])
    with col_t:
        if data_inicio and data_fim:
            st.title(f"Contas a Pagar — {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        else:
            st.title("Contas a Pagar")
    with col_btn:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button(
            "🙈 Ocultar" if not _oc_cap else "👁 Exibir",
            key="cap_btn_ocultar", use_container_width=True,
            help="Ocultar/exibir valores",
        ):
            st.session_state["cap_ocultar"] = not _oc_cap
    with col_atualizar:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="cap_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    ocultar = st.session_state["cap_ocultar"]

    if not (data_inicio and data_fim):
        st.info("Informe a **Data inicial** e a **Data final** na barra lateral.")
        return

    # Período anterior à data de corte: busca de novo a partir da Data inicial.
    if carregar_desde and data_corte and data_inicio < data_corte:
        with st.spinner(f"Buscando dados desde {data_inicio.strftime('%d/%m/%Y')}..."):
            df = carregar_desde(data_inicio.isoformat())
        if df.empty:
            st.info("Nenhum registro encontrado para o período.")
            return

    df_filtrado = df.copy()
    if orgs:
        df_filtrado = df_filtrado[df_filtrado["ORG"].isin(orgs)]
    if tipos_sel and "TIPO_CLASSIFICACAO" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["TIPO_CLASSIFICACAO"].isin(tipos_sel)]
    if status_sel:
        df_filtrado = df_filtrado[df_filtrado["STATUS"].isin(status_sel)]
    if "PRORROGADO" in df_filtrado.columns:
        datas = pd.to_datetime(df_filtrado["PRORROGADO"], errors="coerce")
        df_filtrado = df_filtrado[
            (datas >= pd.to_datetime(data_inicio)) &
            (datas <= pd.to_datetime(data_fim))
        ]

    st.divider()

    if df_filtrado.empty:
        st.info("Nenhum registro encontrado com os filtros selecionados.")
        return

    df_filtrado = _separa_favorecido(df_filtrado)

    # ── Cards: só quantidade, sem valor ──────────────────────────────────────
    qtd_vencidos = int((df_filtrado["STATUS"] == "VENCIDO").sum()) if "STATUS" in df_filtrado.columns else 0
    qtd_a_vencer = int((df_filtrado["STATUS"] == "A VENCER").sum()) if "STATUS" in df_filtrado.columns else 0
    qtd_erros    = int(df_filtrado["CATEGORIA_ERRO"].notna().sum()) if "CATEGORIA_ERRO" in df_filtrado.columns else 0

    render_cards_row([
        card_html("Qtd. Títulos Vencidos", str(qtd_vencidos), cor_borda="#E24B4A"),
        card_html("Qtd. Títulos a Vencer", str(qtd_a_vencer), cor_borda="#22c55e"),
        card_html("APs com Erro", str(qtd_erros), cor_borda="#BA7517"),
    ])

    st.divider()

    # ── Tabela detalhada ──────────────────────────────────────────────────────
    # Ordem fixa das colunas (tela e Excel) — campos que não estão na lista entram
    # no fim, na ordem em que a consulta devolve, para nada sumir do relatório.
    _ORDEM_COLUNAS = [
        "ORG", "FILIAL", "AP", "APROVACAO", "APROVADORES", "DOCTO", "PARC",
        "TIPO_DOCTO", "TIPO_FAVORECIDO", "TIPO_CLASSIFICACAO", "CÓD_FORNEC", "FORNECEDOR", "VALOR", "SALDO", "STATUS",
        "DIAS", "EMISSAO", "ENTRADA", "VENCTO", "PRORROGADO", "FORMA_PAGTO", "PIX",
        "LINHA_DIGITAVEL", "COMPLEMENTO", "ACAO", "RATEIO_CLASSES", "RATEIO_CENTRO_CUSTO",
        "RATEIO_PROJETO", "CATEGORIA_ERRO", "SOLICITANTE", "STATUS_ANEXO",
        "QTD_ANEXOS", "NOME_ANEXO", "STATUS_DIAS", "FAIXA_DIAS",
    ]
    colunas_visuais = [c for c in _ORDEM_COLUNAS if c in df_filtrado.columns]
    colunas_visuais += [c for c in df_filtrado.columns if c not in colunas_visuais]

    df_exib = df_filtrado[colunas_visuais].copy()
    for _c in _COLUNAS_RATEIO_CAP:
        if _c in df_exib.columns:
            df_exib[_c] = df_exib[_c].apply(_rateio_clicavel)
    # complemento em uma linha só: quebras de linha viram espaço
    if "COMPLEMENTO" in df_exib.columns:
        df_exib["COMPLEMENTO"] = df_exib["COMPLEMENTO"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    for col in ["EMISSAO", "ENTRADA", "VENCTO", "PRORROGADO"]:
        if col in df_exib.columns:
            df_exib[col] = pd.to_datetime(df_exib[col], errors="coerce").dt.strftime("%d/%m/%Y")

    if ocultar:
        for col in ["VALOR", "SALDO"]:
            if col in df_exib.columns:
                df_exib[col] = "••••••"
    else:
        for col in ["VALOR", "SALDO"]:
            if col in df_exib.columns:
                df_exib[col] = pd.to_numeric(df_filtrado[col], errors="coerce").apply(formatar_moeda)

    # Sem coloração de linha na tela — pandas Styler é lento em volume grande
    # (roda uma função Python por linha). O Excel exportado já tem cor por
    # status própria (formatação condicional nativa do openpyxl).
    st.subheader("Detalhe")
    render_tabela_html(df_exib, colunas_moeda=["VALOR", "SALDO"], colunas_cinza=["COMPLEMENTO"])

    excel_bytes = exportar_excel_contas_pagar(df_filtrado[colunas_visuais])
    botao_exportar_excel(
        excel_bytes,
        f"Contas a Pagar {data_inicio.strftime('%d-%m-%Y')} a {data_fim.strftime('%d-%m-%Y')}.xlsx",
        key="cap_export",
    )
