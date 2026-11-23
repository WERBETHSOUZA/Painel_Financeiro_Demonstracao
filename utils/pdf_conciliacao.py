"""PDF das Pendências de Conciliação (A4 retrato): resumo por empresa (só quando há mais de uma), e, por empresa, os cards, o resumo por banco e o
detalhe de cada banco (Data, Docto Banco, Tipo Docto, Histórico, Valor, Natureza, Importação). Recebe o DataFrame da consulta
QUERY_PENDENCIAS_CONCILIACAO.sql (colunas em maiúsculas) já filtrado pela tela."""
import datetime
import re
from html import escape
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_NV, _NV2, _CL, _GY, _CC = (colors.HexColor(x) for x in ("#0D1C2E", "#1B3A6B", "#D6E4F7", "#F5F7FA", "#CCCCCC"))
_VD, _VM, _AM, _TX, _MU = (colors.HexColor(x) for x in ("#166534", "#991B1B", "#B45309", "#1A1A1A", "#5B6B80"))
_L = A4[0] - 3 * cm                      # largura útil


def nome_empresa(organizacao) -> str:
    """"WANTEL TECNOLOGIA - CONSOLIDADORA FISCAL" -> "WANTEL TECNOLOGIA" (o sufixo da consolidadora só confunde na tela e no PDF; o separador pode vir como caractere estranho do banco, por isso a regra corta tudo antes de CONSOLIDADORA)."""
    return re.sub(r"[\W_]*CONSOLIDADORA.*$", "", str(organizacao or ""), flags=re.I).strip() or str(organizacao or "")


def _br(v) -> str:
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ps(nome, size, bold=False, color=_TX, align=TA_LEFT, lead=None):
    return ParagraphStyle(nome, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, textColor=color, alignment=align, leading=lead or size * 1.25)


