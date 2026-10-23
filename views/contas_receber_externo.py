"""
views/contas_receber_externo.py
================================
Painel Contas a Receber — Mercado Externo.

Usa a mesma consulta do Contas a Receber (QUERY_CONTAS_RECEBER.sql), só com
MERCADO = 'ME'. Os valores ficam na moeda de origem (SALDO_MOEDA) e em reais
(SALDO_EM_ABERTO); nunca soma moedas diferentes entre si.
"""

import base64

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel, botoes_acao_row
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.exporters import adicionar_aba_ptax, exportar_excel
from utils.imagem_email import gerar_imagem_painel_externo
from utils.prazos import calcular_dias_prazo, formatar_dias_html, formatar_dias_unificado_html, nullar_zeros_dias, VERDE_DIAS, VERMELHO_DIAS
from utils.ptax import (
    buscar_historico_ptax, buscar_ptax, buscar_ptax_mes_anterior_e_vigente,
    limpar_cache_ptax, link_bcb,
)

_SIMBOLOS = {"USD": "US$", "EUR": "€", "GBP": "£"}
_NOMES = {"USD": "Dólar", "EUR": "Euro", "GBP": "Libra"}
_ORDEM_FAIXAS = [
    "Vencido 30+ dias", "Vencido até 30 dias", "A vencer até 30 dias",
    "A vencer 31 a 60 dias", "A vencer 61 a 90 dias", "A vencer 90+ dias",
]
_CORES_FAIXAS = {
    "Vencido 30+ dias":    "#791F1F",
    "Vencido até 30 dias": "#E24B4A",
    "A vencer até 30 dias":   "#22c55e",
    "A vencer 31 a 60 dias":  "#BA7517",
    "A vencer 61 a 90 dias":  "#E8724A",
    "A vencer 90+ dias":      "#6366f1",
}
_OPAC = ["1","1","1","0.70","0.55","0.45","0.38","0.32","0.28","0.24","0.21","0.18"]


def _barras_ranking(df_rank, valor_col: str, total: float, unidade: str,
                    cor: str, ocultar: bool, titulo: str = "") -> None:
    maximo = df_rank[valor_col].max() or 1
    linhas = ""
    for i, (_, row) in enumerate(df_rank.iterrows()):
        opac = _OPAC[i] if i < len(_OPAC) else "0.18"
        pct  = row[valor_col] / total * 100 if total else 0
        barw = row[valor_col] / maximo * 100
        nome = row["CLIENTE"]
        if len(nome) > 32:
            nome = nome[:31] + "…"
        pct_txt = "••" if ocultar else f"{pct:.2f}%"
        val_txt = "••••••" if ocultar else f"{unidade} {_num(row[valor_col])}"
        linhas += (
            f'<div style="display:grid;grid-template-columns:18px minmax(0,1fr) 42px minmax(0,1fr) 130px;'
            f'gap:8px;align-items:center;font-size:13px;padding:2px 0">'
            f'<span style="color:#8892A4;font-size:11px;font-weight:600;text-align:center">{i+1}</span>'
            f'<span style="color:#e0e0e0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{nome}</span>'
            f'<span style="color:{cor};font-size:11px;font-weight:600;text-align:right;white-space:nowrap">{pct_txt}</span>'
            f'<div style="height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div style="width:{barw:.1f}%;height:100%;background:{cor};opacity:{opac}"></div></div>'
            f'<span style="color:#ffffff;font-size:12px;text-align:right;white-space:nowrap">{val_txt}</span>'
            f'</div>'
        )
    # título fica fora da caixa, como no Mercado Interno
    if titulo:
        st.markdown(
            f'<div style="font-size:14px;font-weight:600;color:#ffffff;margin:0 0 6px">{titulo}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px;width:100%">'
        + '<div style="color:#8892A4;font-size:11px;margin-bottom:8px">% sobre saldo total em aberto</div>'
        + linhas
        + '</div>',
        unsafe_allow_html=True,
    )


def _barras_aging(ag: "pd.DataFrame", valor_col: str, unidade: str,
                  ocultar: bool) -> None:
    if ag.empty:
        return
    total  = ag[valor_col].sum() or 1
    maximo = ag[valor_col].max() or 1
    linhas = ""
    for _, row in ag.iterrows():
        faixa = row["FAIXA_DIAS"]
        val   = row[valor_col]
        cor   = _CORES_FAIXAS.get(faixa, "#6366f1")
        barw  = val / maximo * 100
        val_txt = "••••••" if ocultar else f"{unidade} {_num(val)}"
        linhas += (
            f'<div style="display:grid;grid-template-columns:160px minmax(0,1fr) 150px;gap:12px;'
            f'align-items:center;font-size:13px;padding:5px 0">'
            f'<span style="color:#e0e0e0;">{faixa}</span>'
            f'<div style="height:14px;border-radius:4px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div style="width:{barw:.1f}%;height:100%;background:{cor}"></div></div>'
            f'<span style="color:#8892A4;text-align:right;">{val_txt}</span></div>'
        )
    venc_v  = ag.loc[ag["grupo"] == "Vencido",   valor_col].sum()
    avenc_v = ag.loc[ag["grupo"] == "A vencer",  valor_col].sum()
    total_fmt = "••••••" if ocultar else f"{unidade} {_num(total)}"
    rodape = (
        f"Vencido: {unidade} {_num(venc_v)}  ·  A vencer: {unidade} {_num(avenc_v)}"
        if not ocultar else "••••••"
    )
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px;width:100%">'
        + linhas
        + '<div style="height:1px;background:#2a2a3a;margin:10px 0"></div>'
        + '<div style="display:flex;justify-content:space-between">'
        + f'<span style="color:#8892A4;font-size:11px">{rodape}</span>'
        + f'<span style="color:#e0e0e0;font-size:13px;font-weight:600">Total: {total_fmt}</span>'
        + '</div></div>',
        unsafe_allow_html=True,
    )


