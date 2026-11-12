"""
views/visao_geral_comercial.py
===============================
Painel "Visão Geral Comercial" (Mercado Interno): faturamento dos últimos 12 meses, os mesmos painéis do Contas a
Receber - Mercado Interno (Top Clientes a Receber por grupo/cliente, Vencido por Cliente e Vencido por Faixa de Atraso)
e a lista de clientes com título em aberto bloqueados por Faturamento (título com prorrogação vencida) e/ou por
Documentação (Situação do Grupo de Crédito).
"""

import datetime
import unicodedata

import pandas as pd
import streamlit as st

from components.cards import card_html, render_cards_row
from components.buttons import botao_exportar_excel
from config.pdd import classificar_vencidos
from services.data_service import (
    carregar_faturado_mensal_mi, carregar_notas_vendidas_mi, carregar_vendas_dia_vendedor_mi,
)
from views.contas_receber import (
    _bloco_faixas_vencido, _bloco_vencido_por_cliente, _ranking_clientes, formatar_moeda,
)

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_OPACIDADES = ["1", "1", "1", "0.70", "0.55", "0.45", "0.38", "0.32", "0.28", "0.24", "0.21", "0.18", "0.16", "0.14", "0.12"]
_VERDE, _VERMELHO, _AZUL, _AMBAR = "#22c55e", "#E24B4A", "#378ADD", "#F59E0B"
_ROSA = "#e879f9"      # linha do ano anterior
_MESES_NOME = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def _mi(valor: float, ocultar: bool) -> str:
    """Valor abreviado: 7,40 mi · 240 mil · 20 mil · 350."""
    if ocultar:
        return "••"
    if abs(valor) >= 1e6:
        return f"{valor / 1e6:.2f}".replace(".", ",") + " mi"
    if abs(valor) >= 1e3:
        return f"{valor / 1e3:.0f} mil"
    return f"{valor:.0f}"


