"""
views/relatorio_conferencia_matriz_filial.py
==============================================
Aba "Conferência Matriz x Filial" do relatório Fretes Mot - Matriz x Filial: confere par a par o que a Demo efetuou e o que a Filial recebeu, em conhecimentos (CONHEC x CRECEBER, baixa no
mesmo dia) e adiantamentos (ação 55 x lançamento 981, com classe, centro de custo e projeto iguais). O período (data de prorrogação) é o do relatório Fretes Mot,
escolhido na barra lateral dele, e só ele vai ao banco. As pendências ficam no topo, e o Excel traz o que está na tela. Regras em
services/conferencia_matriz_filial.py.
"""

import datetime
from html import escape
from io import BytesIO

import pandas as pd
import streamlit as st
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row
from services.data_service import carregar_conferencia_matriz_filial

# coluna da conferência -> título exibido (mesma ordem do Excel)
_COLUNAS = {
    "GRUPO": "Grupo", "LADO": "Lado", "ORG": "Organização", "TIPO_DOCTO": "Tipo Docto", "AP": "AP", "DOCTO": "Docto", "FAVORECIDO": "Favorecido", "VALOR": "Valor",
    "SALDO": "Saldo", "STATUS": "Status", "DATA": "Baixa/Prorrogação", "ACAO": "Ação", "RATEIO_CLASSES": "Rateio Classes",
    "RATEIO_CENTRO_CUSTO": "Rateio Centro de Custo", "RATEIO_PROJETO": "Rateio Projeto", "SOLICITANTE": "Solicitante", "CONFERENCIA": "Conferência",
}
_LARGURAS = [14, 11, 46.7, 12, 10, 12, 44, 14, 13, 12, 19.7, 47.9, 53.1, 58.4, 40.9, 16, 39]


_RATEIOS = ("RATEIO_CLASSES", "RATEIO_CENTRO_CUSTO", "RATEIO_PROJETO")


def _larg_rateio(df: pd.DataFrame, col: str) -> int:
    """Largura (em caracteres) da coluna de rateio: a do texto da primeira linha; o que passar disso é cortado (o texto inteiro fica no passar do mouse)."""
    primeira = df[col].dropna()
    texto = str(primeira.iloc[0]).split("|")[0].strip() if len(primeira) else ""          # com vários rateios (separados por " | ") vale só o primeiro
    return max(len(texto) if texto else 20, 12)


def _larg_nome(df: pd.DataFrame, col: str, titulo: str) -> float:
    """Largura da coluna de nome (Organização, Favorecido): a do maior nome, com folga para o botão do filtro."""
    maior = int(df[col].dropna().astype(str).str.len().max()) if df[col].notna().any() else 0
    return max(maior, len(titulo) + 3) + 3


def _moeda(v) -> str:
    return "" if pd.isna(v) else f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cor_conferencia(texto: str, categoria: str) -> str:
    return "#6fd69a" if categoria == "OK" else "#f5c070" if categoria == "AGUARDANDO" else "#f3a3a2"


def _resumo_pendencias(df: pd.DataFrame) -> str:
    """Texto do cartão de pendências: quantos pares de cada tipo."""
    pend = df[df["CATEGORIA"] == "PENDENCIA"].drop_duplicates("GRUPO_ID")["CONFERENCIA"]
    partes = []
    for rotulo, teste in (("falta baixar na Filial", lambda t: t.startswith("FALTA BAIXAR")), ("falta lançar o 981", lambda t: "FALTA LANÇAR O 981" in t),
                          ("baixa em dia diferente", lambda t: t.startswith("BAIXA EM DIA")), ("diferenças de classe, centro de custo ou projeto",
                                                                                              lambda t: t.startswith("DIFERENTE") and "FALTA LANÇAR O 981" not in t)):
        n = int(pend.map(teste).astype(bool).sum()) if len(pend) else 0
        if n:
            partes.append(f"{n} {rotulo}")
    return " · ".join(partes) if partes else "nenhuma pendência"