_CORES_PTAX = {"EUR": "#4A7FB5", "GBP": "#9B59B6", "USD": "#27AE60"}
_DIAS_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _sparkline_svg(hist: list, cor: str) -> str:
    """Gera sparkline SVG inline a partir do histórico (mais antigo → mais recente)."""
    if len(hist) < 2:
        return ""
    dados = [h["venda"] for h in reversed(hist)]
    vmin, vmax = min(dados), max(dados)
    span = vmax - vmin or 0.0001
    W, H = 160, 32
    pts = []
    for i, v in enumerate(dados):
        x = i / (len(dados) - 1) * W
        y = H - ((v - vmin) / span) * (H - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(pts)
    poly_closed = polyline + f" {W},{H} 0,{H}"
    grad_id = f"sg_{cor[1:]}"
    return (
        f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" '
        f'style="width:100%;height:32px;display:block">'
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{cor}" stop-opacity="0.3"/>'
        f'<stop offset="100%" stop-color="{cor}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{poly_closed}" fill="url(#{grad_id})"/>'
        f'<polyline points="{polyline}" fill="none" stroke="{cor}" stroke-width="1.5"/>'
        f'<circle cx="{pts[-1].split(",")[0]}" cy="{pts[-1].split(",")[1]}" r="2.5" fill="{cor}"/>'
        f'</svg>'
    )


def _bloco_cartao(idx: int, moeda: str, frente_html: str, hist: list) -> str:
    """Um card de cotação que gira: a seta no canto superior direito vira o card.
    O verso mostra só os últimos 5 dias úteis, com o botão Excel (só ícone) que exporta os 30 dias."""
    cor = _CORES_PTAX[moeda]
    if not hist:
        return f'<div class="cena">{frente_html}</div>'
    linhas = "".join(
        f'<div class="g"><span>{_DIAS_CURTOS[h["data"].weekday()]}</span>'
        f'<span>{h["data"].strftime("%d/%m")}</span>'
        f'<span class="n">{_fmt4(h["venda"])}</span>'
        f'<span class="n">{_fmt4(h["compra"])}</span></div>'
        for h in hist[:5]
    )
    xlsx = _excel_historico(moeda, hist)
    link_xlsx = f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{base64.b64encode(xlsx).decode()}"
    gid = f"g{idx}"
    return f"""<div class="cena"><div class="giro" id="{gid}">
<div class="face frente">{frente_html}<button class="seta" aria-label="Ver histórico" title="Ver histórico" onclick="virar('{gid}',true)">↗</button></div>
<div class="face verso" style="border-left:4px solid {cor}">
<div class="topo"><span class="titulo">{moeda}/BRL</span>
<span class="acoes"><a class="ico" href="{link_xlsx}" download="PTAX_{moeda}_BRL.xlsx" title="Exportar para Excel" aria-label="Exportar para Excel"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/></svg></a>
<button class="voltar" aria-label="Voltar" title="Voltar" onclick="virar('{gid}',false)">↩</button></span></div>
<div class="cab"><span>Dia</span><span>Data</span><span class="n">Venda</span><span class="n">Compra</span></div>
{linhas}
</div>
</div></div>"""


_CSS_CARTOES = """
body{margin:0;background:transparent;font-family:"Source Sans Pro",Arial,sans-serif;color:#E8EAF0}
.linha{display:flex;gap:12px;align-items:flex-start}
.cena{position:relative;width:240px;height:176px;perspective:1000px;flex:0 0 240px}
.linha.grade{display:grid;align-items:stretch}
.linha.grade .cena{width:auto;height:192px;flex:none;min-width:0}
.linha.grade .cena>.cm{height:100%;box-sizing:border-box}
.giro{position:relative;width:100%;height:100%;transform-style:preserve-3d;transition:transform .6s}
.giro.virado{transform:rotateY(180deg)}
.face{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden}
.frente>div{height:100%;box-sizing:border-box}
.seta{position:absolute;top:6px;right:8px;z-index:2;background:none;border:none;color:#8892A4;font-size:14px;cursor:pointer;padding:2px 4px;line-height:1}
.seta:hover{color:#E8EAF0}
.verso{transform:rotateY(180deg);background:#252D3F;border-radius:8px;box-sizing:border-box;padding:12px 14px;height:100%}
.topo{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.titulo{font-size:13px;color:#ffffff;text-transform:uppercase}
.acoes{display:flex;align-items:center;gap:4px}
.ico{display:inline-flex;align-items:center;justify-content:center;width:26px;height:22px;border:0.5px solid #323D56;border-radius:6px;color:#378ADD;text-decoration:none}
.voltar{background:none;border:none;color:#8892A4;font-size:14px;cursor:pointer;padding:2px 4px;line-height:1}
.cab,.g{display:grid;grid-template-columns:30px 44px 1fr 1fr;font-size:11px;padding:4px 0;border-bottom:0.5px solid #323D56}
.cab{color:#8892A4}
.n{text-align:right}
.cm{background:#1e1e2e;border-left:4px solid var(--c);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:2px}
.l1{font-size:12px;color:#aab;padding-right:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.l1 em{font-style:normal;color:#6b7488;margin-left:4px}
.big{font-size:21px;font-weight:600;color:#fff;margin:1px 0 3px;white-space:nowrap}
.l2{font-size:11px;color:#8892A4;white-space:nowrap}.l2 b{color:#c9d1e6;font-weight:500}
.dif{display:inline-block;align-self:flex-start;margin-top:4px;padding:1px 7px;border-radius:5px;font-size:11px;font-weight:500}
.mm{display:flex;justify-content:space-between;margin-top:2px}.mm span,.mm a{font-size:10px}
"""
_JS_CARTOES = "<script>function virar(id,on){document.getElementById(id).classList.toggle('virado',on);}</script>"


def _documento_cartoes(blocos: list[str], colunas: int | None = None) -> str:
    """Sem `colunas`: cartões de 240 px em linha (usado também no relatório Variação Cambial ME).
    Com `colunas`: grade de largura total, `colunas` cartões por linha."""
    if colunas:
        linha = f'<div class="linha grade" style="grid-template-columns:repeat({colunas},minmax(0,1fr))">'
    else:
        linha = '<div class="linha">'
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{_CSS_CARTOES}</style></head>'
            f'<body>{linha}{"".join(blocos)}</div>{_JS_CARTOES}</body></html>')


def _fmt4(v: float) -> str:
    return f"{v:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _excel_historico(moeda: str, hist: list) -> bytes:
    df = pd.DataFrame({
        "Dia": [_DIAS_CURTOS[h["data"].weekday()] for h in hist],
        "Data": [h["data"].strftime("%d/%m/%Y") for h in hist],
        "PTAX Venda": [h["venda"] for h in hist],
        "PTAX Compra": [h["compra"] for h in hist],
    })
    return exportar_excel(df, f"PTAX {moeda}")


def _badge_dif(dif: float, pct: float, ocultar: bool) -> str:
    """Selo da diferença cambial (PTAX × cotação do faturamento): vermelho = perda, verde = ganho."""
    cor = "#4caf7a" if dif >= 0 else "#E24B4A"
    bg = "rgba(76,175,122,0.12)" if dif >= 0 else "rgba(226,75,74,0.12)"
    seta = "▲" if dif >= 0 else "▼"
    valor = "••••••" if ocultar else _num(abs(dif))
    perc = "••" if ocultar else f"{abs(pct):.2f}%"
    return f'<span class="dif" style="color:{cor};background:{bg}">{seta} R$ {valor} ({perc})</span>'


def _frente_cartao(cor: str, titulo: str, valor_grande: str, linhas: list, dif_html: str = "",
                   spark_html: str = "", rodape_html: str = "") -> str:
    corpo = "".join(f'<div class="l2">{l}</div>' for l in linhas)
    return (f'<div class="cm" style="--c:{cor}"><div class="l1">{titulo}</div>'
            f'<div class="big">{valor_grande}</div>{corpo}{dif_html}{spark_html}{rodape_html}</div>')