class _Numerado(rl_canvas.Canvas):
    """Rodapé com "Página x de y"."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._pgs = []

    def showPage(self):
        self._pgs.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._pgs)
        for st in self._pgs:
            self.__dict__.update(st)
            self.setFont("Helvetica", 7)
            self.setFillColor(colors.HexColor("#666666"))
            self.drawString(1.5 * cm, 1.0 * cm, "Painel Financeiro DEMO")
            self.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, f"Página {self._pageNumber} de {n}")
            super().showPage()
        super().save()


def _cabecalho(empresa: str, subtitulo: str, ini: datetime.date, fim: datetime.date) -> Table:
    t = Table([[Paragraph(f"<b>{escape(empresa)}</b>", _ps("e", 9, True, colors.white)),
                Paragraph(subtitulo, _ps("t", 11.5, True, colors.white, TA_CENTER)),
                Paragraph(f"Período: {ini:%d/%m/%Y} a {fim:%d/%m/%Y}<br/>Emitido em {datetime.datetime.now():%d/%m/%Y %H:%M}",
                          _ps("m", 7, color=colors.HexColor("#C9D6E8"), align=TA_RIGHT))]],
              colWidths=[_L * 0.26, _L * 0.48, _L * 0.26])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _NV), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 9),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    return t


def _card(titulo, valor, sub, cor, largura):
    t = Table([[Paragraph(titulo, _ps("ct", 7.5, color=_MU))], [Paragraph(f"<b>{valor}</b>", _ps("cv", 15, True, cor, lead=18))],
               [Paragraph(sub, _ps("cs", 7.5, color=_MU))]], colWidths=[largura])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _GY), ("LINEABOVE", (0, 0), (-1, 0), 3, cor), ("BOX", (0, 0), (-1, -1), 0.4, _CC),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 9)]))
    return t


def _cards(d: pd.DataFrame, rotulo_grupo: str) -> Table:
    cred = d["NATUREZA"].eq("Crédito")
    linha = Table([[_card("Lançamentos pendentes", str(len(d)), rotulo_grupo, _NV2, _L / 3 - 0.3 * cm),
                    _card("Débitos pendentes", f"R$ {_br(d.loc[~cred, 'VALOR'].sum())}", f"{int((~cred).sum())} lançamento(s)", _VM, _L / 3 - 0.3 * cm),
                    _card("Créditos pendentes", f"R$ {_br(d.loc[cred, 'VALOR'].sum())}", f"{int(cred.sum())} lançamento(s)", _VD, _L / 3 - 0.3 * cm)]],
                  colWidths=[_L / 3] * 3)
    linha.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return linha


def _estilo_tabela(n_linhas: int, total: bool = True) -> list:
    base = [("BACKGROUND", (0, 0), (-1, 0), _NV2), ("ROWBACKGROUNDS", (0, 1), (-1, -2 if total else -1), [colors.white, _GY]),
            ("LINEBELOW", (0, 1), (-1, -2 if total else -1), 0.3, _CC), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if total:
        base += [("BACKGROUND", (0, -1), (-1, -1), _CL), ("LINEABOVE", (0, -1), (-1, -1), 0.8, _NV2)]
    return base


_H, _HR = _ps("th", 7.5, True, colors.white), _ps("thr", 7.5, True, colors.white, TA_RIGHT)
_C0, _C1, _C2 = _ps("c0", 7.5), _ps("c1", 7.5, align=TA_RIGHT), _ps("c2", 7.5, True)
_C2R = _ps("c2r", 7.5, True, align=TA_RIGHT)


def _agrupar(d: pd.DataFrame, chaves: list) -> pd.DataFrame:
    cred = d["NATUREZA"].eq("Crédito")
    d = d.assign(_CRED=d["VALOR"].where(cred, 0.0), _DEB=d["VALOR"].where(~cred, 0.0), _MAN=d["DATA_IMPORTACAO"].isna().astype(int))
    return (d.groupby(chaves, as_index=False, dropna=False)
             .agg(QTD=("VALOR", "size"), CRED=("_CRED", "sum"), DEB=("_DEB", "sum"), MAN=("_MAN", "sum"), ANT=("DATA", "min"))
             .sort_values("QTD", ascending=False))


def _com_rotulo_banco(g: pd.DataFrame) -> pd.DataFrame:
    """Coluna BANCO = "código - nome da conta" (o código vem antes do nome no resumo e no título de cada bloco)."""
    return g.assign(BANCO=g["COD_BANCO"].map(lambda c: f"{int(c)}") + " - " + g["CONTA"].astype(str))


def _tabela_resumo(g: pd.DataFrame, coluna: str, rotulo: str, col_cod: str | None = None) -> Table:
    """Resumo (empresa ou banco); com `col_cod` ganha uma coluna "Cód." antes do nome."""
    cab = [Paragraph(rotulo, _H), Paragraph("Pend.", _HR), Paragraph("Créditos", _HR), Paragraph("Débitos", _HR), Paragraph("Man.", _HR), Paragraph("Mais antigo", _H)]
    lin = [([Paragraph("Cód.", _H)] if col_cod else []) + cab]
    for r in g.to_dict("records"):
        lin.append(([Paragraph(str(int(r[col_cod])), _C0)] if col_cod else []) + [Paragraph(escape(str(r[coluna])), _C0), Paragraph(str(r["QTD"]), _C1),
                    Paragraph(_br(r["CRED"]) if r["CRED"] else "—", _C1), Paragraph(_br(r["DEB"]) if r["DEB"] else "—", _C1), Paragraph(str(int(r["MAN"])), _C1),
                    Paragraph(f"{pd.Timestamp(r['ANT']):%d/%m/%Y}", _C0)])
    lin.append(([Paragraph("", _C2)] if col_cod else []) + [Paragraph("Total", _C2), Paragraph(str(int(g["QTD"].sum())), _C2R), Paragraph(_br(g["CRED"].sum()), _C2R),
                Paragraph(_br(g["DEB"].sum()), _C2R), Paragraph(str(int(g["MAN"].sum())), _C2R), Paragraph(f"{pd.Timestamp(g['ANT'].min()):%d/%m/%Y}", _C2)])
    larg = [0.07, 0.34, 0.07, 0.13, 0.15, 0.07, 0.17] if col_cod else [0.40, 0.07, 0.14, 0.16, 0.07, 0.16]
    t = Table(lin, colWidths=[_L * x for x in larg], repeatRows=1)
    t.setStyle(TableStyle(_estilo_tabela(len(lin))))
    return t


def _bloco_banco(conta: str, d: pd.DataFrame) -> list:
    d = d.sort_values(["DATA"], kind="stable")
    topo = Table([[Paragraph(f"<b>{escape(str(conta))}</b>", _ps("bt", 10, True, _NV2)),
                   Paragraph(f"{len(d)} lançamento(s) pendente(s)", _ps("bs", 7.5, color=_MU, align=TA_RIGHT))]], colWidths=[_L * 0.75, _L * 0.25])
    topo.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, _NV2), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    rows = [[Paragraph("Data", _H), Paragraph("Docto<br/>Banco", _H), Paragraph("Tipo<br/>Docto", _H), Paragraph("Histórico", _H), Paragraph("Valor", _HR),
             Paragraph("Natureza", _H), Paragraph("Importação", _H)]]
    nat_c, nat_d = _ps("nc", 7.5, color=_VD), _ps("nd", 7.5, color=_VM)
    manual = _ps("im", 7, True, _AM)
    for x in d.to_dict("records"):
        imp = Paragraph("Importação Manual", manual) if pd.isna(x["DATA_IMPORTACAO"]) else Paragraph(f"{pd.Timestamp(x['DATA_IMPORTACAO']):%d/%m/%Y %H:%M}", _C0)
        rows.append([Paragraph(f"{pd.Timestamp(x['DATA']):%d/%m/%Y}", _C0), Paragraph(escape(str(x["DOCTO_BANCO"] or "")), _C0),
                     Paragraph(escape(str(x["TIPO_DOCTO"] or "")), _C0), Paragraph(escape(str(x["HISTORICO"] or "")), _C0), Paragraph(_br(x["VALOR"]), _C1),
                     Paragraph(x["NATUREZA"], nat_c if x["NATUREZA"] == "Crédito" else nat_d), imp])
    tc, td = d.loc[d["NATUREZA"] == "Crédito", "VALOR"].sum(), d.loc[d["NATUREZA"] != "Crédito", "VALOR"].sum()
    resumo = " · ".join(p for p in ((f"Débitos: {_br(td)}" if td else ""), (f"Créditos: {_br(tc)}" if tc else "")) if p)
    rows.append([Paragraph("Total do banco", _C2), "", "", Paragraph(resumo, _ps("rs", 7.5, True)), "", "", ""])
    t = Table(rows, colWidths=[_L * 0.10, _L * 0.10, _L * 0.10, _L * 0.30, _L * 0.12, _L * 0.09, _L * 0.19], repeatRows=1)
    t.setStyle(TableStyle(_estilo_tabela(len(rows)) + [("SPAN", (0, -1), (2, -1)), ("SPAN", (3, -1), (-1, -1))]))
    bloco = [Spacer(1, 0.5 * cm), topo, t]
    return [KeepTogether(bloco)] if len(rows) <= 14 else bloco       # banco curto não é cortado entre páginas; o longo continua com o cabeçalho repetido


def gerar_pdf(df: pd.DataFrame, dt_ini: datetime.date, dt_fim: datetime.date) -> bytes:
    """PDF das pendências de `df` (uma ou várias empresas) no período `dt_ini` a `dt_fim`."""
    d = df.copy()
    d["EMPRESA"] = d["ORGANIZACAO"].map(nome_empresa)
    empresas = list(d.groupby("EMPRESA").size().sort_values(ascending=False).index)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm, bottomMargin=1.6 * cm,
                            title="Pendências de conciliação", author="Painel Financeiro DEMO")
    el = []
    if len(empresas) > 1:                    # várias empresas: a primeira página resume por empresa
        el += [_cabecalho("TODAS AS EMPRESAS", "Pendências de conciliação por empresa", dt_ini, dt_fim), Spacer(1, 0.45 * cm),
               _cards(d, f"em {len(empresas)} empresas"), Spacer(1, 0.45 * cm), Paragraph("Resumo por empresa", _ps("h", 10, True, _NV2)), Spacer(1, 0.15 * cm),
               _tabela_resumo(_agrupar(d, ["EMPRESA"]), "EMPRESA", "Empresa")]
    for i, emp in enumerate(empresas):
        e = d[d["EMPRESA"] == emp]
        if el:
            el.append(PageBreak())
        n_bancos = e["COD_BANCO"].nunique()
        el += [_cabecalho(emp, "Pendências de conciliação por banco", dt_ini, dt_fim), Spacer(1, 0.45 * cm),
               _cards(e, f"em {n_bancos} banco(s)"), Spacer(1, 0.45 * cm), Paragraph("Resumo por banco", _ps("h", 10, True, _NV2)), Spacer(1, 0.15 * cm),
               _tabela_resumo(_agrupar(e, ["COD_BANCO", "CONTA"]), "CONTA", "Banco", col_cod="COD_BANCO")]
        ordem = _com_rotulo_banco(_agrupar(e, ["COD_BANCO", "CONTA"]))
        for r in ordem.to_dict("records"):
            el += _bloco_banco(r["BANCO"], e[e["COD_BANCO"] == r["COD_BANCO"]])
    doc.build(el, canvasmaker=_Numerado)
    return buf.getvalue()