def _html_tabela(df: pd.DataFrame) -> str:
    cab = "".join(f"<th>{escape(t)}</th>" for t in _COLUNAS.values())
    linhas = []
    larg = {c: _larg_rateio(df, c) for c in _RATEIOS}
    ids = list(dict.fromkeys(df["GRUPO_ID"]))                       # ordem dos pares na tela: o fundo alterna de um par para o outro
    posicao = {gid: i for i, gid in enumerate(ids)}
    anterior = None
    for r in df.itertuples(index=False):
        rd = r._asdict()
        banda = " class='b'" if posicao[rd["GRUPO_ID"]] % 2 == 0 else ""
        topo = " style='border-top:1px solid #3a4160'" if rd["GRUPO_ID"] != anterior else ""
        anterior = rd["GRUPO_ID"]
        tds = []
        for col in _COLUNAS:
            v = rd[col]
            if col in ("VALOR", "SALDO"):
                tds.append(f"<td class='r'>{_moeda(v)}</td>")
            elif col == "DATA":
                tds.append("<td></td>" if pd.isna(v) else f"<td>{pd.Timestamp(v):%d/%m/%Y}</td>")
            elif col == "STATUS":
                tds.append(f"<td class='st {'ab' if v == 'EM ABERTO' else 'bx'}'>{escape(str(v))}</td>")
            elif col == "CONFERENCIA":
                tds.append(f"<td style='text-align:center;color:{_cor_conferencia(str(v), rd['CATEGORIA'])};font-weight:600'>{escape(str(v))}</td>")
            elif col == "AP":
                tds.append(f"<td>{'' if pd.isna(v) else int(v)}</td>")
            elif col in _RATEIOS:
                txt = "" if v is None or (isinstance(v, float) and pd.isna(v)) else escape(str(v))
                px = int(larg[col] * 7.4 + 20)
                tds.append(f"<td style='width:{px}px;min-width:{px}px;max-width:{px}px;overflow:hidden;text-overflow:ellipsis' title='{txt}'>{txt}</td>")
            else:
                tds.append(f"<td>{'' if v is None or (isinstance(v, float) and pd.isna(v)) else escape(str(v))}</td>")
        linhas.append(f"<tr{banda}{topo}>{''.join(tds)}</tr>")
    css = ("<style>.rci{max-height:560px;overflow:auto;border-radius:8px;background:#1e1e2e;margin-bottom:12px}"
           ".rci table{border-collapse:collapse;font-size:12.5px;color:#e0e0e0;table-layout:auto}"
           ".rci th{position:sticky;top:0;background:#1B3A6B;color:#fff;font-weight:500;text-align:left;padding:7px 9px;white-space:nowrap;z-index:1}"
           ".rci td{padding:5px 9px;white-space:nowrap}.rci tr.b td{background:rgba(55,138,221,.16)}.rci td.r{text-align:right}"
           ".rci td.st{text-align:center;font-weight:700}.rci td.st.bx{color:#4fa3e0}.rci td.st.ab{color:#f5c070}</style>")
    return css + f"<div class='rci'><table><thead><tr>{cab}</tr></thead><tbody>{''.join(linhas)}</tbody></table></div>"