def _faturamento_12_meses(ocultar: bool) -> None:
    st.markdown("#### Faturamento")
    df = carregar_faturado_mensal_mi()
    if df is None or df.empty:
        st.info("Sem faturamento no período.")
        return
    df = df.copy()
    for c in ("ANO", "MES", "VALOR_TOTAL_FATURADO"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    hoje = datetime.date.today()
    idx_atual = hoje.year * 12 + hoje.month - 1
    por_mes = {int(a) * 12 + int(m) - 1: float(v) for a, m, v in zip(df["ANO"], df["MES"], df["VALOR_TOTAL_FATURADO"])}
    fechados = [(i, por_mes.get(i, 0.0)) for i in range(idx_atual - 12, idx_atual)]
    total = sum(v for _, v in fechados)
    media = total / 12
    melhor = max(fechados, key=lambda x: x[1])
    pior = min(fechados, key=lambda x: x[1])
    parcial = por_mes.get(idx_atual, 0.0)
    colunas = fechados + [(idx_atual, parcial)]
    maximo = max(v for _, v in colunas) or 1
    rot = lambda i: f"{_MESES[i % 12]}/{str(i // 12)[2:]}"
    anterior = por_mes.get(idx_atual - 1, 0.0)
    rs = lambda v: "R$ ••••••" if ocultar else formatar_moeda(v)
    # título em branco; o mês (subtítulo) fica no cinza padrão do card
    titulo = lambda t: f'<span style="color:#ffffff">{t}</span>'
    render_cards_row([
        card_html(titulo("Vendido Mês Anterior"), rs(anterior), rot(idx_atual - 1), cor_borda=_AZUL),
        card_html(titulo("Vendido Mês Atual"), rs(parcial), f"{rot(idx_atual)} - parcial", cor_borda=_AMBAR),
    ])

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    df_dia = carregar_vendas_dia_vendedor_mi()
    st.markdown(
        f"<style>.st-key-vgc_fat_bloco{{background:#1e1e2e;border-radius:12px;border-top:4px solid {_AZUL};"
        "padding:14px 18px;box-sizing:border-box}</style>",
        unsafe_allow_html=True,
    )
    with st.container(key="vgc_fat_bloco"):
        if df_dia is None or df_dia.empty:
            st.info("Sem vendas no período.")
        else:
            _bloco_vendas(df_dia, hoje, ocultar)

    # Fora do bloco do gráfico. A planilha só é gerada (e as notas só são buscadas) quando o botão é clicado.
    botao_exportar_excel(
        lambda: _excel_notas_vendidas(carregar_notas_vendidas_mi(f"{hoje.year}-01-01"), hoje.year, hoje),
        f"Notas_Vendidas_MI_{hoje.year}.xlsx", key="vgc_export_notas", label="Exportar notas vendidas (Excel)",
        help="Resumo por vendedor e mês + todas as notas do ano (Mercado Interno).",
    )


def _primeiro_e_ultimo(nome: str) -> str:
    """"RAFAEL CARVALHO DE MELLO" -> "Rafael Mello"."""
    partes = str(nome).split()
    while len(partes) > 2 and partes[-1].upper().strip(".") in ("LTDA", "ME", "EPP", "EIRELI", "SA", "S/A", "S.A"):
        partes.pop()   # sufixo de razão social não é sobrenome
    if len(partes) <= 1:
        return str(nome).title()
    return f"{partes[0]} {partes[-1]}".title()


def _ranking_vendedores_html(d: pd.DataFrame, cor: str, ocultar: bool, nota: str, altura: int = 158) -> str:
    """Linhas do ranking: posição, nome (primeiro e último), %, barra, valor e quantidade de NF."""
    total = d["valor"].sum() or 1
    maximo = d["valor"].max() or 1
    linhas = ""
    for k, r in enumerate(d.itertuples()):
        opac = _OPACIDADES[k] if k < len(_OPACIDADES) else "0.12"
        val = "R$ ••••••" if ocultar else (formatar_moeda(r.valor) if r.valor else "—")
        pct = "••" if ocultar else f"{r.valor / total * 100:.2f}%".replace(".", ",")
        linhas += (
            '<div style="display:grid;grid-template-columns:20px minmax(0,1fr) 52px minmax(0,1fr) 120px 64px;gap:8px;align-items:center;font-size:13px;padding:5px 0">'
            f'<span style="color:#8892A4;font-size:11px;font-weight:600;text-align:center">{k + 1}</span>'
            f'<span style="color:#e0e0e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{r.VENDEDOR}">{_primeiro_e_ultimo(r.VENDEDOR)}</span>'
            f'<span style="color:{cor};font-size:11px;font-weight:600;text-align:right">{pct}</span>'
            '<div style="height:14px;border-radius:4px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div style="width:{r.valor / maximo * 100:.1f}%;height:100%;background:{cor};opacity:{opac}"></div></div>'
            f'<span style="color:#fff;font-size:12px;text-align:right;white-space:nowrap">{val}</span>'
            f'<span style="color:#8892A4;font-size:11px;text-align:right;white-space:nowrap">{int(r.notas)} NF</span></div>'
        )
    # 5 vendedores visíveis; os demais aparecem na barra de rolagem
    return (f'<div style="max-height:{altura}px;overflow-y:scroll;padding-right:6px;scrollbar-width:auto;scrollbar-color:#6b7690 #2a2a3a">{linhas}</div>'
            f'<div style="height:1px;background:#2a2a3a;margin:8px 0 6px"></div><span style="color:#8892A4;font-size:11px">{nota}</span>')


def _ultimo_dia(ano: int, mes: int) -> datetime.date:
    return datetime.date(ano + mes // 12, mes % 12 + 1, 1) - datetime.timedelta(days=1)


def _um_ano_antes(d: datetime.date) -> datetime.date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:      # 29/02
        return d.replace(year=d.year - 1, day=28)


def _periodos(modo: str, ano_sel, mes_sel: int, hoje: datetime.date) -> tuple:
    """Períodos do gráfico (barras) e o período equivalente do ano anterior, cortado no mesmo ponto quando o período está em
    andamento. Devolve (lista de períodos, título, unidade da média, rótulo do período para o Top Vendedores)."""
    per = []
    idx_atual = hoje.year * 12 + hoje.month - 1
    if modo == "Mês":
        idxs = range(idx_atual - 11, idx_atual + 1) if ano_sel is None else range(ano_sel * 12, ano_sel * 12 + 12)
        for i in idxs:
            a, m = i // 12, i % 12 + 1
            ini, fim = datetime.date(a, m, 1), _ultimo_dia(a, m)
            fim_c = _ultimo_dia(a - 1, m) if fim <= hoje else _um_ano_antes(hoje)
            per.append(dict(rot=f"{_MESES[m - 1]}/{str(a)[2:]}" if ano_sel is None else _MESES[m - 1],
                            nome=f"{_MESES_NOME[m - 1]}/{a}", ini=ini, fim=fim,
                            ini_c=datetime.date(a - 1, m, 1), fim_c=fim_c))
        tit, un = ("últimos 12 meses" if ano_sel is None else str(ano_sel)), "mês"
    elif modo == "Semana":
        if ano_sel is None:
            seg = hoje - datetime.timedelta(days=hoje.weekday())
            inicio, limite = seg - datetime.timedelta(weeks=12), hoje
        else:
            jan1 = datetime.date(ano_sel, 1, 1)
            inicio, limite = jan1 - datetime.timedelta(days=jan1.weekday()), min(datetime.date(ano_sel, 12, 31), hoje)
        d0 = inicio
        while d0 <= limite:
            ini = max(d0, datetime.date(ano_sel, 1, 1)) if ano_sel is not None else d0
            fim = d0 + datetime.timedelta(days=6)
            if ano_sel is not None:
                fim = min(fim, datetime.date(ano_sel, 12, 31))
            ef = min(fim, hoje)
            nsem = (d0 + datetime.timedelta(days=3)).isocalendar()[1]     # semana ISO (segunda a domingo)
            per.append(dict(rot=f"S{nsem}", rot2=f"{d0:%d/%m}", nome=f"Semana {nsem} · {ini:%d/%m} a {fim:%d/%m/%Y}", ini=ini, fim=fim,
                            ini_c=ini - datetime.timedelta(days=364), fim_c=ef - datetime.timedelta(days=364)))
            d0 += datetime.timedelta(days=7)
        tit, un = ("últimas 13 semanas" if ano_sel is None else str(ano_sel)), "semana"
    else:
        a = hoje.year if ano_sel is None else ano_sel
        for dia in range(1, _ultimo_dia(a, mes_sel).day + 1):
            d0 = datetime.date(a, mes_sel, dia)
            per.append(dict(rot=f"{dia:02d}", nome=f"{d0:%d/%m/%Y}", ini=d0, fim=d0,
                            ini_c=_um_ano_antes(d0), fim_c=_um_ano_antes(d0)))
        tit, un = f"{_MESES_NOME[mes_sel - 1]}/{a}", "dia com venda"
    for p in per:
        p["futuro"] = p["ini"] > hoje
        p["parcial"] = p["ini"] <= hoje <= p["fim"]
    return per, tit, un, tit


def _soma(df: pd.DataFrame, ini, fim) -> pd.DataFrame:
    return df[(df["_D"] >= ini) & (df["_D"] <= fim)]


def _grafico_periodos(per: list, nomes: list, cores: list, comparar: bool, ocultar: bool) -> str:
    """Colunas empilhadas por vendedor (uma por período), valor no topo quando cabe e, se pedido, linha tracejada com o
    total do período equivalente do ano anterior. O quadro com o detalhe aparece ao passar o mouse sobre a coluna."""
    n = len(per)
    maximo = max([p["total"] for p in per] + ([p["comp"] for p in per] if comparar else []) + [1.0])
    duas_linhas = n <= 13 and bool(per[0].get("rot2"))      # semanas: "S46" e, abaixo, a data da segunda-feira
    W, H, T, B = 860, (244 if duas_linhas else 230), 18, (40 if duas_linhas else 26)
    bw = (W - 20) / n
    larg = bw * (0.6 if n <= 13 else 0.7)
    brl = lambda v: "R$ ••••••" if ocultar else formatar_moeda(v)
    passo = 1 if n <= 31 else 4
    fonte_x = 11 if n <= 13 else 9
    svg, camada_dicas, css_dicas, pontos = "", "", "", []
    for k, p in enumerate(per):
        x = 10 + k * bw + (bw - larg) / 2
        cx = x + larg / 2
        acc, segs = 0.0, ""
        for j, v in enumerate(p["linha"]):
            h = (H - T - B) * v / maximo
            if v > 0:
                segs += f'<rect x="{x:.1f}" y="{T + (H - T - B) - acc - h:.1f}" width="{larg:.1f}" height="{h:.1f}" fill="{cores[j]}"/>'
            acc += h
        rotulos = ""
        if n <= 13 and p["total"] > 0:
            rotulos += (f'<text x="{cx:.1f}" y="{T + (H - T - B) - acc - 5:.1f}" text-anchor="middle" fill="#d7e0ee" font-size="11">'
                        f'{_mi(p["total"], ocultar)}{"*" if p["parcial"] else ""}</text>')
        if k % passo == 0:
            marca = "*" if p["parcial"] and n <= 13 else ""
            rotulos += (f'<text x="{cx:.1f}" y="{H - 8 - (14 if duas_linhas else 0)}" text-anchor="middle" fill="{_AMBAR if p["parcial"] else "#8892a4"}" '
                        f'font-size="{fonte_x}">{p["rot"]}{marca}</text>')
            if duas_linhas:
                rotulos += f'<text x="{cx:.1f}" y="{H - 8}" text-anchor="middle" fill="#6b7690" font-size="10">{p["rot2"]}</text>'
        com_comp = comparar and not p["futuro"]
        if com_comp:
            pontos.append((cx, T + (H - T - B) * (1 - p["comp"] / maximo)))
        itens = [(cores[j], nomes[j], v) for j, v in enumerate(p["linha"]) if v > 0]
        extra = 1 + (1 if com_comp else 0)
        bx_w, lh = 250, 17
        bx_h = 28 + lh * (len(itens) + extra) + 6
        bx = cx + bw * 0.45 if cx < W / 2 else cx - bw * 0.45 - bx_w
        by = max(2, T + 4)
        titulo_q = p["nome"] + (" (parcial)" if p["parcial"] else "")
        quadro = (f'<g class="vg-tip vg-t{k}" pointer-events="none"><rect x="{bx:.1f}" y="{by}" width="{bx_w}" height="{bx_h}" rx="6" fill="#0b1320" stroke="#5a6488" stroke-width="1"/>'
                  f'<text x="{bx + 10:.1f}" y="{by + 18}" fill="#fff" font-size="12" font-weight="700">{titulo_q}</text>')
        for j, (cor_i, nome_i, v) in enumerate(itens):
            yy = by + 28 + lh * j + 12
            quadro += (f'<rect x="{bx + 10:.1f}" y="{yy - 9}" width="10" height="10" rx="2" fill="{cor_i}"/>'
                       f'<text x="{bx + 26:.1f}" y="{yy}" fill="#d7e0ee" font-size="11">{nome_i}</text>'
                       f'<text x="{bx + bx_w - 10:.1f}" y="{yy}" text-anchor="end" fill="#fff" font-size="11">{brl(v)}</text>')
        yy = by + 28 + lh * len(itens) + 12
        quadro += (f'<line x1="{bx + 10:.1f}" x2="{bx + bx_w - 10:.1f}" y1="{yy - 12}" y2="{yy - 12}" stroke="#3a4160"/>'
                   f'<text x="{bx + 10:.1f}" y="{yy}" fill="#8892a4" font-size="11">Total</text>'
                   f'<text x="{bx + bx_w - 10:.1f}" y="{yy}" text-anchor="end" fill="#fff" font-size="11" font-weight="700">{brl(p["total"])}</text>')
        if com_comp:
            quadro += (f'<text x="{bx + 10:.1f}" y="{yy + lh}" fill="{_ROSA}" font-size="11">Ano anterior</text>'
                       f'<text x="{bx + bx_w - 10:.1f}" y="{yy + lh}" text-anchor="end" fill="{_ROSA}" font-size="11">{brl(p["comp"])}</text>')
        quadro += "</g>"
        svg += (f'<g class="vg-col vg-c{k}"><rect x="{10 + k * bw:.1f}" y="0" width="{bw:.1f}" height="{H}" fill="#fff" fill-opacity="0"/>'
                f'{segs}{rotulos}</g>')
        camada_dicas += quadro
        css_dicas += f'svg:has(.vg-c{k}:hover) .vg-t{k}{{display:block}}'
    if len(pontos) >= 2:
        trilha = " ".join(f"{px:.1f},{py:.1f}" for px, py in pontos)
        svg += (f'<polyline points="{trilha}" fill="none" stroke="{_ROSA}" stroke-width="2" stroke-dasharray="5 4" pointer-events="none"/>'
                + "".join(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.6" fill="{_ROSA}" pointer-events="none"/>' for px, py in pontos))
    svg += camada_dicas
    leg = "".join(f'<span style="margin-right:14px"><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:{cores[k]};margin-right:4px"></span>{nm}</span>'
                  for k, nm in enumerate(nomes))
    if comparar:
        leg += f'<span style="margin-right:14px"><span style="color:{_ROSA};font-weight:700">- - </span>Ano anterior (total)</span>'
    return ('<style>.vg-col{cursor:pointer}.vg-tip{display:none}' + css_dicas +
            '.vg-col:hover rect[fill-opacity="0"]{fill-opacity:.07}</style>'
            f'<div style="font-size:12px;color:#d7e0ee;margin-bottom:6px">{leg}</div>'
            f'<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;overflow:visible">{svg}</svg>'
            '<div style="color:#6b7690;font-size:11px;margin:4px 0 10px">Vendido empilhado por vendedor (data de emissão da nota) · * período em andamento · passe o mouse sobre a barra para ver o valor de cada vendedor</div>')


def _bloco_vendas(df: pd.DataFrame, hoje: datetime.date, ocultar: bool) -> None:
    """Gráfico único de vendas com filtros Mês | Semana | Dia, ano e (no Dia) mês, comparação com o ano anterior e
    Top Vendedores do mesmo período."""
    d = df.copy()
    for c in ("VALOR_TOTAL_FATURADO", "QTD_NOTAS"):
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    d["_D"] = pd.to_datetime(d["DIA"]).dt.date
    anos = sorted({x.year for x in d["_D"]}, reverse=True)

    c1, c2, c3, c4 = st.columns([1.7, 1.4, 1.3, 2.2], vertical_alignment="bottom")
    with c1:
        modo = st.segmented_control("Período", ["Mês", "Semana", "Dia"], default="Mês", required=True,
                                    key="vgc_modo", label_visibility="collapsed")
    with c2:
        ano_txt = st.selectbox("Ano", ["Últimos 12 meses"] + [str(a) for a in anos], key="vgc_ano", label_visibility="collapsed")
    ano_sel = None if ano_txt == "Últimos 12 meses" else int(ano_txt)
    mes_sel = hoje.month
    with c3:
        if modo == "Dia":
            a = hoje.year if ano_sel is None else ano_sel
            ate = hoje.month if a == hoje.year else 12
            nomes_mes = _MESES_NOME[:ate]
            nome_m = st.selectbox("Mês", nomes_mes, index=len(nomes_mes) - 1, key=f"vgc_mes_{a}", label_visibility="collapsed")
            mes_sel = _MESES_NOME.index(nome_m) + 1
    with c4:
        comparar = st.toggle("Comparar com ano anterior", key="vgc_cmp")

    per, tit, un, rotulo = _periodos(modo, ano_sel, mes_sel, hoje)
    # vendedores: os 3 maiores do período e "Demais"
    ini_g, fim_g = per[0]["ini"], per[-1]["fim"]
    base = _soma(d, ini_g, fim_g)
    tops = list(base.groupby("VENDEDOR")["VALOR_TOTAL_FATURADO"].sum().sort_values(ascending=False).head(3).index)
    nomes = [_primeiro_e_ultimo(t) for t in tops] + ["Demais"]
    cores = [_AZUL, _VERDE, _AMBAR, "#8892a4"]
    for p in per:
        x = _soma(d, p["ini"], p["fim"]) if not p["futuro"] else d.iloc[0:0]
        linha = [float(x.loc[x["VENDEDOR"] == t, "VALOR_TOTAL_FATURADO"].sum()) for t in tops]
        linha.append(float(x.loc[~x["VENDEDOR"].isin(tops), "VALOR_TOTAL_FATURADO"].sum()))
        p["linha"], p["total"] = linha, sum(linha)
        p["comp"] = 0.0 if p["futuro"] else float(_soma(d, p["ini_c"], p["fim_c"])["VALOR_TOTAL_FATURADO"].sum())

    total = sum(p["total"] for p in per)
    comp_total = sum(p["comp"] for p in per)
    validos = [p for p in per if not p["futuro"] and not p["parcial"] and p["total"] > 0] or [p for p in per if p["total"] > 0]
    kpi = lambda r, v, cor="#fff": (f'<div><div style="font-size:11px;color:#8892a4">{r}</div>'
                                    f'<div style="font-size:17px;font-weight:700;color:{cor};white-space:nowrap">{v}</div></div>')
    cab = kpi(f"Total · {tit}", f"R$ {_mi(total, ocultar)}")
    if validos:
        melhor = max(validos, key=lambda p: p["total"])
        pior = min(validos, key=lambda p: p["total"])
        media = sum(p["total"] for p in validos) / len(validos)
        cab += (kpi(f"Média por {un}", f"R$ {_mi(media, ocultar)}")
                + kpi("Melhor", f"{melhor['rot']} · {_mi(melhor['total'], ocultar)}", _VERDE)
                + kpi("Menor", f"{pior['rot']} · {_mi(pior['total'], ocultar)}", _VERMELHO))
    if comparar:
        if comp_total > 0 and not ocultar:
            v = (total / comp_total - 1) * 100
            cab += kpi("vs ano anterior", f"{v:+.2f}%".replace(".", ","), _VERDE if v >= 0 else _VERMELHO)
        else:
            cab += kpi("vs ano anterior", "••" if ocultar else "sem dados", "#8892a4")
    st.markdown(f'<div style="display:flex;gap:28px;flex-wrap:wrap;margin:6px 0 4px">{cab}</div>', unsafe_allow_html=True)
    st.markdown(_grafico_periodos(per, nomes, cores, comparar, ocultar), unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:#2a2a3a;margin:6px 0 2px"></div>', unsafe_allow_html=True)
    _top_vendedores(ocultar, base, rotulo, ini_g, fim_g, hoje)


def _top_vendedores(ocultar: bool, base: pd.DataFrame, rotulo: str, ini, fim, hoje: datetime.date) -> None:
    """Top Vendedores do mesmo período do gráfico (segue o filtro). Mostra 5 vendedores; os demais ficam na barra de
    rolagem. Vendedor = representante da nota fiscal."""
    ranking = (base.groupby("VENDEDOR").agg(valor=("VALOR_TOTAL_FATURADO", "sum"), notas=("QTD_NOTAS", "sum"))
               .reset_index().sort_values("valor", ascending=False))
    ranking = ranking[ranking["valor"] > 0]
    total = ranking["valor"].sum() if not ranking.empty else 0.0
    rs = "R$ ••••••" if ocultar else formatar_moeda(total)
    st.markdown(f'<div style="font-weight:700;color:#fff;font-size:15px;padding-top:6px">Top Vendedores · {rotulo}</div>', unsafe_allow_html=True)
    corpo = (_ranking_vendedores_html(ranking, _AMBAR, ocultar, "% sobre o total vendido no período · vendedor = representante da nota fiscal")
             if not ranking.empty else '<div style="color:#8892a4;padding:8px 0">Sem vendas neste período.</div>')
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin:2px 0 6px;font-size:12px;color:#8892a4">'
        f'<span>{ini:%d/%m/%Y} a {min(fim, hoje):%d/%m/%Y}</span><span>Total vendido: <b style="color:#fff">{rs}</b></span></div>{corpo}',
        unsafe_allow_html=True,
    )


def _excel_notas_vendidas(df: pd.DataFrame, ano: int, ate: datetime.date) -> bytes:
    """Planilha das notas vendidas (Mercado Interno): aba "Resumo" (vendedor x mês, total, % e NF) e aba "Notas"
    (uma linha por nota, no formato do relatório de faturamento do Mega)."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    d = df.copy()
    d["EMISSAO"] = pd.to_datetime(d["EMISSAO"], errors="coerce")
    d["VALOR_TOTAL"] = pd.to_numeric(d["VALOR_TOTAL"], errors="coerce").fillna(0.0)
    d["VENDEDOR"] = d["VENDEDOR"].fillna("").astype(str).str.strip().replace("", "SEM VENDEDOR")
    d = d[d["EMISSAO"].dt.year == ano]
    d["MES"] = d["EMISSAO"].dt.month

    azul, claro, cinza = "1F3864", "D9E1F2", "F2F2F2"
    f_cab = Font(bold=True, color="FFFFFF")
    fill_cab = PatternFill("solid", start_color=azul, end_color=azul)
    fill_tot = PatternFill("solid", start_color=claro, end_color=claro)
    fino = Side(style="thin", color="D9D9D9")
    borda = Border(left=fino, right=fino, top=fino, bottom=fino)
    moeda = '#,##0.00;-#,##0.00;"-"'

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    ult = ate.month if ano == ate.year else 12
    meses = [f"{_MESES[m - 1].capitalize()}{'*' if (ano == ate.year and m == ate.month) else ''}" for m in range(1, ult + 1)]
    ws["A1"] = f"Notas vendidas — Mercado Interno · {ano}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (f"Valor total das notas por vendedor e mês de emissão · até {ate:%d/%m/%Y}"
                f"{' · *mês parcial' if ano == ate.year else ''} · sem notas canceladas · ações 161, 170, 288 e 326")
    ws["A2"].font = Font(italic=True, color="595959")
    cab = ["Vendedor"] + meses + [f"Total {ano}", "%", "NF"]
    for j, t in enumerate(cab, start=1):
        c = ws.cell(row=4, column=j, value=t)
        c.font, c.fill, c.border = f_cab, fill_cab, borda
        c.alignment = Alignment(horizontal="left" if j == 1 else "center", vertical="center")
    piv = d.pivot_table(index="VENDEDOR", columns="MES", values="VALOR_TOTAL", aggfunc="sum", fill_value=0.0)
    piv = piv.reindex(columns=range(1, ult + 1), fill_value=0.0)
    piv["_TOT"] = piv.sum(axis=1)
    notas = d.groupby("VENDEDOR").size()
    piv = piv.sort_values("_TOT", ascending=False)
    total_geral = float(piv["_TOT"].sum()) or 1.0
    r = 5
    for vend, linha in piv.iterrows():
        ws.cell(row=r, column=1, value=vend).border = borda
        for m in range(1, ult + 1):
            c = ws.cell(row=r, column=1 + m, value=float(linha[m]))
            c.number_format, c.border = moeda, borda
        c = ws.cell(row=r, column=ult + 2, value=float(linha["_TOT"]))
        c.number_format, c.border, c.font = moeda, borda, Font(bold=True)
        c = ws.cell(row=r, column=ult + 3, value=float(linha["_TOT"]) / total_geral)
        c.number_format, c.border = "0.00%", borda
        c = ws.cell(row=r, column=ult + 4, value=int(notas.get(vend, 0)))
        c.number_format, c.border = "#,##0", borda
        r += 1
    # linha de total: fórmulas somam as linhas acima
    ws.cell(row=r, column=1, value="TOTAL")
    for j in range(2, ult + 3):
        L = get_column_letter(j)
        ws.cell(row=r, column=j, value=f"=SUM({L}5:{L}{r - 1})").number_format = moeda
    ws.cell(row=r, column=ult + 3, value=f"=SUM({get_column_letter(ult + 3)}5:{get_column_letter(ult + 3)}{r - 1})").number_format = "0.00%"
    ws.cell(row=r, column=ult + 4, value=f"=SUM({get_column_letter(ult + 4)}5:{get_column_letter(ult + 4)}{r - 1})").number_format = "#,##0"
    for j in range(1, ult + 5):
        c = ws.cell(row=r, column=j)
        c.font, c.fill, c.border = Font(bold=True), fill_tot, borda
    ws.column_dimensions["A"].width = 46
    for j in range(2, ult + 3):
        ws.column_dimensions[get_column_letter(j)].width = 16
    ws.column_dimensions[get_column_letter(ult + 3)].width = 9
    ws.column_dimensions[get_column_letter(ult + 4)].width = 9
    ws.freeze_panes = "B5"

    wn = wb.create_sheet("Notas")
    colunas = [("Emissão", "EMISSAO", 12), ("Nota", "NOTA", 10), ("Código", "COD_CLIENTE", 10), ("Nome", "CLIENTE", 52),
               ("UF", "UF", 6), ("Valor Total", "VALOR_TOTAL", 16), ("Vendedor", "VENDEDOR", 44)]
    for j, (t, _, w) in enumerate(colunas, start=1):
        c = wn.cell(row=1, column=j, value=t)
        c.font, c.fill, c.border = f_cab, fill_cab, borda
        c.alignment = Alignment(horizontal="center", vertical="center")
        wn.column_dimensions[get_column_letter(j)].width = w
    for i, row in enumerate(d.sort_values(["EMISSAO", "NOTA"]).itertuples(index=False), start=2):
        reg = row._asdict()
        wn.cell(row=i, column=1, value=reg["EMISSAO"].to_pydatetime().date()).number_format = "dd/mm/yyyy"
        wn.cell(row=i, column=2, value=int(reg["NOTA"]))
        wn.cell(row=i, column=3, value=int(reg["COD_CLIENTE"]) if pd.notna(reg["COD_CLIENTE"]) else None)
        wn.cell(row=i, column=4, value=reg["CLIENTE"])
        wn.cell(row=i, column=5, value=reg["UF"])
        wn.cell(row=i, column=6, value=float(reg["VALOR_TOTAL"])).number_format = moeda
        wn.cell(row=i, column=7, value=reg["VENDEDOR"])
    wn.freeze_panes = "A2"
    wn.auto_filter.ref = f"A1:G{max(len(d) + 1, 2)}"

    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto).upper()) if unicodedata.category(c) != "Mn")


def _selo(bloqueado: bool) -> str:
    cor, fundo, txt = (_VERMELHO, "rgba(239,68,68,0.16)", "Bloqueado") if bloqueado else (_VERDE, "rgba(34,197,94,0.13)", "Liberado")
    return (f'<span style="display:inline-flex;align-items:center;border-radius:999px;padding:1px 10px;font-size:11px;'
            f'font-weight:600;white-space:nowrap;background:{fundo};color:{cor}">● {txt}</span>')


def _tabela_bloqueios(df_mi: pd.DataFrame, df_grupo_agentes, df_grupo_geral, ocultar: bool) -> None:
    """Situação Grupo de Crédito: todos os grupos de crédito (limite zerado ou não; mercado interno e externo), com ou
    sem título em aberto (os títulos em aberto são os do Mercado Interno). Faturamento = título em aberto com prorrogação vencida; Documentação = situação do grupo."""
    st.markdown("#### Situação Grupo de Crédito")
    if (df_grupo_geral is None or df_grupo_geral.empty or df_grupo_agentes is None or df_grupo_agentes.empty
            or not {"GRUPO_CODIGO", "NOME_GRUPO", "VALOR_LIMITE"}.issubset(df_grupo_geral.columns)
            or not {"COD_AGENTE", "COD_GRUPO"}.issubset(df_grupo_agentes.columns)):
        st.info("Dados do Grupo de Crédito indisponíveis.")
        return

    g = df_grupo_geral.drop_duplicates("GRUPO_CODIGO").copy()
    g["_LIM"] = pd.to_numeric(g["VALOR_LIMITE"], errors="coerce").fillna(0)
    ag = df_grupo_agentes.copy()
    ag["_COD"] = ag["COD_AGENTE"].astype(str)
    g = g.set_index("GRUPO_CODIGO")      # todos os grupos de crédito: mercado interno e externo, com limite zerado ou não

    # Títulos em aberto do Mercado Interno por grupo
    d = df_mi[pd.to_numeric(df_mi["SALDO_EM_ABERTO"], errors="coerce").fillna(0) > 0].copy()
    d["SALDO_EM_ABERTO"] = pd.to_numeric(d["SALDO_EM_ABERTO"], errors="coerce").fillna(0)
    d["_PROR"] = pd.to_datetime(d["PRORROGADO"], errors="coerce")
    d["_GRP"] = d["COD_CLIENTE"].astype(str).map(ag.drop_duplicates("_COD").set_index("_COD")["COD_GRUPO"])
    d = d.dropna(subset=["_GRP"])
    hoje = pd.Timestamp(datetime.date.today())
    abertos = {}
    for cod, x in d.groupby("_GRP"):
        atrasados = x["_PROR"].dropna()
        atrasados = atrasados[atrasados < hoje]
        abertos[cod] = (
            x["SALDO_EM_ABERTO"].sum(),
            x.loc[x["SITUACAO"] == "VENCIDO", "SALDO_EM_ABERTO"].sum() if "SITUACAO" in x.columns else 0.0,
            (hoje - atrasados.min()).days if not atrasados.empty else None,
        )
    nomes_agentes = ag.groupby("COD_GRUPO")["NOME_AGENTE"].apply(lambda s: " ".join(s.astype(str))) if "NOME_AGENTE" in ag.columns else {}

    linhas = []
    for cod, r in g.iterrows():
        aberto, venc, dias = abertos.get(cod, (0.0, 0.0, None))
        sit = str(r.get("SITUACAO_CLIENTE", "")).upper()
        busca_txt = f"{r['NOME_GRUPO']} {nomes_agentes.get(cod, '')}"
        linhas.append((str(r["NOME_GRUPO"]), dias is not None, "BLOQ" in sit, r["_LIM"], aberto, venc, dias, busca_txt))
    todos = pd.DataFrame(linhas, columns=["grupo", "fat", "doc", "limite", "aberto", "vencido", "dias", "busca"])
    if todos.empty:
        st.info("Nenhum grupo de crédito encontrado.")
        return

    busca = st.text_input("Pesquisar cliente ou grupo", key="vgc_busca_cliente",
                          placeholder="Mostra só os bloqueados; ao pesquisar, procura entre todos os grupos…")
    bloq = todos
    if busca.strip():
        bloq = bloq[bloq["busca"].map(_sem_acento).str.contains(_sem_acento(busca.strip()), regex=False)]
    if not busca.strip():     # sem pesquisa: só os bloqueados; pesquisando, procura entre todos
        bloq = bloq[bloq["fat"] | bloq["doc"]]
    n_fat, n_doc, n_tot = int(todos["fat"].sum()), int(todos["doc"].sum()), len(todos)
    n_bloq = int((todos["fat"] | todos["doc"]).sum())
    n_aberto = int((todos["aberto"] > 0).sum())

    fmt = lambda v: "R$ ••••••" if ocultar else "R$ " + formatar_moeda(v).replace("R$", "").strip()
    selo_n = lambda n, b: (f'<span style="border-radius:999px;padding:1px 10px;font-size:11px;font-weight:600;'
                           f'background:{"rgba(239,68,68,0.16)" if b else "rgba(34,197,94,0.13)"};'
                           f'color:{_VERMELHO if b else _VERDE}">{n} {"bloqueados" if b else "liberados"}</span>')
    cab = (
        f'<div style="display:flex;gap:6px;align-items:center"><b style="color:#fff">Faturamento</b>{selo_n(n_fat, True)}</div>'
        f'<div style="display:flex;gap:6px;align-items:center"><b style="color:#fff">Documentação</b>{selo_n(n_doc, True)}</div>'
        f'<span style="margin-left:auto;color:#8892a4">{n_tot} grupos · {n_aberto} com título em aberto · {n_bloq} com algum bloqueio'
        f'{" · pesquisa: " + str(len(bloq)) + " exibido(s)" if busca.strip() else ""}</span>'
    )
    if bloq.empty:
        corpo = '<div style="color:#8892a4;padding:8px 0">Nenhum cliente encontrado.</div>'
    else:
        bloq = bloq.assign(ambos=bloq["fat"] & bloq["doc"], algum=bloq["fat"] | bloq["doc"]).sort_values(
            ["ambos", "algum", "aberto", "limite"], ascending=[False, False, False, False])
        cab_col = lambda t, r=False: (f'<span style="color:#8892a4;font-size:11px;position:sticky;top:0;background:#1e1e2e;z-index:1;'
                                      f'padding-bottom:4px;{"text-align:right" if r else ""}">{t}</span>')
        corpo = (
            '<div style="display:grid;grid-template-columns:minmax(0,1fr) 105px 115px 120px 120px 115px 46px;gap:7px 10px;align-items:center;font-size:13px;'
            'max-height:340px;overflow-y:scroll;padding-right:6px;scrollbar-width:auto;scrollbar-color:#6b7690 #2a2a3a">'
            + cab_col("Grupo") + cab_col("Faturamento") + cab_col("Documentação") + cab_col("Limite", True)
            + cab_col("Em aberto", True) + cab_col("Vencido", True) + cab_col("Dias", True)
        )
        vazio = '<span style="color:#8892a4;text-align:right">—</span>'
        for r in bloq.itertuples():
            nome = r.grupo if len(r.grupo) <= 38 else r.grupo[:37] + "…"
            aberto = f'<span style="color:#fff;text-align:right;white-space:nowrap">{fmt(r.aberto)}</span>' if r.aberto > 0 else vazio
            venc = f'<span style="color:{_VERMELHO};text-align:right;white-space:nowrap">{fmt(r.vencido)}</span>' if r.vencido > 0 else vazio
            if pd.isna(r.dias):
                dias = vazio
            else:
                dias = (f'<span style="color:{_VERMELHO if int(r.dias) > 30 else _AMBAR};text-align:right;font-weight:600">'
                        f'{"••" if ocultar else int(r.dias)}</span>')
            corpo += (
                f'<span style="color:#e0e0e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{r.grupo}">{nome}</span>'
                f'<span>{_selo(r.fat)}</span><span>{_selo(r.doc)}</span>'
                f'<span style="color:#8892a4;text-align:right;white-space:nowrap">{fmt(r.limite)}</span>{aberto}{venc}{dias}'
            )
        corpo += "</div>"
    st.markdown(
        f'<div style="background:#1e1e2e;border-radius:12px;padding:14px 18px;border-top:4px solid {_AMBAR};box-sizing:border-box">'
        f'<div style="display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin-bottom:10px;font-size:12px">{cab}</div>{corpo}'
        '<div style="height:1px;background:#2a2a3a;margin:10px 0 6px"></div>'
        '<span style="color:#8892A4;font-size:11px">Todos os grupos de crédito (limite zerado ou não; Mercado Interno e Externo), com ou sem título em aberto · '
        'Faturamento: título em aberto com prorrogação vencida · Documentação: situação do Grupo de Crédito · Dias: desde a prorrogação mais antiga</span></div>',
        unsafe_allow_html=True,
    )


def render(df_cr: pd.DataFrame, df_grupo_agentes=None, df_grupo_geral=None) -> None:
    if "cr_ocultar" not in st.session_state:
        st.session_state["cr_ocultar"] = False
    oc = st.session_state["cr_ocultar"]

    col_t, col_btn, col_at = st.columns([9, 1.4, 1.4])
    with col_t:
        st.title("Visão Geral Comercial - MI")
    with col_btn:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("Ocultar" if not oc else "Exibir", icon=":material/visibility_off:" if not oc else ":material/visibility:",
                     key="btn_ocultar_vgc", use_container_width=True, help="Ocultar/exibir valores"):
            st.session_state["cr_ocultar"] = not oc
            st.rerun()
    with col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="vgc_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if df_cr is None or df_cr.empty or "MERCADO" not in df_cr.columns:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return
    df_mi = df_cr[df_cr["MERCADO"] == "MI"].copy()
    for c in ("SALDO_EM_ABERTO", "DIAS"):
        if c in df_mi.columns:
            df_mi[c] = pd.to_numeric(df_mi[c], errors="coerce")
    oc = st.session_state["cr_ocultar"]

    _faturamento_12_meses(oc)
    st.divider()

    df_mi = classificar_vencidos(df_mi)
    # vencido sem o PDD (acima do limite de dias o título é PDD e sai do vencido)
    df_venc = df_mi[(df_mi["CLASSIF_VENCIDO"] == "VENCIDO") & (df_mi["SALDO_EM_ABERTO"].fillna(0) > 0)].copy()
    c1, c2 = st.columns(2)
    with c1:
        _ranking_clientes(df_mi, ocultar=oc, df_grupo_agentes=df_grupo_agentes, df_grupo_geral=df_grupo_geral, altura_lista=445)
    with c2:
        if df_venc.empty:
            st.markdown("#### Vencido por Cliente")
            st.success("Nenhum título vencido.")
        else:
            _bloco_vencido_por_cliente(df_mi, df_venc, oc)
        bloco = _bloco_faixas_vencido(df_venc, ocultar=oc)
        if bloco:
            st.markdown("#### Vencido por Faixa de Atraso")
            st.markdown(bloco, unsafe_allow_html=True)

    st.divider()
    _tabela_bloqueios(df_mi, df_grupo_agentes, df_grupo_geral, oc)
