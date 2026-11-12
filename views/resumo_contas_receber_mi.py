"""
views/resumo_contas_receber_mi.py
=================================
Visão "Resumo" do Contas a Receber - MI (botão Painel | Resumo em contas_receber_painel.py). Por enquanto só Recebimentos: o que entrou no banco por mês (baixas
196 e 953 pela data do banco; desconto e adiantamento ficam de fora), a comparação com o ano anterior e o PMR (prazo médio
de recebimento: dias entre a emissão da nota e o pagamento, ponderado pelo valor pago). A visão Posição entra depois.
"""

import datetime

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from services.data_service import carregar_recebido_banco_mes_mi, carregar_recebido_mensal_mi, carregar_recebido_periodo_mi
from utils.exporters import exportar_excel_abas_recebimentos

_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
          "Novembro", "Dezembro"]
_ABREV = [m[:3] for m in _MESES]
_VERDE = "#00B050"
_VERMELHO = "#FF0000"
_ROSA = "#e879f9"


def _moeda(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float, sinal: bool = False) -> str:
    return (f"{v:+.2f}" if sinal else f"{v:.2f}").replace(".", ",") + "%"


def _mi(v: float) -> str:
    """Valor em milhões com 1 decimal ("6,2")."""
    return f"{v / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pmr(d: pd.DataFrame):
    """PMR em dias: média da distância emissão -> pagamento ponderada pelo valor pago. Só entram baixas com emissão
    achada e pagamento não anterior à emissão. None se não houver base."""
    v = d[d["EMISSAO"].notna()]
    dias = (v["DIA"] - v["EMISSAO"]).dt.days
    ok = dias >= 0
    v, dias = v[ok], dias[ok]
    total = v["VALOR_PAGO"].sum()
    return float((v["VALOR_PAGO"] * dias).sum() / total) if total > 0 else None