def _gerar_excel(df: pd.DataFrame) -> bytes:
    """Aba única "Conferência": pares com o fundo alternando azul e branco, Status em azul (baixado) e amarelo (em aberto), larguras fixas, título e filtro."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Conferência"
    titulos = list(_COLUNAS.values())
    ws.append(titulos)
    cab_fill, banda = PatternFill("solid", fgColor="1F3864"), PatternFill("solid", fgColor="DCE6F1")
    for c in ws[1]:
        c.fill, c.font, c.alignment = cab_fill, Font(bold=True, color="FFFFFF"), Alignment(horizontal="center", vertical="center", wrap_text=False)
    fundo_status = {"EM ABERTO": PatternFill("solid", fgColor="FFEB9C"), "BAIXADO": PatternFill("solid", fgColor="95B3D7")}
    cor_texto_conf = {"OK": "00B050", "AGUARDANDO": "C58B00", "PENDENCIA": "FF0000"}
    ids = list(dict.fromkeys(df["GRUPO_ID"]))
    posicao = {gid: i for i, gid in enumerate(ids)}
    linha_topo = Side(style="thin", color="7F7F7F")
    anterior = None
    col_status = titulos.index("Status") + 1
    for r in df.itertuples(index=False):
        rd = r._asdict()
        valores = []
        for col in _COLUNAS:
            v = rd[col]
            if col == "DATA":
                v = None if pd.isna(v) else pd.Timestamp(v).to_pydatetime()
            elif col == "AP":
                v = None if pd.isna(v) else int(v)
            elif v is not None and isinstance(v, float) and pd.isna(v):
                v = None
            valores.append(v)
        ws.append(valores)
        n = ws.max_row
        faixa = posicao[rd["GRUPO_ID"]] % 2 == 0
        for j, c in enumerate(ws[n], 1):
            if faixa and j != col_status:
                c.fill = banda
            if isinstance(c.value, float):
                c.number_format = "#,##0.00"
            elif hasattr(c.value, "year"):
                c.number_format = "DD/MM/YYYY"
            c.alignment = Alignment(wrap_text=False, vertical="center")
            if rd["GRUPO_ID"] != anterior:
                c.border = Border(top=linha_topo)
        anterior = rd["GRUPO_ID"]
        sc = ws.cell(n, col_status)
        sc.fill = fundo_status.get(rd["STATUS"], sc.fill)
        sc.alignment = Alignment(horizontal="center", vertical="center")
        if rd["STATUS"] == "EM ABERTO":
            sc.font = Font(color="9C5700")
        cc = ws.cell(n, titulos.index("Conferência") + 1)
        cc.font = Font(bold=True, color=cor_texto_conf[rd["CATEGORIA"]])
        cc.alignment = Alignment(horizontal="center", vertical="center")
    for i, (col, w) in enumerate(zip(_COLUNAS, _LARGURAS), 1):
        ws.column_dimensions[get_column_letter(i)].width = _larg_rateio(df, col) + 2 if col in _RATEIOS else _larg_nome(df, col, titulos[i - 1]) if col in ("ORG", "FAVORECIDO") else w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(titulos))}{ws.max_row}"
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def render_corpo(dt_ini: datetime.date, dt_fim: datetime.date) -> None:
    """Conteúdo da aba Conferência do relatório Fretes Mot - Matriz x Filial: usa o período (prorrogação) e o botão Gerar Relatório da barra lateral dele."""
    with st.spinner("Conferindo os lançamentos do período..."):
        df = carregar_conferencia_matriz_filial(dt_ini.strftime("%d/%m/%Y"), dt_fim.strftime("%d/%m/%Y"))
    if df is None or df.empty:
        st.info(f"Nenhum conhecimento ou adiantamento com prorrogação entre {dt_ini:%d/%m/%Y} e {dt_fim:%d/%m/%Y}.")
        return
    df = df.assign(GRUPO=df["GRUPO"].replace({"Conhecimento": "Pagamento"}))          # na tela e no Excel o conhecimento aparece como Pagamento
    grupos = st.session_state.get("rci_grupo") or []          # filtro Grupo fica na barra lateral (views/relatorio_fretes_mot_matriz_filial.py)
    if grupos:
        df = df[df["GRUPO"].isin(grupos)]
        if df.empty:
            st.info("Nenhum lançamento para o grupo escolhido.")
            return

    pares = df.drop_duplicates("GRUPO_ID")
    n_pend, n_ok, n_ag = (int((pares["CATEGORIA"] == c).sum()) for c in ("PENDENCIA", "OK", "AGUARDANDO"))
    render_cards_row([
        card_html("Pendências", str(n_pend), _resumo_pendencias(df), cor_borda="#E24B4A", largura="320px"),
        card_html("Conferidos (OK)", str(n_ok), "pares iguais nos dois lados", cor_borda="#22c55e", largura="280px"),
        card_html("Aguardando pagamento", str(n_ag), "ainda em aberto na Demo", cor_borda="#BA7517", largura="280px"),
    ])

    st.caption(f"{df['GRUPO_ID'].nunique()} par(es) · {len(df)} linha(s) · prorrogado de {dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}")
    st.html(_html_tabela(df))
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    col_excel, _ = st.columns([1, 5], gap="small")          # botão compacto, do tamanho do padrão dos outros relatórios
    with col_excel:
        botao_exportar_excel(
            lambda: _gerar_excel(df),
            f"Conferencia_Demo_x_Filial_{dt_ini:%d-%m-%Y}_a_{dt_fim:%d-%m-%Y}.xlsx",
            key="rci_excel", use_container_width=True, label="Excel", help="Excel com o que está na tela: pares alternando azul e branco, Status colorido",
        )