# Bloco inteiro de cotações (um cartão por moeda, impacto cambial e gráfico da diferença) atualizado a cada 1 hora.
# O botão ↻ Atualizar PTAX recarrega só este bloco, não a página inteira.
@st.fragment(run_every=3300)
def _render_ptax_bloco(df_me: pd.DataFrame, moeda_filtro: str = "Todas") -> None:
    ocultar = st.session_state.get("cr_ocultar", False)
    _oculto = lambda v: "••••••" if ocultar else _num(v)
    col_cap, col_atu = st.columns([9, 1.4])
    with col_atu:
        atualizar = st.button("↻ Atualizar PTAX", key="ptax_atualizar", width="stretch")
    if atualizar:
        limpar_cache_ptax()
    ptax = buscar_ptax()
    data_ref = ptax["data_ref"].strftime("%d/%m/%Y")
    with col_cap:
        st.caption(f"Cotação PTAX {data_ref} · Fonte: BCB · variação vs D-2")

    _FLAGS = {"EUR": "🇪🇺", "GBP": "🇬🇧", "USD": "🇺🇸"}
    _COR_MOEDA = {"EUR": "#4A7FB5", "GBP": "#9B59B6", "USD": "#27AE60"}
    _moedas_exibir = ("EUR", "GBP", "USD") if moeda_filtro == "Todas" else (moeda_filtro,)

    # ── dados por moeda: saldo na moeda, na cotação do faturamento e pela PTAX de venda ──
    dados = {}
    for m in _moedas_exibir:
        sub = df_me[df_me["MOEDA"] == m]
        saldo_m = float(sub["SALDO_MOEDA"].sum())
        if saldo_m <= 0:
            continue
        d = ptax.get(m)
        taxa = d["venda"] if d else None
        dados[m] = {"saldo_m": saldo_m, "saldo_fat": float(sub["SALDO_EM_ABERTO"].sum()), "d": d,
                    "taxa": taxa, "saldo_brl": saldo_m * taxa if taxa else None}
    if not dados:
        st.info("Sem saldo em moeda estrangeira para exibir.")
        return

    com_ptax = {m: v for m, v in dados.items() if v["saldo_brl"] is not None}
    total_ptax = sum(v["saldo_brl"] for v in com_ptax.values())
    fat_total = sum(v["saldo_fat"] for v in com_ptax.values())

    # ── um cartão por moeda (+ total): saldo, PTAX, diferença cambial e PTAX dos últimos 30 dias ──
    blocos = []
    for i, (m, v) in enumerate(dados.items()):
        cor_m, d, hist_m = _COR_MOEDA[m], v["d"], buscar_historico_ptax(m, 30)
        simbolo = _SIMBOLOS.get(m, m)
        linhas, dif_html, spark_html, rodape = [], "", "", ""
        if d:
            var = d.get("var_venda")
            var_html = ""
            if var is not None:
                cor_v = "#4caf7a" if var >= 0 else "#E24B4A"
                var_html = f' <span style="color:{cor_v}">{"▲" if var >= 0 else "▼"} {abs(var):.2f}%</span>'
            linhas.append(f'PTAX <b>R$ {_fmt4(v["taxa"])}</b>{var_html}')
            linhas.append(f'Valor Atualizado <b>R$ {_oculto(v["saldo_brl"])}</b>')
            linhas.append(f'Cot. fat. R$ {_oculto(v["saldo_fat"])}')
            dif = v["saldo_brl"] - v["saldo_fat"]
            pct = (dif / v["saldo_fat"] * 100) if v["saldo_fat"] else 0
            dif_html = _badge_dif(dif, pct, ocultar)
        else:
            linhas.append("PTAX indisponível")
            linhas.append(f'Cot. fat. R$ {_oculto(v["saldo_fat"])}')
        if hist_m:
            vendas = [h["venda"] for h in hist_m]
            spark_html = f'<div style="margin-top:6px">{_sparkline_svg(hist_m, cor_m)}</div>'
            rodape = (f'<div class="mm"><span style="color:#555e72">máx/mín 30d</span>'
                      f'<span style="color:#4caf7a">↑ {_fmt4(max(vendas))}</span>'
                      f'<span style="color:#E24B4A">↓ {_fmt4(min(vendas))}</span>'
                      f'<a href="{link_bcb()}" target="_blank" style="color:{cor_m};text-decoration:none">BCB ↗</a></div>')
        frente = _frente_cartao(cor_m, f'{_NOMES[m]}<em>{m}/BRL</em>',
                                f'{simbolo} {_oculto(v["saldo_m"])}', linhas, dif_html, spark_html, rodape)
        blocos.append(_bloco_cartao(i, m, frente, hist_m))

    if len(dados) > 1 and com_ptax:
        dif_t = total_ptax - fat_total
        pct_t = (dif_t / fat_total * 100) if fat_total else 0
        linhas_t = [f'Valor Faturamento <b>R$ {_oculto(fat_total)}</b>']
        cor_t = "#4caf7a" if dif_t >= 0 else "#E24B4A"
        var_html = (
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:6px;'
            f'padding-top:6px;border-top:1px solid #2a2a3e"><span style="font-size:11px;color:#8892A4;white-space:nowrap">Variação cambial</span>'
            f'<span style="font-size:14px;font-weight:600;white-space:nowrap;color:{cor_t}">{"-" if dif_t < 0 else "+"}R$ {_oculto(abs(dif_t))} '
            f'<small style="font-size:11px;font-weight:400">({"••" if ocultar else f"{abs(pct_t):.2f}%"})</small></span></div>'
        )
        barra_html = ""
        if len(com_ptax) > 1 and not ocultar:
            soma_abs = sum(abs(v["saldo_brl"] - v["saldo_fat"]) for v in com_ptax.values()) or 1
            partes = [(m, abs(v["saldo_brl"] - v["saldo_fat"]) / soma_abs * 100) for m, v in com_ptax.items()]
            partes.sort(key=lambda x: -x[1])
            segmentos = "".join(f'<span style="width:{pt:.2f}%;background:{_COR_MOEDA[m]}"></span>' for m, pt in partes)
            legenda = "".join(
                f'<span><i style="display:inline-block;width:7px;height:7px;border-radius:2px;margin-right:3px;'
                f'background:{_COR_MOEDA[m]}"></i>{_SIMBOLOS.get(m, m)} {pt:.0f}%</span>' for m, pt in partes
            )
            barra_html = (
                '<div style="display:flex;height:7px;border-radius:4px;overflow:hidden;margin:8px 0 4px">' + segmentos + '</div>'
                '<div style="display:flex;gap:10px;font-size:10px;color:#8892A4;flex-wrap:wrap">'
                + legenda + '</div>'
            )
        blocos.append(f'<div class="cena">{_frente_cartao("#6366f1", "Valor Atualizado<em>PTAX · venda D-1</em>", "R$ " + _oculto(total_ptax), linhas_t, var_html, "", barra_html)}</div>')

    st.iframe(_documento_cartoes(blocos, 4), height=204)
    # ── impacto cambial: tabela à esquerda e gráfico da diferença por moeda à direita ──
    if not com_ptax:
        return
    dif_total = total_ptax - fat_total
    pct_total = (dif_total / fat_total * 100) if fat_total else 0
    cols_grid = "62px 1fr 1fr 112px 1fr 1fr 62px"
    linhas_imp = ""
    for m, v in com_ptax.items():
        dif = v["saldo_brl"] - v["saldo_fat"]
        pct = (dif / v["saldo_fat"] * 100) if v["saldo_fat"] else 0
        cor = "#4caf7a" if dif >= 0 else "#E24B4A"
        seta = "▲" if dif >= 0 else "▼"
        linhas_imp += (
            f'<div style="display:grid;grid-template-columns:{cols_grid};gap:4px 10px;padding:6px 0;'
            f'border-bottom:1px solid rgba(42,42,62,0.5);font-size:12px;align-items:center">'
            f'<span style="color:#8892A4">{_FLAGS[m]} {m}</span>'
            f'<span style="color:#8892A4;white-space:nowrap">{_SIMBOLOS.get(m, m)} {_oculto(v["saldo_m"])}</span>'
            f'<span style="color:#e0e0e0;white-space:nowrap">R$ {_oculto(v["saldo_fat"])}</span>'
            f'<span style="color:#8892A4;white-space:nowrap">{_fmt4(v["taxa"])}</span>'
            f'<span style="color:#e0e0e0;white-space:nowrap">R$ {_oculto(v["saldo_brl"])}</span>'
            f'<span style="color:{cor};white-space:nowrap">{seta} R$ {_oculto(abs(dif))}</span>'
            f'<span style="color:{cor};white-space:nowrap;font-weight:500">{seta} {"••" if ocultar else f"{abs(pct):.2f}%"}</span>'
            f'</div>'
        )
    rodape_imp = ""
    if len(com_ptax) > 1:
        cor_t = "#4caf7a" if dif_total >= 0 else "#E24B4A"
        seta_t = "▲" if dif_total >= 0 else "▼"
        rodape_imp = (
            f'<div style="display:grid;grid-template-columns:{cols_grid};gap:4px 10px;padding:8px 0 0;'
            f'font-size:12px;font-weight:500;align-items:center">'
            f'<span style="color:#e0e0e0">Total</span><span></span>'
            f'<span style="color:#e0e0e0;white-space:nowrap">R$ {_oculto(fat_total)}</span><span></span>'
            f'<span style="color:#e0e0e0;white-space:nowrap">R$ {_oculto(total_ptax)}</span>'
            f'<span style="color:{cor_t};white-space:nowrap">{seta_t} R$ {_oculto(abs(dif_total))}</span>'
            f'<span style="color:{cor_t};white-space:nowrap">{seta_t} {"••" if ocultar else f"{abs(pct_total):.2f}%"}</span>'
            f'</div>'
        )
    cabecalho = (
        f'<div style="display:grid;grid-template-columns:{cols_grid};gap:4px 10px;padding-bottom:6px;'
        f'border-bottom:1px solid #2a2a3e;font-size:11px;color:#8892A4">'
        f'<span>Moeda</span><span>Valor Moeda</span><span>Valor Faturamento</span><span style="white-space:nowrap">PTAX {data_ref}</span>'
        f'<span>Valor Atualizado</span><span>Diferença</span><span>Valoriz. %</span></div>'
    )
    # gráfico da diferença: perdas saem para a esquerda do eixo, ganhos para a direita
    maximo = max(abs(v["saldo_brl"] - v["saldo_fat"]) for v in com_ptax.values()) or 1
    linhas_graf = ""
    for m, v in sorted(com_ptax.items(), key=lambda kv: -abs(kv[1]["saldo_brl"] - kv[1]["saldo_fat"])):
        dif = v["saldo_brl"] - v["saldo_fat"]
        larg = abs(dif) / maximo * 50
        if dif < 0:
            barra = (f'<i class="an-wipe" style="position:absolute;top:0;bottom:0;right:50%;width:{larg:.1f}%;'
                     f'background:#E24B4A;border-radius:5px 0 0 5px"></i>')
        else:
            barra = (f'<i class="an-wipe" style="position:absolute;top:0;bottom:0;left:50%;width:{larg:.1f}%;'
                     f'background:#1BADA6;border-radius:0 5px 5px 0"></i>')
        cor_v = "#E24B4A" if dif < 0 else "#4caf7a"
        linhas_graf += (
            f'<div style="display:grid;grid-template-columns:40px 1fr 96px;align-items:center;gap:8px;margin:12px 0;font-size:12px">'
            f'<span style="color:#c9d1e6">{m}</span>'
            f'<div style="position:relative;height:12px;background:#262b3b;border-radius:5px">{barra}'
            f'<span style="position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:#6b7488"></span></div>'
            f'<span style="text-align:right;color:{cor_v};font-weight:500">{"-" if dif < 0 else "+"}R$ {_oculto(abs(dif))}</span></div>'
        )
    if len(com_ptax) > 1:
        cor_g = "#E24B4A" if dif_total < 0 else "#4caf7a"
        linhas_graf += (
            f'<div style="display:grid;grid-template-columns:40px 1fr auto;gap:8px;align-items:center;margin:14px 0 2px;'
            f'padding-top:10px;border-top:1px solid #2a2a3e;font-size:12px">'
            f'<span style="color:#e0e0e0;font-weight:500">Total</span>'
            f'<span style="color:#8892A4;font-size:11px">{"••" if ocultar else f"{abs(pct_total):.2f}%"} sobre o faturado</span>'
            f'<span style="text-align:right;white-space:nowrap;color:{cor_g};font-weight:600">{"-" if dif_total < 0 else "+"}R$ {_oculto(abs(dif_total))}</span></div>'
        )
    c_tab, c_graf = st.columns([1.6, 1])
    with c_tab:
        st.markdown(
            f'<div style="background:#1e1e2e;border-radius:10px;padding:14px 16px;margin-top:6px">'
            f'<div style="font-size:13px;font-weight:500;color:#e0e0e0;margin-bottom:10px">'
            f'Impacto cambial — faturamento vs PTAX {data_ref}</div>'
            + cabecalho + linhas_imp + rodape_imp + '</div>',
            unsafe_allow_html=True,
        )
    with c_graf:
        st.markdown(
            f'<div style="background:#1e1e2e;border-radius:10px;padding:14px 16px;margin-top:6px">'
            f'<div style="font-size:13px;font-weight:500;color:#e0e0e0;margin-bottom:2px">Diferença cambial por moeda</div>'
            f'<div style="font-size:11px;color:#8892A4">perda à esquerda · ganho à direita</div>'
            + linhas_graf + '</div>',
            unsafe_allow_html=True,
        )
    st.caption("Diferença entre o valor na cotação do faturamento e o valor convertido pela PTAX atual.")