def _mensal(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Uma linha por mês de `ano` com dados: Recebido, Títulos, Clientes e PMR."""
    d = df[df["DIA"].dt.year == ano]
    linhas = []
    for m in sorted(d["DIA"].dt.month.unique()):
        x = d[d["DIA"].dt.month == m]
        linhas.append({"Mes": int(m), "Recebido": x["VALOR_PAGO"].sum(),
                       "Titulos": x[["DOC", "AGN", "PARC"]].drop_duplicates().shape[0],
                       "Clientes": x["AGN"].nunique(), "PMR": _pmr(x)})
    return pd.DataFrame(linhas, columns=["Mes", "Recebido", "Titulos", "Clientes", "PMR"])


def _anterior_comparavel(df: pd.DataFrame, ano: int, hoje: datetime.date) -> pd.DataFrame:
    """Recebido por mês do ano anterior para comparar com `ano`. No mês corrente do ano atual só entram os dias até o dia de
    hoje (o mês de `ano` ainda está incompleto), a mesma regra do card de comparação."""
    ant = _mensal(df, ano - 1)
    if ano == hoje.year:
        x = df[(df["DIA"].dt.year == ano - 1) & (df["DIA"].dt.month == hoje.month) & (df["DIA"].dt.day <= hoje.day)]
        ant = ant[ant["Mes"] != hoje.month]
        if not x.empty:
            linha = {"Mes": hoje.month, "Recebido": x["VALOR_PAGO"].sum(),
                     "Titulos": x[["DOC", "AGN", "PARC"]].drop_duplicates().shape[0], "Clientes": x["AGN"].nunique(),
                     "PMR": _pmr(x)}
            ant = pd.concat([ant, pd.DataFrame([linha])], ignore_index=True).sort_values("Mes").reset_index(drop=True)
    return ant


def _card(rotulo: str, valor: str, sub: str, cor: str, cor_valor: str = "#fff") -> str:
    return (f'<div style="background:#1e1e2e;border-radius:8px;border-top:3px solid {cor};padding:10px 12px;min-width:0">'
            f'<div style="font-size:11px;color:#8892A4">{rotulo}</div>'
            f'<div style="font-size:18px;font-weight:600;color:{cor_valor};margin-top:2px;white-space:nowrap">{valor}</div>'
            f'<div style="font-size:10px;color:#8892A4;margin-top:2px">{sub}</div></div>')


def _grafico(atual: pd.DataFrame, anterior: pd.DataFrame, ano: int, ocultar: bool = False, bancos: dict = None) -> str:
    """Colunas do recebido por mês do ano escolhido, com a linha tracejada do ano anterior (mesma escala). Ao passar o mouse
    numa coluna aparece o quadro do mês: total, valor por banco (com %) e o mesmo mês do ano anterior. `bancos`:
    {mês: [(banco, valor), ...]} em ordem decrescente. Com "Ocultar" ligado não há valores nem quadro."""
    bancos = bancos or {}
    W, H, PL, PB = 760, 230, 40, 24
    va = dict(zip(atual["Mes"], atual["Recebido"]))
    vp = dict(zip(anterior["Mes"], anterior["Recebido"]))
    topo = max([*va.values(), *vp.values(), 1.0])
    passo = 1e6 if topo <= 6e6 else 2e6 if topo <= 14e6 else 5e6
    teto = (int(topo // passo) + 1) * passo
    area = H - PB - 14
    y = lambda v: H - PB - v / teto * area
    bw = (W - PL) / 12
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Recebido por mês em {ano} e {ano - 1}">'
         f'<title>Recebido por mês</title>']
    t = 0.0
    while t <= teto + 1:
        s.append(f'<line x1="{PL}" x2="{W}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#2a2a3a"/>'
                 f'<text x="{PL - 6}" y="{y(t) + 4:.1f}" fill="#8892A4" font-size="10" text-anchor="end">{"" if ocultar else _mi(t)}</text>')
        t += passo
    for m in range(1, 13):
        x = PL + (m - 1) * bw
        s.append(f'<text x="{x + bw / 2:.1f}" y="{H - 8}" fill="#8892A4" font-size="10" text-anchor="middle">{_ABREV[m - 1]}</text>')
        if m in va:
            h = va[m] / teto * area
            s.append(f'<rect x="{x + bw * 0.2:.1f}" y="{y(va[m]):.1f}" width="{bw * 0.6:.1f}" height="{h:.1f}" rx="3" fill="{_VERDE}"/>'
                     f'<text x="{x + bw / 2:.1f}" y="{y(va[m]) - 4:.1f}" fill="#e0e0e0" font-size="10" text-anchor="middle">{"" if ocultar else _mi(va[m])}</text>')
    for m in sorted(va):                       # ano anterior: um traço por coluna (só nos meses que têm coluna)
        if m in vp:
            x0 = PL + (m - 1) * bw
            s.append(f'<line x1="{x0 + bw * 0.08:.1f}" x2="{x0 + bw * 0.92:.1f}" y1="{y(vp[m]):.1f}" y2="{y(vp[m]):.1f}" '
                     f'stroke="{_ROSA}" stroke-width="3" stroke-linecap="round"/>')

    css = ""
    if not ocultar:
        TW = 400.0
        for m in sorted(va):
            x0 = PL + (m - 1) * bw
            linhas = bancos.get(m, [])
            tt_h = 30 + 14 * len(linhas) + 16
            tx = min(max(x0 + bw / 2 - TW / 2, 4), W - TW - 4)
            g = [f'<g class="rcmt{m}" style="display:none" pointer-events="none">'
                 f'<rect x="{tx:.1f}" y="6" width="{TW:.0f}" height="{tt_h}" rx="6" fill="#0f1320" stroke="#3a4160"/>'
                 f'<text x="{tx + 10:.1f}" y="23" fill="#ffffff" font-size="11" font-weight="600">{_MESES[m - 1]}/{ano} · R$ {_moeda(va[m])}</text>']
            for i, (banco, valor) in enumerate(linhas):
                yy = 40 + i * 14
                nome = banco if len(banco) <= 42 else banco[:41] + "…"
                pct = valor / va[m] * 100 if va[m] else 0
                g.append(f'<text x="{tx + 10:.1f}" y="{yy}" fill="#c9cfe0" font-size="10">{nome}</text>'
                         f'<text x="{tx + TW - 10:.1f}" y="{yy}" fill="#e0e0e0" font-size="10" text-anchor="end">{_moeda(valor)} · {_pct(pct)}</text>')
            ant = vp.get(m)
            hoje_ = datetime.date.today()
            sufixo = f" (até o dia {hoje_.day})" if ano == hoje_.year and m == hoje_.month else ""
            g.append(f'<text x="{tx + 10:.1f}" y="{tt_h - 2}" fill="{_ROSA}" font-size="10">'
                     f'{ano - 1}{sufixo}: {"sem dados" if ant is None else "R$ " + _moeda(ant)}</text></g>')
            s.append("".join(g))
            # área de captura do mouse: a coluna inteira do mês (por cima das barras, abaixo do quadro)
            s.insert(len(s) - 1, f'<rect class="rcmh{m}" x="{x0:.1f}" y="0" width="{bw:.1f}" height="{H - PB}" fill="#000" fill-opacity="0"/>')
            css += f"svg:has(.rcmh{m}:hover) .rcmt{m}{{display:block !important}}"
    s.append("</svg>")
    legenda = (f'<div style="display:flex;gap:16px;font-size:11px;color:#8892A4;margin-top:2px">'
               f'<span><span style="display:inline-block;width:10px;height:10px;background:{_VERDE};border-radius:2px"></span> {ano}</span>'
               f'<span><span style="display:inline-block;width:14px;border-top:3px solid {_ROSA};vertical-align:middle"></span> {ano - 1} (mesmo mês)</span>'
               f'<span>{"" if ocultar else "valores em R$ milhões · passe o mouse na coluna para ver o banco"}</span></div>')
    return (f"<style>{css}</style>" if css else "") + "".join(s) + legenda


def _tabela(atual: pd.DataFrame, anterior: pd.DataFrame, ano: int, hoje: datetime.date, ocultar: bool = False) -> str:
    vp = dict(zip(anterior["Mes"], anterior["Recebido"]))
    th = ("<th style='text-align:left;color:#8892A4;font-weight:500;padding:6px 8px;border-bottom:1px solid #2a2a3a'>{}</th>")
    thr = ("<th style='text-align:right;color:#8892A4;font-weight:500;padding:6px 8px;border-bottom:1px solid #2a2a3a'>{}</th>")
    cab = th.format("Mês") + "".join(thr.format(c) for c in ("Recebido", "Títulos", "Clientes", "PMR", f"{ano - 1}", "Variação"))
    td = "<td style='padding:5px 8px;border-bottom:1px solid #23232f;{}'>{}</td>"
    linhas = ""
    for _, r in atual.iterrows():
        m = int(r["Mes"])
        parcial = ano == hoje.year and m == hoje.month
        nome = f"{_MESES[m - 1]}" + (f" <span style='color:#8892A4;font-size:10px'>(até {hoje:%d/%m})</span>" if parcial else "")
        ant = vp.get(m)
        var = ((r["Recebido"] / ant - 1) * 100) if ant else None
        cor = "" if var is None else f"color:{_VERDE if var >= 0 else _VERMELHO};font-weight:600;"
        linhas += ("<tr>" + td.format("", nome)
                   + td.format(f"text-align:right;color:{_VERDE};font-weight:600;", "••••••" if ocultar else _moeda(r["Recebido"]))
                   + td.format("text-align:right;", "••" if ocultar else f"{int(r['Titulos'])}")
                   + td.format("text-align:right;", "••" if ocultar else f"{int(r['Clientes'])}")
                   + td.format("text-align:right;", "—" if r["PMR"] is None else f"{r['PMR']:.0f} d")
                   + td.format("text-align:right;color:#8892A4;", "••••••" if ocultar else ("—" if ant is None else _moeda(ant)))
                   + td.format(f"text-align:right;{cor}", "••" if ocultar else ("—" if var is None else _pct(var, sinal=True))) + "</tr>")
    return (f"<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:12px;color:#e0e0e0'>"
            f"<thead><tr>{cab}</tr></thead><tbody>{linhas}</tbody></table></div>")


def _excel(df: pd.DataFrame, ano: int, atual: pd.DataFrame, anterior: pd.DataFrame) -> bytes:
    """Excel do painel: Resumo mensal, Por banco (meses nas colunas) e Títulos recebidos (detalhe do ano)."""
    hoje = pd.Timestamp.today().normalize()
    ini, fim = pd.Timestamp(ano, 1, 1), min(pd.Timestamp(ano, 12, 31), hoje)
    det = carregar_recebido_periodo_mi(ini.date(), fim.date())
    vp = dict(zip(anterior["Mes"], anterior["Recebido"]))
    # Resumo mensal (mais uma linha de total do ano)
    resumo = pd.DataFrame({
        "Mês": [_MESES[int(m) - 1] for m in atual["Mes"]], "Recebido": atual["Recebido"], "Títulos": atual["Titulos"],
        "Clientes": atual["Clientes"], "PMR (dias)": atual["PMR"].round(0),
        f"Recebido {ano - 1}": [vp.get(int(m)) for m in atual["Mes"]],
    })
    resumo["Variação"] = resumo["Recebido"] / resumo[f"Recebido {ano - 1}"] - 1
    d_ano = df[df["DIA"].dt.year == ano]
    total = {"Mês": "TOTAL", "Recebido": resumo["Recebido"].sum(),
             "Títulos": d_ano[["DOC", "AGN", "PARC"]].drop_duplicates().shape[0], "Clientes": d_ano["AGN"].nunique(),
             "PMR (dias)": round(_pmr(d_ano)) if _pmr(d_ano) is not None else None,
             f"Recebido {ano - 1}": anterior[anterior["Mes"].isin(atual["Mes"])]["Recebido"].sum() or None}
    total["Variação"] = (total["Recebido"] / total[f"Recebido {ano - 1}"] - 1) if total[f"Recebido {ano - 1}"] else None
    resumo = pd.concat([resumo, pd.DataFrame([total])], ignore_index=True)
    # Por banco e detalhe
    if det.empty:
        por_banco, titulos = pd.DataFrame(), pd.DataFrame()
    else:
        det = det.merge(df[["DOC", "AGN", "EMISSAO"]].drop_duplicates(["DOC", "AGN"]), on=["DOC", "AGN"], how="left")
        det["MES"] = det["DIA"].dt.month.map(lambda m: _ABREV[m - 1])
        ordem = [_ABREV[m - 1] for m in sorted(det["DIA"].dt.month.unique())]
        por_banco = det.pivot_table(index="BANCO", columns="MES", values="VALOR_PAGO", aggfunc="sum", fill_value=0.0)[ordem]
        por_banco["Total"] = por_banco.sum(axis=1)
        por_banco = por_banco.sort_values("Total", ascending=False)
        por_banco.loc["TOTAL"] = por_banco.sum()
        por_banco = por_banco.reset_index().rename(columns={"BANCO": "Banco"})
        det = det.sort_values(["DIA", "CLIENTE", "DOC", "PARC"], ascending=[False, True, True, True])
        titulos = pd.DataFrame({
            "Data Pagamento": det["DIA"], "Cód. Cliente": det["AGN"].astype("Int64"), "Cliente": det["CLIENTE"],
            "Banco": det["BANCO"], "NF": det["DOC"], "Parcela": det["PARC"], "Emissão": det["EMISSAO"],
            "Vencimento": det["VENCIMENTO"],
            "Prazo (dias)": (det["DIA"] - det["EMISSAO"]).dt.days.astype("Int64"), "Valor Pago": det["VALOR_PAGO"],
        })
    meses_banco = tuple(c for c in por_banco.columns if c != "Banco")
    return exportar_excel_abas_recebimentos([
        {"nome": "Resumo mensal", "titulo": f"Recebimentos por mês - Mercado Interno - {ano} (pela data da baixa no banco)",
         "df": resumo, "moeda": ("Recebido", f"Recebido {ano - 1}"), "verde": ("Recebido",), "percentual": ("Variação",),
         "centro": ("Títulos", "Clientes", "PMR (dias)"), "total_na_ultima": True},
        {"nome": "Por banco", "titulo": f"Recebido por banco e mês - Mercado Interno - {ano}", "df": por_banco,
         "moeda": meses_banco, "total_na_ultima": True},
        {"nome": "Títulos recebidos", "titulo": f"Títulos recebidos - Mercado Interno - {ano} ({ini:%d/%m/%Y} a {fim:%d/%m/%Y})",
         "df": titulos, "moeda": ("Valor Pago",), "verde": ("Valor Pago",), "centro": ("Parcela", "Prazo (dias)")},
    ])


def render(mostrar_titulo: bool = True, ocultar: bool = False):
    """`mostrar_titulo`: False quando a visão aparece dentro do Contas a Receber - MI (o título já está na página).
    `ocultar`: esconde os valores em R$ (botão Ocultar do Contas a Receber)."""
    hoje = datetime.date.today()
    anos = [hoje.year, hoje.year - 1, hoje.year - 2]
    # Título à esquerda; seletor de ano e botão de Excel encostados no canto direito
    st.markdown("<style>.st-key-rcm_canto{align-items:flex-end}</style>", unsafe_allow_html=True)
    c_tit, c_ano, c_xls = st.columns([4.2, 0.9, 1.5], vertical_alignment="center")
    with c_tit:
        if mostrar_titulo:
            st.title("Resumo do Contas a Receber - MI")
        else:
            st.markdown("#### Resumo · Recebimentos")
    with c_ano:
        ano = st.selectbox("Ano", anos, key="rcm_ano", label_visibility="collapsed", format_func=lambda a: f"Ano {a}")
    st.caption("Recebimentos · Mercado Interno · só o que entrou no banco (data da baixa); desconto e adiantamento não entram")

    with st.spinner("Carregando os recebimentos..."):
        df = carregar_recebido_mensal_mi(ano)
    if df is None or df.empty:
        st.info("Nenhum recebimento encontrado para o período.")
        return
    atual, anterior = _mensal(df, ano), _anterior_comparavel(df, ano, hoje)
    if atual.empty:
        st.info(f"Nenhum recebimento em {ano}.")
        return

    with c_xls:
        with st.container(key="rcm_canto"):
            botao_exportar_excel(lambda: _excel(df, ano, atual, anterior), f"Recebimentos_MI_{ano}.xlsx", key="rcm_excel",
                                 help="Três abas: Resumo mensal, Por banco (meses nas colunas) e Títulos recebidos (detalhe do ano)")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total = atual["Recebido"].sum()
    fechados = atual[~((ano == hoje.year) & (atual["Mes"] == hoje.month))]
    base_media = fechados if not fechados.empty else atual
    melhor = atual.loc[atual["Recebido"].idxmax()]
    ref = int(atual["Mes"].max())                          # último mês com dados no ano escolhido
    parcial = ano == hoje.year and ref == hoje.month
    d_ref = df[(df["DIA"].dt.year == ano) & (df["DIA"].dt.month == ref)]
    d_ant = df[(df["DIA"].dt.year == ano - 1) & (df["DIA"].dt.month == ref)]
    if parcial:
        d_ant = d_ant[d_ant["DIA"].dt.day <= hoje.day]
    v_ref, v_ant = d_ref["VALOR_PAGO"].sum(), d_ant["VALOR_PAGO"].sum()
    var = (v_ref / v_ant - 1) * 100 if v_ant else None
    pmr_ano, pmr_ant = _pmr(df[df["DIA"].dt.year == ano]), _pmr(df[df["DIA"].dt.year == ano - 1])
    titulos_ano = df[df["DIA"].dt.year == ano][["DOC", "AGN", "PARC"]].drop_duplicates().shape[0]
    delta_pmr = (f"{pmr_ano - pmr_ant:+.0f} dias vs {ano - 1}" if pmr_ano is not None and pmr_ant is not None
                 else "sem base do ano anterior")
    mi_txt = lambda v: "•••" if ocultar else _mi(v)
    cards = [
        _card(f"Recebido em {ano}", f"R$ {mi_txt(total)} mi", "•• títulos" if ocultar else f"{titulos_ano} títulos", _VERDE, _VERDE),
        _card("Média mensal", f"R$ {mi_txt(base_media['Recebido'].mean())} mi", f"{len(base_media)} mês(es) fechado(s)", "#378ADD"),
        _card("Melhor mês", _MESES[int(melhor['Mes']) - 1], f"R$ {mi_txt(melhor['Recebido'])} mi", "#eda100"),
        _card(f"{_ABREV[ref - 1]} x {_ABREV[ref - 1].lower()}/{ano - 1}",
              "••%" if ocultar else ("—" if var is None else _pct(var, sinal=True)),
              f"até o dia {hoje.day}" if parcial else "mês completo", "#8b5cf6",
              "#fff" if (var is None or ocultar) else (_VERDE if var >= 0 else _VERMELHO)),
        _card("PMR (emissão até o pagamento)", "—" if pmr_ano is None else f"{pmr_ano:.0f} dias", delta_pmr, "#1BADA6"),
    ]
    st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:6px 0 14px">'
                + "".join(cards) + "</div>", unsafe_allow_html=True)

    # ── Giro da carteira (PMR) ─────────────────────────────────────────────────
    if pmr_ano:
        giros = 365 / pmr_ano
        st.markdown(
            '<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px;margin-bottom:14px;display:flex;align-items:center;'
            'gap:14px;flex-wrap:wrap"><div><div style="font-size:12px;color:#c9cfe0;font-weight:500">Giro da carteira</div>'
            '<div style="font-size:11px;color:#8892A4">PMR ponderado pelo valor pago, da emissão da nota ao pagamento</div></div>'
            f'<div style="font-size:22px;font-weight:600;color:#1BADA6">a cada {pmr_ano:.0f} dias</div>'
            f'<div style="font-size:13px;color:#c9cfe0">= {f"{giros:.1f}".replace(".", ",")} giros por ano</div></div>',
            unsafe_allow_html=True)

    # ── Gráfico e tabela ───────────────────────────────────────────────────────
    bancos = {}
    if not ocultar:                                    # recebido por banco, só para o quadro do mouse
        bm = carregar_recebido_banco_mes_mi(ano)
        for m, g in bm.groupby("MES"):
            bancos[int(m)] = list(g.sort_values("VALOR", ascending=False)[["BANCO", "VALOR"]].itertuples(index=False, name=None))
    st.markdown('<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px;margin-bottom:14px">'
                '<div style="font-size:12px;color:#c9cfe0;font-weight:500;margin-bottom:6px">Recebido por mês (baixa no banco)</div>'
                + _grafico(atual, anterior, ano, ocultar, bancos) + "</div>", unsafe_allow_html=True)
    st.markdown('<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px">'
                '<div style="font-size:12px;color:#c9cfe0;font-weight:500;margin-bottom:6px">Por mês</div>'
                + _tabela(atual, anterior, ano, hoje, ocultar) + "</div>", unsafe_allow_html=True)
