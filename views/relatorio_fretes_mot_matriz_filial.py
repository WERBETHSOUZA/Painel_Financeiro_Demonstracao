"""
views/relatorio_fretes_mot_matriz_filial.py
=============================================
Relatório "Fretes Mot - Matriz x Filial": contas a pagar das organizações 6 (Demo) e 42500 (Filial) para a
Transportadora Filial (42501) e a Siderúrgica (678), com o rateio por classe, centro de custo e projeto
(QUERY_FRETES_MOT_DEMO_FILIAL.sql). O período (data de prorrogação, dia final incluído; abre no mês vigente) é escolhido
na barra lateral e só ele vai ao banco. Os rateios ficam em uma linha só (separados por " | ").
"""

import calendar
import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from components.buttons import botao_exportar_excel
from components.cards import render_tabela_html
from services.data_service import carregar_fretes_mot_matriz_filial
from utils.exporters import exportar_excel

# coluna da consulta -> título exibido (mesma ordem do SELECT)
_COLUNAS = {
    "ORG":                 "ORG",
    "TIPO_DOCTO":          "Tipo Docto",
    "AP":                  "AP",
    "DOCTO":               "Docto",
    "FAVORECIDO":          "Favorecido",
    "VALOR":               "Valor",
    "SALDO":               "Saldo",
    "STATUS":              "Status",
    "PRORROGADO":          "Prorrogado",
    "ACAO":                "Ação",
    "RATEIO_CLASSES":      "Rateio Classes",
    "RATEIO_CENTRO_CUSTO": "Rateio Centro de Custo",
    "RATEIO_PROJETO":      "Rateio Projeto",
    "SOLICITANTE":         "Solicitante",
}
_COR_STATUS = {"BAIXADO": "#4fa3e0", "VENCIDO": "#E24B4A", "NO PRAZO": "#22c55e"}
_COLUNAS_RATEIO = ("Rateio Classes", "Rateio Centro de Custo", "Rateio Projeto")
_LARGURAS = {"ORG": 8, "Tipo Docto": 12, "AP": 9, "Docto": 14, "Favorecido": 42, "Valor": 15, "Saldo": 15, "Status": 12,
             "Prorrogado": 12, "Ação": 48, "Rateio Classes": 42, "Rateio Centro de Custo": 38, "Rateio Projeto": 34,
             "Solicitante": 18}


def _formatar_numero(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _ajustar_excel(xlsx: bytes) -> bytes:
    """Larguras das colunas do Excel."""
    wb = load_workbook(BytesIO(xlsx))
    ws = wb.active
    for idx, cel in enumerate(ws[1], start=1):
        if cel.value in _LARGURAS:
            ws.column_dimensions[get_column_letter(idx)].width = _LARGURAS[cel.value]
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def render() -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Fretes Mot - Matriz x Filial")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        # Callback: com st.rerun no meio da página os filtros da barra lateral seriam esquecidos
        st.button("🔄 Atualizar", key="rfm_atualizar", use_container_width=True, on_click=st.cache_data.clear)

    hoje = datetime.date.today()
    mes_vigente = (hoje.replace(day=1), hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]))
    with st.sidebar:
        st.caption("Fretes Mot - Matriz x Filial")
        periodo = st.date_input(
            "Prorrogado (período)", value=mes_vigente, format="DD/MM/YYYY", key="rfm_periodo",
            help="Data de prorrogação do título; abre no mês vigente. Só o período escolhido é buscado no banco; o dia final entra.",
        )
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rfm_gerar")

    if gerar:
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            st.session_state["_rfm_periodo"] = (periodo[0], periodo[1])
        else:
            st.session_state.pop("_rfm_periodo", None)
            st.warning("Selecione o período (data inicial e final) na barra lateral e clique em Gerar Relatório.")
            return

    periodo_sel = st.session_state.get("_rfm_periodo")
    if not periodo_sel:
        st.info("O período de prorrogação abre no **mês vigente**. Ajuste-o na barra lateral, se precisar, e clique em **Gerar Relatório**.")
        return
    dt_ini, dt_fim = periodo_sel

    with st.spinner("Carregando os fretes do período..."):
        df = carregar_fretes_mot_matriz_filial(dt_ini.strftime("%d/%m/%Y"), dt_fim.strftime("%d/%m/%Y"))
    if df is None or df.empty:
        st.info("Nenhum título no período selecionado.")
        return
    if not set(_COLUNAS).issubset(df.columns):
        st.warning("Dados incompletos para montar este relatório.")
        return

    df = df[list(_COLUNAS)].rename(columns=_COLUNAS)
    for col in ("Valor", "Saldo"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Prorrogado"] = pd.to_datetime(df["Prorrogado"], errors="coerce")
    # rateios: quando há mais de um item (a consulta separa por quebra de linha), ficam na mesma linha, separados por " | "
    for col in _COLUNAS_RATEIO:
        df[col] = df[col].fillna("").astype(str).str.replace(r"\s*[\r\n]+\s*", " | ", regex=True).str.strip()
    for col in ("ORG", "AP"):          # números de verdade (a consulta devolve texto ou número solto)
        _num = pd.to_numeric(df[col], errors="coerce")
        if _num.notna().all():
            df[col] = _num.astype("int64")

    st.caption(f"{len(df)} título(s) encontrado(s) · Prorrogado de {dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}")

    df_tela = df.copy()
    df_tela["Prorrogado"] = df_tela["Prorrogado"].dt.strftime("%d/%m/%Y").fillna("")
    for col in ("Valor", "Saldo"):
        df_tela[col] = df_tela[col].apply(_formatar_numero)
        # Status em texto colorido (como no Excel), sem selo: assim a linha tem a mesma altura do Relatório de Aprovação
    df_tela["Status"] = df_tela["Status"].map(lambda v: f'<span style="color:{_COR_STATUS.get(str(v).upper(), "#8892A4")};font-weight:600">{v}</span>')
    render_tabela_html(df_tela)   # mesma tabela e proporções do Relatório de Aprovação

    st.markdown("&nbsp;", unsafe_allow_html=True)
    arquivo = exportar_excel(
        df, "FRETES_MOT", colunas_moeda=("Valor", "Saldo"), colunas_situacao_sem_fundo=("Status",),
    )
    botao_exportar_excel(
        _ajustar_excel(arquivo),
        f"Fretes_Mot_Demo_x_Filial_{dt_ini:%d-%m-%Y}_a_{dt_fim:%d-%m-%Y}.xlsx",
        key="rfm_export",
    )