_PAISES = {
    "USA": "Estados Unidos", "EUA": "Estados Unidos", "US": "Estados Unidos", "DEU": "Alemanha", "DE": "Alemanha",
    "GBR": "Reino Unido", "GB": "Reino Unido", "FRA": "França", "FR": "França", "ESP": "Espanha", "ES": "Espanha",
    "ITA": "Itália", "IT": "Itália", "NLD": "Holanda", "NL": "Holanda", "BEL": "Bélgica", "BE": "Bélgica",
    "PRT": "Portugal", "PT": "Portugal", "IRL": "Irlanda", "IE": "Irlanda", "CHN": "China", "CN": "China",
    "ARE": "Emirados Árabes", "SAU": "Arábia Saudita", "CAN": "Canadá", "MEX": "México", "ARG": "Argentina",
    "CHL": "Chile", "URY": "Uruguai", "PRY": "Paraguai", "JPN": "Japão", "KOR": "Coreia do Sul",
}


def _render_containers(df: pd.DataFrame) -> None:
    """Painel "Containers em aberto": total, ticker automático e containers por cliente e por país.
    Um container pode ter várias notas; conta-se cada container uma única vez."""
    if "CONTAINER" not in df.columns:
        return
    import html as _html

    esc = _html.escape
    tem = df["CONTAINER"].notna() & (df["CONTAINER"].astype(str).str.strip() != "")
    # NF Complementar ME (ação 262) normalmente não tem container: não conta como "sem container"
    if "CLASSIFICACAO" in df.columns:
        sem_container = int((~tem & (df["CLASSIFICACAO"].astype(str) != "NF Complementar ME")).sum())
    else:
        sem_container = int((~tem).sum())
    base = df[tem].copy()
    if base.empty:
        st.info("Nenhum container vinculado aos títulos em aberto.")
        return
    # a consulta traz, por nota, os containers separados por vírgula
    base["CONTAINER"] = base["CONTAINER"].astype(str).str.split(",")
    base = base.explode("CONTAINER")
    base["CONTAINER"] = base["CONTAINER"].str.strip()
    base = base[base["CONTAINER"] != ""]
    if "PAIS" in base.columns:
        base["_PAIS"] = base["PAIS"].astype(str).str.strip().str.upper().map(lambda p: _PAISES.get(p, p if p and p != "NAN" else "Sem país"))
    else:
        base["_PAIS"] = "Sem país"

    total = int(base["CONTAINER"].nunique())
    por_cliente = base.groupby("CLIENTE")["CONTAINER"].nunique().sort_values(ascending=False)
    por_pais = base.groupby("_PAIS")["CONTAINER"].nunique().sort_values(ascending=False)

    venc = base[base["SITUACAO"] == "VENCIDO"] if "SITUACAO" in base.columns else base.iloc[0:0]
    n_venc = int(venc["CONTAINER"].nunique())

    def _rotulo(n: int) -> str:
        return f"{n} container" + ("" if n == 1 else "s")

    itens = "".join(
        f'<span class="cnt-it"><b>{esc(str(c))}</b><span class="cnt-ch">{_rotulo(int(q))}</span></span>'
        for c, q in por_cliente.head(15).items()
    ) + "".join(
        f'<span class="cnt-it"><b>{esc(str(c))}</b><span class="cnt-chp">{_rotulo(int(q))}</span></span>'
        for c, q in por_pais.head(8).items()
    )
    # velocidade do ticker: cerca de 6 s por item, no mínimo 90 s por volta (quanto maior o número, mais lento)
    duracao_ticker = max(90, (min(len(por_cliente), 15) + min(len(por_pais), 8)) * 6)

    def _linhas(serie: pd.Series, cor: str) -> str:
        mx = int(serie.iloc[0]) or 1
        return "".join(
            f'<div class="cnt-r"><span class="cnt-l" title="{esc(str(n))}">{esc(str(n))}</span>'
            f'<div class="cnt-tt"><i class="an-wipe" style="width:{q / mx * 100:.1f}%;background:{cor}"></i></div>'
            f'<b>{int(q)}</b></div>'
            for n, q in serie.items()
        )

    avisos = ""
    if n_venc:
        avisos += f'<span class="cnt-venc">{n_venc} vencido{"" if n_venc == 1 else "s"}</span> '
    if sem_container:
        avisos += f'<span class="cnt-sem">{sem_container} título{"" if sem_container == 1 else "s"} sem container</span>'

    estilo = (
        "<style>"
        ".cnt-box{background:#1e1e2e;border-radius:10px;padding:14px 16px;margin-top:6px}"
        ".cnt-hd{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:10px}"
        ".cnt-t{font-size:13px;font-weight:500;color:#e0e0e0}.cnt-s{font-size:11px;color:#8892A4}"
        ".cnt-tk{overflow:hidden;white-space:nowrap;border:1px solid #2a2f40;border-radius:8px;background:#151a28;padding:7px 0;margin-bottom:12px}"
        ".cnt-tr{display:inline-block;animation:cnt-rola 40s linear infinite}.cnt-tk:hover .cnt-tr{animation-play-state:paused}"
        "@keyframes cnt-rola{from{transform:translateX(0)}to{transform:translateX(-50%)}}"
        ".cnt-it{display:inline-flex;align-items:center;gap:6px;margin-right:24px;font-size:12px;color:#c9d1e6}.cnt-it b{color:#fff;font-weight:500}"
        ".cnt-ch{background:#1f2a40;color:#9db8e8;border-radius:8px;padding:1px 7px;font-size:10px}"
        ".cnt-chp{background:#2a2540;color:#b9aee0;border-radius:8px;padding:1px 7px;font-size:10px}"
        ".cnt-venc{background:rgba(226,75,74,0.14);color:#f28b8a;border-radius:8px;padding:1px 7px;font-size:10px;font-weight:500}"
        ".cnt-sem{background:rgba(232,163,23,0.14);color:#f0b35a;border-radius:8px;padding:1px 7px;font-size:10px;font-weight:500}"
        ".cnt-grid{display:grid;grid-template-columns:minmax(150px,0.7fr) 1.2fr 1fr;gap:18px}"
        ".cnt-big{font-size:40px;font-weight:600;color:#fff;line-height:1}.cnt-lb{font-size:12px;color:#8892A4;margin:4px 0 10px}"
        ".cnt-sub{font-size:11px;color:#8892A4;margin-bottom:4px}"
        ".cnt-sc{max-height:150px;overflow-y:auto;padding-right:8px;scrollbar-width:thin;scrollbar-color:#3a4258 transparent}"
        ".cnt-sc::-webkit-scrollbar{width:6px}.cnt-sc::-webkit-scrollbar-thumb{background:#3a4258;border-radius:3px}"
        ".cnt-r{display:grid;grid-template-columns:minmax(90px,150px) 1fr 28px;align-items:center;gap:8px;margin:7px 0;font-size:12px}"
        ".cnt-l{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#c9d1e6}"
        ".cnt-tt{height:10px;border-radius:5px;background:#262b3b;overflow:hidden}.cnt-tt i{display:block;height:100%;border-radius:5px}"
        ".cnt-r b{text-align:right;font-weight:500;color:#e0e0e0}"
        "</style>"
    )
    st.markdown(
        estilo
        + f'<div class="cnt-box"><div class="cnt-hd"><span class="cnt-t">Containers em aberto</span>'
        f'<span class="cnt-s">{_rotulo(total)} · {len(por_cliente)} cliente{"" if len(por_cliente) == 1 else "s"} · '
        f'{len(por_pais)} {"país" if len(por_pais) == 1 else "países"}</span></div>'
        f'<div class="cnt-tk"><div class="cnt-tr" style="animation-duration:{duracao_ticker}s">{itens}{itens}</div></div>'
        f'<div class="cnt-grid"><div><div class="cnt-big">{total}</div>'
        f'<div class="cnt-lb">Total de containers em aberto</div>{avisos}</div>'
        f'<div><div class="cnt-sub">Por cliente</div><div class="cnt-sc">{_linhas(por_cliente, "#4A7FB5")}</div></div>'
        f'<div><div class="cnt-sub">Por país</div><div class="cnt-sc">{_linhas(por_pais, "#7B68B5")}</div></div></div></div>',
        unsafe_allow_html=True,
    )


def _num(valor) -> str:
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "0,00"


def _cot(valor) -> str:
    """Cotação sempre com 4 casas decimais (ex.: 5,6666)."""
    try:
        return f"{float(valor):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _para_excel(df_x: pd.DataFrame, colunas_data=("VENCIMENTO", "PRORROGADO")) -> pd.DataFrame:
    """Datas como dd/mm/aaaa (sem hora) e dias como número inteiro, para o Excel."""
    df_x = df_x.copy()
    for c in colunas_data:
        if c in df_x.columns:
            df_x[c] = pd.to_datetime(df_x[c], errors="coerce").dt.strftime("%d/%m/%Y")
    if "DIAS" in df_x.columns:
        df_x["DIAS"] = pd.to_numeric(df_x["DIAS"], errors="coerce").round().astype("Int64")
    return df_x


def _moeda(valor, sigla: str) -> str:
    return f"{_SIMBOLOS.get(sigla, sigla)} {_num(valor)}"


def _reais(valor) -> str:
    return f"R$ {_num(valor)}"


def render(df_cr: pd.DataFrame, mostrar_titulo: bool = True) -> None:
    # Botão /do painel de Contas a Receber: esconde os valores em reais e nas moedas.
    ocultar = st.session_state.get("cr_ocultar", False)

    def _mascarar(fn):
        return lambda *a: "••••••" if ocultar else fn(*a)

    _m_moeda, _m_reais, _m_num = _mascarar(_moeda), _mascarar(_reais), _mascarar(_num)

    if mostrar_titulo:
        _col_t, _col_at = st.columns([8, 1])
        with _col_t:
            st.title("Contas a Receber - Mercado Externo")
        with _col_at:
            st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
            if st.button("🔄 Atualizar", key="cr_me_atualizar", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

    if df_cr.empty or "MERCADO" not in df_cr.columns:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return

    df = df_cr[df_cr["MERCADO"] == "ME"].copy()
    for col in ("SALDO_EM_ABERTO", "SALDO_MOEDA", "COTACAO"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["SALDO_EM_ABERTO"].fillna(0) > 0]

    if df.empty:
        st.info("Nenhum título em aberto no mercado externo.")
        return

    df["MOEDA"] = df["MOEDA"].fillna("SEM MOEDA")
    # Títulos já em reais (R$) não têm cartão nem opção própria, mas entram nos totais de "Todas".
    moedas = [m for m in sorted(df["MOEDA"].unique()) if m != "R$"]
    escolha = st.radio("Moeda:", ["Todas"] + moedas, horizontal=True, key="cre_moeda")
    if escolha != "Todas":
        df = df[df["MOEDA"] == escolha]

    # ── Cards ────────────────────────────────────────────────────────────────
    if escolha == "Todas":
        cards = []
        for m in moedas:
            d = df[df["MOEDA"] == m]
            cards.append(card_html(
                f"Saldo em {_NOMES.get(m, m)}",
                _m_reais(d["SALDO_EM_ABERTO"].sum()),
                _m_moeda(d["SALDO_MOEDA"].sum(), m),
                cor_borda="#4A7FB5",
                tamanho_valor="20px",
            ))
        cards.append(card_html("Total em reais", _m_reais(df["SALDO_EM_ABERTO"].sum()),
                               "Com base na Cotação do Faturamento", cor_borda="#6366f1"))
    else:
        venc = df[df["SITUACAO"] == "VENCIDO"]
        avenc = df[df["SITUACAO"] == "A VENCER"]
        saldo_m = df["SALDO_MOEDA"].sum()
        cot_media = df["SALDO_EM_ABERTO"].sum() / saldo_m if saldo_m else 0
        cards = [
            card_html(f"Saldo em {_NOMES.get(escolha, escolha)}",
                      _m_reais(df["SALDO_EM_ABERTO"].sum()),
                      _m_moeda(saldo_m, escolha),
                      cor_borda="#4A7FB5", tamanho_valor="20px"),
            card_html("Vencido",
                      _m_reais(venc["SALDO_EM_ABERTO"].sum()),
                      _m_moeda(venc["SALDO_MOEDA"].sum(), escolha),
                      cor_borda="#E24B4A", tamanho_valor="20px"),
            card_html("A vencer",
                      _m_reais(avenc["SALDO_EM_ABERTO"].sum()),
                      _m_moeda(avenc["SALDO_MOEDA"].sum(), escolha),
                      cor_borda="#22c55e", tamanho_valor="20px"),
            card_html("Cotação média", _cot(cot_media), f"{escolha} → R$", cor_borda="#6366f1"),
        ]
    if escolha == "Todas":
        cards_img = [
            {"label": f"Saldo em {_NOMES.get(m, m)}",
             "valor": f"{_SIMBOLOS.get(m, m)} {_m_num(df.loc[df['MOEDA'] == m, 'SALDO_MOEDA'].sum())}",
             "cor": (74, 127, 181)}
            for m in moedas
        ] + [{"label": "Total em reais", "valor": _m_reais(df["SALDO_EM_ABERTO"].sum()), "cor": (99, 102, 241)}]
    else:
        cards_img = [
            {"label": f"Saldo em {_NOMES.get(escolha, escolha)}", "valor": _m_moeda(saldo_m, escolha), "cor": (74, 127, 181)},
            {"label": "Vencido", "valor": _m_moeda(venc["SALDO_MOEDA"].sum(), escolha), "cor": (226, 75, 74)},
            {"label": "A vencer", "valor": _m_moeda(avenc["SALDO_MOEDA"].sum(), escolha), "cor": (34, 197, 94)},
            {"label": "Cotação média", "valor": _cot(cot_media), "cor": (99, 102, 241)},
        ]
    if escolha != "Todas":   # em "Todas", o bloco PTAX abaixo mostra um cartão por moeda e o total
        render_cards_row(cards)
        st.caption("Valores em reais com base na Cotação do Faturamento.")

    # ── taxas PTAX para colunas nas tabelas ───────────────────────────────────
    _ptax_info = buscar_ptax()
    _ptax_data_ref = _ptax_info["data_ref"].strftime("%d/%m/%Y")
    _col_taxa    = f"PTAX {_ptax_data_ref}"
    _col_valor   = "Valor Atualizado (R$)"
    _col_var_r   = "Variação (R$)"
    _col_var_pct = "Variação %"
    _col_sit     = "Variação Cambial"

    def _adicionar_ptax(df_x: pd.DataFrame) -> pd.DataFrame:
        df_x = df_x.copy()
        df_x[_col_taxa] = df_x["MOEDA"].apply(
            lambda m: _ptax_info[m]["venda"] if _ptax_info.get(m) else None)
        df_x[_col_valor] = df_x.apply(
            lambda r: (float(r["SALDO_MOEDA"]) * float(r[_col_taxa]))
            if pd.notna(r.get("SALDO_MOEDA")) and pd.notna(r.get(_col_taxa)) else None,
            axis=1,
        )
        # Mantém o sinal real: Excel usa-o para coloração condicional.
        # O formato numérico "#,##0.00;#,##0.00" esconde o "-" na exibição.
        df_x[_col_var_r] = df_x.apply(
            lambda r: (r[_col_valor] - float(r["SALDO_EM_ABERTO"]))
            if pd.notna(r.get(_col_valor)) and pd.notna(r.get("SALDO_EM_ABERTO")) else None,
            axis=1,
        )
        df_x[_col_var_pct] = df_x.apply(
            lambda r: (r[_col_var_r] / float(r["SALDO_EM_ABERTO"]) * 100)
            if pd.notna(r.get(_col_var_r)) and float(r.get("SALDO_EM_ABERTO") or 0) != 0 else None,
            axis=1,
        )
        df_x[_col_sit] = df_x[_col_var_r].apply(
            lambda v: "▲ Positiva" if pd.notna(v) and v >= 0 else ("▼ Negativa" if pd.notna(v) else None))
        return df_x

    _render_ptax_bloco(df, moeda_filtro=escolha)

    _render_containers(df)

    st.divider()

    valor_col = "SALDO_EM_ABERTO" if escolha == "Todas" else "SALDO_MOEDA"
    unidade = "R$" if escolha == "Todas" else _SIMBOLOS.get(escolha, escolha)

    # ── Pré-computa aging (também usado na exportação de imagem) ─────────────
    ag = pd.DataFrame()
    total_ag = 1
    resumo = ""
    venc_v = avenc_v = 0.0
    if "FAIXA_DIAS" in df.columns:
        ag = df.dropna(subset=["FAIXA_DIAS"]).groupby("FAIXA_DIAS", as_index=False)[valor_col].sum()
        ag["ordem"] = ag["FAIXA_DIAS"].apply(
            lambda f: _ORDEM_FAIXAS.index(f) if f in _ORDEM_FAIXAS else 99)
        ag = ag.sort_values("ordem").reset_index(drop=True)
        total_ag = ag[valor_col].sum() or 1
        ag["grupo"] = ag["FAIXA_DIAS"].apply(
            lambda f: "Vencido" if str(f).startswith("Vencido") else "A vencer")
        venc_v  = ag.loc[ag["grupo"] == "Vencido",  valor_col].sum()
        avenc_v = ag.loc[ag["grupo"] == "A vencer", valor_col].sum()
        resumo = (
            f"Vencido: {unidade} {_m_num(venc_v)} ({_m_num(venc_v / total_ag * 100)}%)  ·  "
            f"A vencer: {unidade} {_m_num(avenc_v)} ({_m_num(avenc_v / total_ag * 100)}%)"
        )

    rank = (df.groupby("CLIENTE", as_index=False)[valor_col].sum()
            .sort_values(valor_col, ascending=False).head(8))

    col_aging, col_rank = st.columns(2)

    with col_aging:
        st.markdown(f"#### Aging{' (em reais)' if escolha == 'Todas' else f' (em {escolha})'}")
        _barras_aging(ag, valor_col, unidade, ocultar)

    with col_rank:
        _barras_ranking(rank, valor_col, df[valor_col].sum(), unidade, "#4A7FB5", ocultar,
                        titulo=f"Ranking de clientes{' (em reais)' if escolha == 'Todas' else f' (em {escolha})'}")


    st.divider()

    aba_resumo, aba_titulos = st.tabs(["Resumo", "Títulos em Aberto"])

    with aba_resumo:
        # ── Títulos vencidos e vencido por cliente (igual ao Contas a Receber Interno) ──
        df_venc_t = df[df["SITUACAO"] == "VENCIDO"].copy() if "SITUACAO" in df.columns else df.iloc[0:0]
        col_tv, col_vc = st.columns(2)

        with col_tv:
            st.subheader("Títulos Vencidos")
            if df_venc_t.empty:
                st.success("Nenhum título vencido.")
            else:
                df_venc_t["DIAS"] = pd.to_numeric(df_venc_t["DIAS"], errors="coerce")
                df_venc_t = df_venc_t.sort_values("DIAS")
                df_venc_t = _adicionar_ptax(df_venc_t)

                def _badge(cor, bg, texto):
                    return (f'<span style="color:{cor};background:{bg};'
                            f'border-radius:4px;padding:1px 6px;font-size:12px;font-weight:500">'
                            f'{texto}</span>')

                def _cores_sit(sit):
                    pos = sit == "▲ Positiva" if sit else False
                    return ("#4caf7a", "rgba(76,175,122,0.12)") if pos else ("#E24B4A", "rgba(226,75,74,0.12)")

                def _fmt_var_r(row):
                    v, sit = row[_col_var_r], row[_col_sit]
                    if pd.isna(v): return "—"
                    cor, bg = _cores_sit(sit)
                    seta = "▲" if sit == "▲ Positiva" else "▼"
                    return _badge(cor, bg, f"{seta} R$ {'••••••' if ocultar else _num(abs(v))}")

                def _fmt_var_pct(row):
                    v, sit = row[_col_var_pct], row[_col_sit]
                    if pd.isna(v): return "—"
                    cor, bg = _cores_sit(sit)
                    seta = "▲" if sit == "▲ Positiva" else "▼"
                    return _badge(cor, bg, f"{seta} {'••' if ocultar else f'{abs(v):.2f}%'}")

                def _fmt_sit(v):
                    if not v: return "—"
                    cor, bg = _cores_sit(v)
                    return _badge(cor, bg, v)

                tv = pd.DataFrame({
                    "Cliente": df_venc_t["CLIENTE"],
                    "País": (df_venc_t["PAIS"].fillna("—") if "PAIS" in df_venc_t.columns else "—"),
                    "NF": df_venc_t["NF"],
                    "Entrada": (pd.to_datetime(df_venc_t["ENTRADA"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("—")
                                if "ENTRADA" in df_venc_t.columns else "—"),
                    "Container": (df_venc_t["CONTAINER"].fillna("—") if "CONTAINER" in df_venc_t.columns else "—"),
                    "Moeda": df_venc_t["MOEDA"],
                    "Saldo em Aberto (Moeda)": df_venc_t["SALDO_MOEDA"].apply(
                        lambda v: _m_num(v) if pd.notna(v) else ""),
                    "Saldo em Aberto (R$)": df_venc_t["SALDO_EM_ABERTO"].apply(_m_reais),
                    _col_taxa: df_venc_t[_col_taxa].apply(
                        lambda v: _cot(v) if pd.notna(v) else "—"),
                    _col_valor: df_venc_t[_col_valor].apply(
                        lambda v: _m_reais(v) if pd.notna(v) else "—"),
                    _col_var_r:   df_venc_t[[_col_var_r, _col_sit]].apply(_fmt_var_r, axis=1),
                    _col_var_pct: df_venc_t[[_col_var_pct, _col_sit]].apply(_fmt_var_pct, axis=1),
                    _col_sit:     df_venc_t[_col_sit].apply(_fmt_sit),
                    "Atraso": df_venc_t["DIAS"].apply(
                        lambda v: f"{abs(int(v))} dias" if pd.notna(v) else ""),
                    "Complemento": df_venc_t["COMPLEMENTO"].fillna("-") if "COMPLEMENTO" in df_venc_t.columns else "-",
                })
                render_tabela_html(
                    tv,
                    coluna_dias="Atraso",
                    coluna_complemento="Complemento",
                    colunas_moeda=["Saldo em Aberto (R$)", _col_valor],
                )

        with col_vc:
            if not df_venc_t.empty:
                vc = (df_venc_t.groupby("CLIENTE", as_index=False)[valor_col].sum()
                      .sort_values(valor_col, ascending=False).head(8))
                _barras_ranking(vc, valor_col, df_venc_t[valor_col].sum(),
                                unidade, "#E24B4A", ocultar, titulo="Vencido por Cliente")

        if not df_venc_t.empty:
            cols_export = {
                "Cliente": df_venc_t["CLIENTE"],
                "País": df_venc_t["PAIS"] if "PAIS" in df_venc_t.columns else None,
                "NF": df_venc_t["NF"],
                "Entrada": df_venc_t["ENTRADA"] if "ENTRADA" in df_venc_t.columns else None,
                "Container": df_venc_t["CONTAINER"] if "CONTAINER" in df_venc_t.columns else None,
                "Vencimento": df_venc_t["VENCIMENTO"],
                "Prorrogado": df_venc_t["PRORROGADO"] if "PRORROGADO" in df_venc_t.columns else None,
                "Situação": df_venc_t["SITUACAO"],
                "Dias Vencto.": df_venc_t["DIAS"],
                "Moeda": df_venc_t["MOEDA"],
                "Cotação": df_venc_t["COTACAO"],
                "Saldo em Aberto (Moeda)": df_venc_t["SALDO_MOEDA"],
                "Saldo em Aberto (R$)": df_venc_t["SALDO_EM_ABERTO"],
                _col_taxa:    df_venc_t[_col_taxa],
                _col_valor:   df_venc_t[_col_valor],
                _col_var_r:   df_venc_t[_col_var_r],
                _col_var_pct: df_venc_t[_col_var_pct],
                _col_sit:     df_venc_t[_col_sit],
                "Complemento": (df_venc_t["COMPLEMENTO"].fillna("-").replace("", "-")
                                if "COMPLEMENTO" in df_venc_t.columns else "-"),
            }
            df_excel_v = pd.DataFrame(cols_export)
            for c in ("Entrada", "Vencimento", "Prorrogado"):
                df_excel_v[c] = pd.to_datetime(df_excel_v[c], errors="coerce").dt.strftime("%d/%m/%Y")
            df_excel_v["Dias Vencto."] = pd.to_numeric(df_excel_v["Dias Vencto."], errors="coerce").round().astype("Int64")
            _arquivo_excel_v = exportar_excel(
                df_excel_v, "TITULOS_VENCIDOS_EXTERNO",
                colunas_situacao_sem_fundo=("Situação Vencto.",),
                colunas_percentual=(_col_var_pct,),
                colunas_verde_vermelho=(_col_var_r, _col_var_pct, _col_sit, "Dias Vencto."),
                colunas_valor_abs=(_col_var_r, _col_var_pct),
            )
            # aba PTAX: mês anterior e mês vigente, uma linha por dia útil, com compra/venda/variação das moedas
            try:
                _linhas_ptax = buscar_ptax_mes_anterior_e_vigente()
                _desde_ptax = (pd.Timestamp.today().normalize().replace(day=1) - pd.Timedelta(days=1)).replace(day=1).date()
                _arquivo_excel_v = adicionar_aba_ptax(_arquivo_excel_v, _linhas_ptax, _desde_ptax)
            except Exception:
                st.warning("Cotações PTAX indisponíveis no momento: a aba PTAX não foi incluída na planilha.")
            ranking_img = [
                (r["CLIENTE"], float(r[valor_col]), f"{unidade} {_m_num(r[valor_col])}")
                for _, r in rank.iloc[::-1].iterrows()
            ]
            aging_img = []
            if "FAIXA_DIAS" in df.columns and not ag.empty:
                for _, r in ag.iterrows():
                    aging_img.append({
                        "label": r["FAIXA_DIAS"], "valor": float(r[valor_col]),
                        "texto": f"{unidade} {_m_num(r[valor_col])}",
                        "pct": f"{_m_num(r[valor_col] / total_ag * 100)}%",
                        "cor": (226, 75, 74) if r["grupo"] == "Vencido" else (34, 197, 94),
                    })
            # cotações PTAX entram na imagem como cards extras (mesma data do painel)
            _moedas_img = ("EUR", "GBP", "USD") if escolha == "Todas" else (escolha,)
            cards_ptax_img = [
                {"label": f"{m}/BRL (PTAX)",
                 "valor": f"R$ {_cot(_ptax_info[m]['venda'])}",
                 "cor": tuple(int(_CORES_PTAX[m][i:i + 2], 16) for i in (1, 3, 5))}
                for m in _moedas_img if _ptax_info.get(m)
            ]
            # saldos convertidos pela PTAX de venda do dia, como no painel
            saldos_ptax_img = []
            for m in _moedas_img:
                if _ptax_info.get(m):
                    saldo_m = float(df.loc[df["MOEDA"] == m, "SALDO_MOEDA"].sum())
                    saldos_ptax_img.append({
                        "label": f"Saldo em {_NOMES.get(m, m)} (PTAX)",
                        "valor": f"R$ {_num(saldo_m * float(_ptax_info[m]['venda']))}",
                        "cor": tuple(int(_CORES_PTAX[m][i:i + 2], 16) for i in (1, 3, 5)),
                    })
            if len(saldos_ptax_img) > 1:
                total_ptax_img = sum(
                    float(df.loc[df["MOEDA"] == m, "SALDO_MOEDA"].sum()) * float(_ptax_info[m]["venda"])
                    for m in _moedas_img if _ptax_info.get(m)
                )
                saldos_ptax_img.append({"label": "Total em Reais (PTAX)", "valor": f"R$ {_num(total_ptax_img)}", "cor": (99, 102, 241)})
            # cards de cotação com sparkline, como na tela
            _hist_img = {m: list(reversed(buscar_historico_ptax(m, 30))) for m in _moedas_img}
            cotacoes_img = []
            for m in _moedas_img:
                if not _ptax_info.get(m):
                    continue
                v = _ptax_info[m]
                serie = [h["venda"] for h in _hist_img[m]]
                var = v.get("var_venda")
                var_txt = (f"{'▲' if var >= 0 else '▼'} {abs(var):.2f}%".replace(".", ",")
                           if var is not None else "")
                cotacoes_img.append({
                    "label": f"{m}/BRL",
                    "valor": f"R$ {_cot(v['venda'])}",
                    "subtitulo": f"compra: R$ {_cot(v['compra'])}  {var_txt}",
                    "cor": tuple(int(_CORES_PTAX[m][i:i + 2], 16) for i in (1, 3, 5)),
                    "serie": serie,
                    "maxima": _cot(max(serie)) if serie else "",
                    "minima": _cot(min(serie)) if serie else "",
                })
            # impacto cambial, mesma tabela da tela
            impacto_linhas = []
            saldo_fat_tot = saldo_brl_tot = 0.0
            for m in _moedas_img:
                if not _ptax_info.get(m):
                    continue
                s_m = float(df.loc[df["MOEDA"] == m, "SALDO_MOEDA"].sum())
                s_fat = float(df.loc[df["MOEDA"] == m, "SALDO_EM_ABERTO"].sum())
                s_brl = s_m * float(_ptax_info[m]["venda"])
                saldo_fat_tot += s_fat
                saldo_brl_tot += s_brl
                dif = s_brl - s_fat
                pct = dif / s_fat * 100 if s_fat else 0
                seta = "▲" if dif >= 0 else "▼"
                impacto_linhas.append([
                    m, f"{_SIMBOLOS.get(m, m)} {_m_num(s_m)}", f"R$ {_m_num(s_fat)}", _cot(_ptax_info[m]["venda"]),
                    f"R$ {_m_num(s_brl)}", f"{seta} R$ {_m_num(abs(dif))}", f"{seta} {abs(pct):.2f}%".replace(".", ","),
                ])
            impacto_img = None
            if impacto_linhas:
                dif_tot = saldo_brl_tot - saldo_fat_tot
                pct_tot = dif_tot / saldo_fat_tot * 100 if saldo_fat_tot else 0
                seta_t = "▲" if dif_tot >= 0 else "▼"
                if len(impacto_linhas) > 1:
                    impacto_linhas.append([
                        "Total", "", f"R$ {_m_num(saldo_fat_tot)}", "", f"R$ {_m_num(saldo_brl_tot)}",
                        f"{seta_t} R$ {_m_num(abs(dif_tot))}", f"{seta_t} {abs(pct_tot):.2f}%".replace(".", ","),
                    ])
                impacto_img = {
                    "titulo": f"Impacto cambial — faturamento vs PTAX {_ptax_data_ref}",
                    "cabecalho": ["Moeda", "Valor Moeda", "Valor Faturamento", f"PTAX {_ptax_data_ref}",
                                  "Valor Atualizado", "Diferença cambial", "Valorização %"],
                    "linhas": impacto_linhas,
                }
            imagem_png = gerar_imagem_painel_externo(
                titulo_principal="Contas a Receber - Mercado Externo"
                                 + ("" if escolha == "Todas" else f" — {_NOMES.get(escolha, escolha)}"),
                cards_resumo=cards_img + saldos_ptax_img,
                cotacoes=cotacoes_img,
                impacto=impacto_img,
                total_ranking=float(df["SALDO_EM_ABERTO"].sum()),
                total_aging_texto=f"Total: {unidade} {_m_num(total_ag)}" if aging_img else "",
                ranking=ranking_img,
                titulo_ranking="Ranking de clientes" + (" (em reais)" if escolha == "Todas" else f" (em {escolha})"),
                aging=aging_img,
                titulo_aging="Aging" + (" (em reais)" if escolha == "Todas" else f" (em {escolha})"),
                resumo_aging=resumo.replace("", "").replace("", "").strip() if aging_img else "",
            )
            botoes_acao_row(
                excel={"data": _arquivo_excel_v, "file_name": "Contas_a_Receber_Externo_Vencidos.xlsx", "key": "cre_export_excel"},
                imagem={"data": imagem_png, "file_name": "Contas_a_Receber_Externo_Vencidos.png", "key": "cre_export_imagem"},
                copiar={"data": imagem_png, "key": "cre_copiar"},
            )


    with aba_titulos:
        # ── Títulos ───────────────────────────────────────────────────────────────
        st.subheader("Títulos em aberto")
        notas = df["NF"].nunique() if "NF" in df.columns else 0
        st.caption(f"{len(df)} parcela(s) (linhas) em {notas} nota(s) fiscal(is)")
        colunas = {
            "NF": "NF", "CONTAINER": "Container", "PARCELA": "Parcela", "CLIENTE": "Cliente", "PAIS": "País", "MOEDA": "Moeda",
            "ENTRADA": "Entrada", "VENCIMENTO": "Vencimento", "PRORROGADO": "Prorrogado",
            "DIAS_VENCIDO": "Dias Vencto.", "SITUACAO": "Situação Vencto.", "VLR_PARCELA_MOEDA": "Valor da parcela (moeda)",
            "COTACAO": "PTAX Faturamento", "SALDO_MOEDA": "Saldo em Aberto (Moeda)", "SALDO_EM_ABERTO": "Saldo em Aberto (R$)",
        }
        situacao_sel = st.radio(
            "Filtrar por situação:", ["Todos", "A VENCER", "VENCIDO"],
            horizontal=True, key="cre_situacao",
        )
        df_lista = df if situacao_sel == "Todos" else df[df["SITUACAO"] == situacao_sel]
        df_lista = calcular_dias_prazo(df_lista)
        cols = [c for c in colunas if c in df_lista.columns]
        df_tab_base = df_lista[cols].sort_values(["PRORROGADO", "NF"] if "PRORROGADO" in cols else cols[:1])

        # adiciona colunas PTAX
        df_tab = _adicionar_ptax(df_tab_base)

        df_exib = df_tab.copy()
        if "DIAS_VENCIDO" in df_exib.columns and "SITUACAO" in df_exib.columns:
            df_exib["DIAS_VENCIDO"] = df_exib.apply(formatar_dias_unificado_html, axis=1)
        for c in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
            if c in df_exib.columns:
                df_exib[c] = pd.to_datetime(df_exib[c], errors="coerce").dt.strftime("%d/%m/%Y")
        if "CONTAINER" in df_exib.columns:
            df_exib["CONTAINER"] = df_exib["CONTAINER"].apply(lambda v: str(v) if pd.notna(v) and str(v).strip() else "—")
        if "PAIS" in df_exib.columns:
            df_exib["PAIS"] = df_exib["PAIS"].apply(lambda v: str(v) if pd.notna(v) and str(v).strip() else "—")
        if "COTACAO" in df_exib.columns:
            df_exib["COTACAO"] = df_exib["COTACAO"].apply(lambda v: _cot(v) if pd.notna(v) else "")
        for c in ("VLR_PARCELA_MOEDA", "SALDO_MOEDA", "SALDO_EM_ABERTO"):
            if c in df_exib.columns:
                df_exib[c] = df_exib[c].apply(lambda v: _m_num(v) if pd.notna(v) else "")
        df_exib[_col_taxa]  = df_exib[_col_taxa].apply(lambda v: _cot(v) if pd.notna(v) else "—")
        df_exib[_col_valor] = df_exib[_col_valor].apply(lambda v: _m_reais(v) if pd.notna(v) else "—")

        def _badge2(cor, bg, texto):
            return (f'<span style="color:{cor};background:{bg};'
                    f'border-radius:4px;padding:1px 6px;font-size:12px;font-weight:500">'
                    f'{texto}</span>')

        def _cores2(sit):
            pos = sit == "▲ Positiva" if sit else False
            return ("#4caf7a", "rgba(76,175,122,0.12)") if pos else ("#E24B4A", "rgba(226,75,74,0.12)")

        def _fmt_vr(row):
            v, sit = row[_col_var_r], row[_col_sit]
            if pd.isna(v): return "—"
            cor, bg = _cores2(sit)
            seta = "▲" if sit == "▲ Positiva" else "▼"
            return _badge2(cor, bg, f"{seta} R$ {_num(abs(v))}")

        def _fmt_vpct(row):
            v, sit = row[_col_var_pct], row[_col_sit]
            if pd.isna(v): return "—"
            cor, bg = _cores2(sit)
            seta = "▲" if sit == "▲ Positiva" else "▼"
            return _badge2(cor, bg, f"{seta} {abs(v):.2f}%")

        def _fmt_vsit(v):
            if not v: return "—"
            cor, bg = _cores2(v)
            return _badge2(cor, bg, v)

        df_exib[_col_var_r]   = df_exib[[_col_var_r, _col_sit]].apply(_fmt_vr, axis=1)
        df_exib[_col_var_pct] = df_exib[[_col_var_pct, _col_sit]].apply(_fmt_vpct, axis=1)
        df_exib[_col_sit]     = df_exib[_col_sit].apply(_fmt_vsit)

        colunas_exib = {**colunas,
                        _col_taxa: _col_taxa, _col_valor: _col_valor,
                        _col_var_r: _col_var_r, _col_var_pct: _col_var_pct, _col_sit: _col_sit}

        render_tabela_html(
            df_exib,
            colunas_renomear=colunas_exib,
            colunas_moeda=["VLR_PARCELA_MOEDA", "SALDO_MOEDA", "SALDO_EM_ABERTO", _col_valor],
            coluna_situacao="SITUACAO",
        )

        st.markdown("&nbsp;", unsafe_allow_html=True)

        # Excel: valores numéricos puros (sem badges/setas)
        df_excel_tab = _para_excel(df_tab, colunas_data=("ENTRADA", "VENCIMENTO", "PRORROGADO")).rename(
            columns={**colunas, _col_taxa: _col_taxa, _col_valor: _col_valor,
                     _col_var_r: _col_var_r, _col_var_pct: _col_var_pct, _col_sit: _col_sit})
        botao_exportar_excel(
            exportar_excel(
                df_excel_tab, "MERCADO_EXTERNO",
                colunas_situacao_sem_fundo=("Situação Vencto.",),
                colunas_percentual=(_col_var_pct,),
                colunas_verde_vermelho=(_col_var_r, _col_var_pct, _col_sit, "Dias Vencto."),
                colunas_valor_abs=(_col_var_r, _col_var_pct),
            ),
            "Contas a Receber - Mercado Externo.xlsx",
            key="cre_export",
        )
