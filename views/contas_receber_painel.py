"""
views/contas_receber_painel.py
================================
Painel único de Contas a Receber, com três abas: Visão Geral, Mercado Interno
e Mercado Externo. A Visão Geral mostra os dois mercados lado a lado (nunca
misturados): o interno em reais e o externo por moeda, com a soma em reais.
"""

from datetime import date, timedelta
from functools import partial

import json
import math

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from components.buttons import botao_exportar_excel, botoes_acao_row
from components.cards import card_html, render_cards_row
from services.data_service import carregar_total_faturado_cliente
from utils.imagem_email import gerar_imagem_visao_geral
from views import contas_receber, contas_receber_externo

_SIMBOLOS = {"USD": "US$", "EUR": "€", "GBP": "£"}
_NOMES = {"USD": "Dólar", "EUR": "Euro", "GBP": "Libra"}
_CORES_MOEDA = {"USD": "#F59E0B", "EUR": "#1CAE85", "GBP": "#8B7EC8"}
_CORES_EXTRAS = ["#D4537E", "#639922", "#993C1D"]
_COR_COMPL = "#BA7517"   # NF Complementar (títulos em reais dentro do mercado externo)
_COR_VENCIDO = "#E24B4A"
_COR_MI = "#1CAE85"
_COR_A_VENCER = "#16A34A"

_FUNDO = "rgba(128,128,128,0.08)"
_BORDA = "1px solid rgba(128,128,128,0.25)"
_TRILHO = "rgba(128,128,128,0.15)"
_TEXTO_SEC = "rgba(128,128,128,0.95)"


# ── Formatação ────────────────────────────────────────────────────────────────

def _oculto(ocultar: bool = None) -> bool:
    """None = segue o botão de ocultar valores do Contas a Receber; True/False força."""
    return st.session_state.get("cr_ocultar", False) if ocultar is None else ocultar


def _corta(valor: float, divisor: float, casas: int) -> float:
    """valor / divisor cortado (em direção ao zero) em `casas` decimais, sem arredondar para cima."""
    fator = 10 ** casas
    corte = math.floor(abs(valor) / divisor * fator + 1e-9) / fator
    return corte if valor >= 0 else -corte


def _abrev(valor: float, ocultar: bool = None) -> str:
    """Valor abreviado: 8,00 mi / 302 mil / — (zero). Respeita o botão de ocultar valores."""
    if _oculto(ocultar):
        return "••••••"
    if not valor:
        return "—"
    # cortado, nunca arredondado (2.587.431,20 vira 2,58 mi): mesma regra em todos os painéis
    if abs(valor) >= 1e6:
        return f"{_corta(valor, 1e6, 2):,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(valor) >= 1e3:
        return f"{_corta(valor, 1e3, 0):,.0f} mil".replace(",", ".")
    return f"{_corta(valor, 1, 0):,.0f}".replace(",", ".")


def _completo(valor: float, ocultar: bool = None) -> str:
    """Valor sem arredondar para mi/mil: 1.234.567,89 (— quando zero)."""
    if _oculto(ocultar):
        return "••••••"
    if not valor:
        return "—"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _rgb(cor_hex: str) -> tuple:
    h = cor_hex.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ── Faixas de vencimento ──────────────────────────────────────────────────────

def _faixas(hoje: date) -> list:
    """Faixas do aging: 2 faixas de vencidos, semana atual + 3 semanas ISO seguintes, A vencer 30+ e 60+.
    Cada faixa é (rótulo, dia_ini, dia_fim) em dias a partir de hoje (negativo = vencido); None = sem limite."""
    # Alinha com semanas ISO (seg-dom) para evitar rótulos duplicados.
    ate_domingo = (6 - hoje.weekday()) % 7
    faixas = [("Vencido 30+", None, -31), ("Vencido 1-30", -30, -1)]
    ini = 0
    fim = ate_domingo
    for i in range(4):
        semana = (hoje + timedelta(days=ini)).isocalendar()[1]
        rotulo = f"Semana {semana}" + (" (atual)" if i == 0 else "")
        faixas.append((rotulo, ini, fim))
        ini, fim = fim + 1, fim + 7
    faixas.append(("A vencer 30+", ini, 60))
    faixas.append(("A vencer 60+", 61, None))
    return faixas


def _na_faixa(dias: pd.Series, ini, fim) -> pd.Series:
    mask = pd.Series(True, index=dias.index)
    if ini is not None:
        mask &= dias >= ini
    if fim is not None:
        mask &= dias <= fim
    return mask


# ── Blocos visuais ────────────────────────────────────────────────────────────

def _linha(rotulo: str, segmentos: list, total: float, maximo: float, dica: str = "",
           ocultar: bool = None) -> str:
    """Uma linha do aging: rótulo, barra (segmentos = [(valor, cor)]) e total em reais."""
    barra = "".join(
        f'<div style="width:{v / maximo * 100:.2f}%;background:{c}"></div>'
        for v, c in segmentos if v > 0 and maximo
    )
    barra = f'<div class="an-wipe" style="display:flex;width:100%;height:100%">{barra}</div>'
    return (
        f'<div title="{dica}" style="display:grid;grid-template-columns:150px minmax(0,1fr) 132px;'
        f'gap:8px;align-items:center;font-size:14px;padding:2px 0">'
        f'<div>{rotulo}</div>'
        f'<div style="height:11px;border-radius:3px;display:flex;overflow:hidden;background:{_TRILHO}">{barra}</div>'
        f'<div style="text-align:right;font-weight:500">{_completo(total, ocultar)}</div></div>'
    )


def _bloco(nome: str, tag: str, cor_tag: str, cabecalho: str, corpo: str, total: float,
           ocultar: bool = None, abreviar: bool = False) -> str:
    return (
        f'<div style="background:{_FUNDO};border:{_BORDA};border-radius:12px;padding:12px 14px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'font-size:17px;font-weight:600;margin-bottom:8px"><span>{nome}</span>'
        f'<span style="font-size:12px;padding:2px 9px;border-radius:4px;font-weight:500;'
        f'background:{cor_tag}22;color:{cor_tag}">{tag}</span></div>'
        f'{cabecalho}{corpo}'
        f'<div style="display:flex;justify-content:space-between;font-size:15px;font-weight:600;'
        f'margin-top:8px;padding-top:7px;border-top:{_BORDA}"><span>Total em reais</span>'
        f'<span>R$ {(_abrev if abreviar else _completo)(total, ocultar)}</span></div></div>'
    )


def _legenda(itens: list) -> str:
    return (
        f'<div style="font-size:12px;color:{_TEXTO_SEC};margin:0 0 5px">'
        + "".join(
            f'<span style="margin-right:10px"><span style="display:inline-block;width:8px;height:8px;'
            f'border-radius:2px;background:{c};margin-right:3px"></span>{n}</span>'
            for n, c in itens
        )
        + "</div>"
    )


def _espaco() -> str:
    return '<div style="height:4px"></div>'


# ── Rankings MI / ME ─────────────────────────────────────────────────────────

_OPAC_RANK = ["1","1","1","0.70","0.55","0.45","0.38","0.32","0.28","0.24","0.21"]


def _ranking_col(df_mercado: pd.DataFrame, titulo: str, cor: str,
                 ocultar: bool = None) -> None:
    df_ab = df_mercado[df_mercado["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    if df_ab.empty or "CLIENTE" not in df_ab.columns:
        st.info("Sem dados.")
        return
    df_rank = (
        df_ab.groupby("CLIENTE")["SALDO_EM_ABERTO"]
        .sum().reset_index()
        .sort_values("SALDO_EM_ABERTO", ascending=False)
        .head(10)
    )
    total = df_ab["SALDO_EM_ABERTO"].sum() or 1
    maximo = df_rank["SALDO_EM_ABERTO"].max() or 1
    linhas = ""
    for i, (_, row) in enumerate(df_rank.iterrows()):
        pct  = row["SALDO_EM_ABERTO"] / total * 100
        barw = row["SALDO_EM_ABERTO"] / maximo * 100
        opac = _OPAC_RANK[i] if i < len(_OPAC_RANK) else "0.18"
        nome = row["CLIENTE"]
        if len(nome) > 28:
            nome = nome[:27] + "…"
        pct_txt = "••" if _oculto(ocultar) else f"{pct:.2f}%"
        val_txt = "••••••" if _oculto(ocultar) else _completo(row["SALDO_EM_ABERTO"])
        linhas += (
            f'<div style="display:grid;grid-template-columns:18px minmax(0,1fr) 38px minmax(0,1fr) 110px;'
            f'gap:6px;align-items:center;font-size:12px;padding:2px 0">'
            f'<span style="color:{_TEXTO_SEC};font-size:10px;font-weight:600;text-align:center">{i+1}</span>'
            f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{nome}</span>'
            f'<span style="color:{cor};font-size:10px;font-weight:600;text-align:right;white-space:nowrap">{pct_txt}</span>'
            f'<div style="height:10px;border-radius:3px;background:{_TRILHO};overflow:hidden">'
            f'<div style="width:{barw:.1f}%;height:100%;background:{cor};opacity:{opac}"></div></div>'
            f'<span style="font-size:11px;text-align:right;white-space:nowrap">{val_txt}</span>'
            f'</div>'
        )
    st.markdown(
        f'<div style="background:{_FUNDO};border:{_BORDA};border-radius:12px;padding:12px 14px">'
        f'<div style="font-size:14px;font-weight:500;margin-bottom:4px">{titulo}</div>'
        f'<div style="font-size:11px;color:{_TEXTO_SEC};margin-bottom:6px">% sobre saldo em aberto · em reais</div>'
        + linhas
        + f'</div>',
        unsafe_allow_html=True,
    )


# ── Gráfico faturamento por ano ───────────────────────────────────────────────

def _grafico_faturamento_ano() -> None:
    df_fat = carregar_total_faturado_cliente()
    if df_fat.empty or "ANO" not in df_fat.columns or "MERCADO" not in df_fat.columns:
        return

    df_fat["VALOR_TOTAL_FATURADO"] = pd.to_numeric(df_fat["VALOR_TOTAL_FATURADO"], errors="coerce").fillna(0)
    df_fat["ANO"] = pd.to_numeric(df_fat["ANO"], errors="coerce")
    df_fat = df_fat.dropna(subset=["ANO"])
    df_fat["ANO"] = df_fat["ANO"].astype(int)

    mi = df_fat[df_fat["MERCADO"] == "MI"].groupby("ANO")["VALOR_TOTAL_FATURADO"].sum().sort_index()
    me = df_fat[df_fat["MERCADO"] == "ME"].groupby("ANO")["VALOR_TOTAL_FATURADO"].sum().sort_index()

    anos = sorted(set(mi.index) | set(me.index))
    if not anos:
        return

    ocultar = _oculto()

    mi_vals = [float(mi.get(a, 0)) for a in anos]
    me_vals = [float(me.get(a, 0)) for a in anos]

    anos_js  = json.dumps([str(a) for a in anos])
    mi_js    = json.dumps(mi_vals)
    me_js    = json.dumps(me_vals)
    ocultar_js = json.dumps(ocultar)

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#e0e0e0;padding:0}}
.leg{{display:flex;gap:16px;margin-bottom:8px;font-size:12px;color:rgba(200,200,200,0.8)}}
.ld{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:3px;vertical-align:middle}}
</style>
</head><body>
<div style="background:{_FUNDO};border:{_BORDA};border-radius:12px;padding:12px 14px;width:100%">
  <div style="font-size:15px;font-weight:600;margin-bottom:2px">Faturamento por ano</div>
  <div style="font-size:12px;color:rgba(180,180,180,0.7);margin-bottom:10px">Total faturado em R$ · data de emissão da NF</div>
  <div class="leg">
    <span><span class="ld" style="background:#1CAE85"></span>Mercado Interno</span>
    <span><span class="ld" style="background:#E8724A"></span>Mercado Externo</span>
  </div>
  <div style="position:relative;width:100%;height:280px">
    <canvas id="ch" role="img" aria-label="Faturamento anual MI e ME"></canvas>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const anos    = {anos_js};
const miVals  = {mi_js};
const meVals  = {me_js};
const ocultar = {ocultar_js};
const green   = '#1CAE85', purple = '#E8724A';

function fmt(v) {{
  if (ocultar) return '••••';
  if (!v || v < 0.1) return null;
  if (v >= 1e9) return (Math.floor(v/1e7+1e-9)/100).toFixed(2).replace('.',',')+'B';
  if (v >= 1e6) return (Math.floor(v/1e5+1e-9)/10).toFixed(1).replace('.',',')+'M';
  if (v >= 1e3) return Math.floor(v/1e3+1e-9).toFixed(0)+'K';
  return Math.floor(v).toFixed(0);
}}

const labelPlugin = {{
  id: 'dotLabel',
  afterDatasetsDraw(chart) {{
    const ctx = chart.ctx;
    chart.data.datasets.forEach((ds, di) => {{
      chart.getDatasetMeta(di).data.forEach((pt, i) => {{
        const v   = ds.data[i];
        const lbl = fmt(v);
        if (!lbl) return;
        const x = pt.x, y = pt.y;
        const above = di === 1;
        ctx.save();
        ctx.font = '700 9.5px -apple-system,sans-serif';
        ctx.fillStyle = ds.borderColor;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(lbl, x, above ? y - 12 : y + 18);
        ctx.restore();
      }});
    }});
  }}
}};

new Chart(document.getElementById('ch'), {{
  type: 'line',
  plugins: [labelPlugin],
  data: {{
    labels: anos,
    datasets: [
      {{ label:'MI', data:miVals, borderColor:green,  borderWidth:2.5,
         pointRadius:5, pointBackgroundColor:green,  pointHoverRadius:7,
         fill:'+1', backgroundColor:'rgba(139,92,246,0.12)', tension:0.35 }},
      {{ label:'ME', data:meVals, borderColor:purple, borderWidth:2.5,
         pointRadius:5, pointBackgroundColor:purple, pointHoverRadius:7,
         fill:false, tension:0.35 }}
    ]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    layout:{{ padding:{{ top:26, bottom:24, left:4, right:4 }} }},
    plugins:{{
      legend:{{ display:false }},
      tooltip:{{
        mode:'index', intersect:false,
        callbacks:{{
          label: ctx => ' ' + ctx.dataset.label + ': ' + (fmt(ctx.raw)||'—'),
          footer: items => ' Gap: ' + (fmt(Math.abs(items[1].raw - items[0].raw))||'—')
        }}
      }}
    }},
    scales:{{
      x:{{ grid:{{ color:'rgba(128,128,128,0.12)' }}, ticks:{{ color:'rgba(180,180,180,0.55)', font:{{ size:10 }} }} }},
      y:{{ grid:{{ color:'rgba(128,128,128,0.12)' }}, ticks:{{ color:'rgba(180,180,180,0.55)', font:{{ size:10 }},
        callback: v => v>=1e9?(v/1e9).toFixed(1)+'B': v>=1e6?(v/1e6).toFixed(0)+'M': v>=1e3?(v/1e3).toFixed(0)+'K': v
      }} }}
    }}
  }}
}});
</script>
</body></html>"""

    components.html(html, height=380, scrolling=False)

    # ── Botão exportar histórico completo ────────────────────────────────────
    from utils.exporters import exportar_excel as _exportar_excel  # import local p/ evitar circular
    df_export = df_fat.copy()
    # Renomeia colunas para o Excel
    df_export = df_export.rename(columns={
        "COD_CLIENTE": "Cód. Cliente",
        "CLIENTE": "Cliente",
        "ANO": "Ano",
        "MERCADO": "Mercado",
        "VALOR_TOTAL_FATURADO": "Total Faturado (R$)",
        "QTD_NOTAS": "Qtd. NF",
    })
    df_export = df_export.sort_values(["Ano", "Mercado", "Cliente"], ignore_index=True)
    arquivo = _exportar_excel(
        df_export,
        nome_aba="Faturamento Histórico",
        colunas_moeda=("Total Faturado (R$)",),
    )
    col_exp, _ = st.columns([2, 6])
    with col_exp:
        botao_exportar_excel(
            data=arquivo,
            file_name=f"Faturamento_Historico.xlsx",
            key="crp_fat_historico_excel",
            use_container_width=True,
            label="Exportar histórico (Excel)",
        )


# ── Visão geral ───────────────────────────────────────────────────────────────

def _pct2(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"


def _ticker_indicadores(df: pd.DataFrame, total_aberto: float) -> None:
    """Faixa de indicadores que rola sozinha (pausa ao passar o mouse), acima dos cards."""
    from utils.ptax import buscar_ptax

    vencido = float(df.loc[df["DIAS"] < 0, "SALDO_EM_ABERTO"].sum())
    a_vencer_7 = float(df.loc[(df["DIAS"] >= 0) & (df["DIAS"] <= 7), "SALDO_EM_ABERTO"].sum())
    prazo = (pd.to_datetime(df["VENCIMENTO"]) - pd.to_datetime(df["ENTRADA"])).dt.days
    peso = df["SALDO_EM_ABERTO"]
    prazo_medio = float((prazo * peso).sum() / peso.sum()) if peso.sum() else 0.0
    maior = df.groupby("CLIENTE")["SALDO_EM_ABERTO"].sum().sort_values(ascending=False)

    itens = [
        ("Total em aberto", f"R$ {_abrev(total_aberto)}", ""),
        ("Vencido", f"R$ {_abrev(vencido)}",
         f'<span class="dn">{_pct2(vencido / total_aberto * 100)}</span>' if total_aberto and not _oculto() else ""),
        ("A vencer em 7 dias", f"R$ {_abrev(a_vencer_7)}", ""),
        ("Prazo médio", f"{prazo_medio:.0f} dias", ""),
    ]
    try:
        ptax = buscar_ptax()
    except Exception:
        ptax = {}
    for moeda, simbolo in (("USD", "US$"), ("EUR", "€")):
        cot = ptax.get(moeda)
        if cot:
            var = cot.get("var_venda")
            seta = ""
            if var is not None:
                seta = (f'<span class="{"up" if var >= 0 else "dn"}">{"▲" if var >= 0 else "▼"} '
                        f'{_pct2(abs(var))}</span>')
            itens.append((f"{simbolo} PTAX", f"{cot['venda']:.4f}".replace(".", ","), seta))
    if len(maior):
        itens.append(("Maior devedor", str(maior.index[0]).title(), ""))
    itens.append(("Títulos em aberto", f"{len(df)}", ""))

    faixa = "".join(
        f'<span class="tk-it"><span class="tk-l">{r}</span><span class="tk-v">{v}</span>{x}</span><span class="tk-sep">•</span>'
        for r, v, x in itens
    )
    st.html(f"""
<style>
.tk{{overflow:hidden;white-space:nowrap;border:0.5px solid rgba(128,128,128,.35);border-radius:8px;
     background:rgba(128,128,128,.08);padding:9px 0;margin-bottom:12px}}
.tk-tr{{display:inline-block;animation:tk-rola 40s linear infinite}}
.tk:hover .tk-tr{{animation-play-state:paused}}
.tk-it{{display:inline-flex;align-items:baseline;gap:6px;margin-right:30px;font-size:13px}}
.tk-l{{opacity:.7}} .tk-v{{font-weight:600}}
.tk-sep{{opacity:.4;margin-right:30px}}
.tk .up{{color:#16a34a}} .tk .dn{{color:#dc2626}}
@keyframes tk-rola{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
</style>
<div class="tk"><div class="tk-tr">{faixa}{faixa}</div></div>""")


def _visao_geral(df: pd.DataFrame) -> None:
    for col in ("SALDO_EM_ABERTO", "SALDO_MOEDA", "DIAS"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[(df["SALDO_EM_ABERTO"].fillna(0) > 0) & df["DIAS"].notna()]

    if df.empty:
        st.info("Nenhum título em aberto.")
        return

    faixas = _faixas(date.today())
    df_mi = df[df["MERCADO"] == "MI"]
    df_me = df[df["MERCADO"] == "ME"].copy()
    df_me["MOEDA"] = df_me["MOEDA"].fillna("SEM MOEDA")

    # ── Mercado interno: só reais ──
    valores_mi = [
        float(df_mi.loc[_na_faixa(df_mi["DIAS"], ini, fim), "SALDO_EM_ABERTO"].sum())
        for _, ini, fim in faixas
    ]
    total_mi = sum(valores_mi)
    maximo_mi = max(valores_mi) if valores_mi else 0

    corpo_mi = ""
    linhas_img_mi = []
    for i, ((rotulo, _, _), valor) in enumerate(zip(faixas, valores_mi)):
        if i in (2, 6):
            corpo_mi += _espaco()
        cor = _COR_VENCIDO if i < 2 else (_COR_MI if i < 6 else _COR_A_VENCER)
        corpo_mi += _linha(rotulo, [(valor, cor)], valor, maximo_mi)
        linhas_img_mi.append({"label": rotulo, "segmentos": [(valor, _rgb(cor))],
                              "texto": _completo(valor), "separador": i in (2, 6)})
    cab_mi = ""
    bloco_mi = _bloco("Aging de Vencimentos - Mercado Interno", "MI · R$", _COR_MI, cab_mi, corpo_mi, total_mi)

    # ── Mercado externo: por moeda, com a soma em reais ──
    saldo_moeda = df_me[df_me["MOEDA"] != "R$"].groupby("MOEDA")["SALDO_EM_ABERTO"].sum()
    moedas = list(saldo_moeda.sort_values(ascending=False).index)   # maior saldo em reais primeiro
    cores, extras = {}, iter(_CORES_EXTRAS)
    for m in moedas:
        cores[m] = _CORES_MOEDA.get(m) or next(extras, "#888780")
    cores["R$"] = _COR_COMPL

    por_moeda = {}   # moeda -> (valores em reais por faixa, valores na moeda por faixa)
    for m in moedas + (["R$"] if (df_me["MOEDA"] == "R$").any() else []):
        d = df_me[df_me["MOEDA"] == m]
        reais, nativo = [], []
        for _, ini, fim in faixas:
            sub = d[_na_faixa(d["DIAS"], ini, fim)]
            reais.append(float(sub["SALDO_EM_ABERTO"].sum()))
            nativo.append(float(sub["SALDO_MOEDA"].sum()) if m != "R$" else 0.0)
        por_moeda[m] = (reais, nativo)

    totais_faixa = [sum(por_moeda[m][0][i] for m in por_moeda) for i in range(len(faixas))]
    total_me = sum(totais_faixa)
    maximo_me = max(totais_faixa) if totais_faixa else 0

    corpo_me = ""
    linhas_img_me = []
    for i, (rotulo, _, _) in enumerate(faixas):
        if i in (2, 6):
            corpo_me += _espaco()
        _cor_faixa_me = _COR_VENCIDO if i < 2 else None
        segmentos, dica = [], []
        for m, (reais, nativo) in por_moeda.items():
            segmentos.append((reais[i], _cor_faixa_me or cores[m]))
            if reais[i] > 0:
                dica.append(f"{_SIMBOLOS.get(m, m)} {_completo(nativo[i])}" if m != "R$" else f"NF Compl. R$ {_completo(reais[i])}")
        corpo_me += _linha(rotulo, segmentos, totais_faixa[i], maximo_me, " · ".join(dica))
        linhas_img_me.append({"label": rotulo, "segmentos": [(v, _rgb(c)) for v, c in segmentos],
                              "texto": _completo(totais_faixa[i]), "separador": i in (2, 6)})

    cab_me = _legenda([("NF Compl." if m == "R$" else _SIMBOLOS.get(m, m), cores[m]) for m in por_moeda])
    bloco_me = _bloco("Aging de Vencimentos - Mercado Externo", "ME · por moeda", _COR_COMPL, cab_me, corpo_me, total_me)

    _ticker_indicadores(df, total_mi + sum(sum(v[0]) for v in por_moeda.values()))

    # ── Cards de totais acima dos aging ──
    _cartao = partial(card_html, largura="100%", altura="96px", padding="12px 14px")
    ordem = [m for m in ("USD", "EUR", "GBP") if m in por_moeda] + [m for m in por_moeda if m not in ("USD", "EUR", "GBP", "R$")]
    cards = [_cartao("Mercado Interno", f"R$ {_abrev(total_mi)}", "em reais", cor_borda=_COR_MI)]
    for m in ordem:
        reais, nativo = por_moeda[m]
        cards.append(_cartao(
            _NOMES.get(m, m), f"{_SIMBOLOS.get(m, m)} {_abrev(sum(nativo))}",
            f"R$ {_abrev(sum(reais))}", cor_borda=cores[m],
        ))
    if "R$" in por_moeda:
        cards.append(_cartao("NF Compl.", f"R$ {_abrev(sum(por_moeda['R$'][0]))}",
                             "títulos em reais", cor_borda=_COR_COMPL))
    saldo_moedas = sum(sum(por_moeda[m][0]) for m in ordem)
    cards.append(_cartao("Saldo Moeda (R$)", f"R$ {_abrev(saldo_moedas)}",
                         "moedas convertidas em reais", cor_borda="#6366f1"))
    render_cards_row(cards, distribuir_igual=True)

    cards_img = [{"label": "Mercado Interno", "valor": f"R$ {_abrev(total_mi)}", "sub": "em reais", "cor": _rgb(_COR_MI)}]
    for m in ordem:
        reais, nativo = por_moeda[m]
        cards_img.append({"label": _NOMES.get(m, m), "valor": f"{_SIMBOLOS.get(m, m)} {_abrev(sum(nativo))}",
                          "sub": f"R$ {_abrev(sum(reais))}", "cor": _rgb(cores[m])})
    if "R$" in por_moeda:
        cards_img.append({"label": "NF Compl.", "valor": f"R$ {_abrev(sum(por_moeda['R$'][0]))}",
                          "sub": "títulos em reais", "cor": _rgb(_COR_COMPL)})
    cards_img.append({"label": "Saldo Moeda (R$)", "valor": f"R$ {_abrev(saldo_moedas)}",
                      "sub": "moedas convertidas em reais", "cor": (99, 102, 241)})
    blocos_img = [
        {"nome": "Mercado Interno", "tag": "MI · R$", "legenda": [],
         "total_texto": f"R$ {_completo(total_mi)}", "linhas": linhas_img_mi},
        {"nome": "Mercado Externo", "tag": "ME · por moeda",
         "legenda": [("NF Compl." if m == "R$" else _SIMBOLOS.get(m, m), _rgb(cores[m])) for m in por_moeda],
         "total_texto": f"R$ {_completo(total_me)}", "linhas": linhas_img_me},
    ]
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    col_mi, col_me = st.columns(2)
    col_mi.html(bloco_mi)
    col_me.html(bloco_me)

    # ── Gráfico faturamento por ano ───────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _grafico_faturamento_ano()

    # ── Rankings de clientes ──────────────────────────────────────────────────
    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
    rank_mi, rank_me = st.columns(2)
    with rank_mi:
        _ranking_col(df_mi, "Ranking de clientes em aberto MI", "#1CAE85")
    with rank_me:
        _ranking_col(df_me, "Ranking de clientes em aberto ME", "#E8724A")

    # ── Rankings para o print ─────────────────────────────────────────────────
    def _montar_ranking_img(df_mercado: pd.DataFrame) -> list:
        df_ab = df_mercado[df_mercado["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
        if df_ab.empty or "CLIENTE" not in df_ab.columns:
            return []
        df_r = (
            df_ab.groupby("CLIENTE")["SALDO_EM_ABERTO"]
            .sum().reset_index()
            .sort_values("SALDO_EM_ABERTO", ascending=False)
            .head(10)
        )
        total = float(df_ab["SALDO_EM_ABERTO"].sum()) or 1.0
        maximo = float(df_r["SALDO_EM_ABERTO"].max()) or 1.0
        return [
            {
                "pos": i + 1,
                "nome": row["CLIENTE"],
                "pct": row["SALDO_EM_ABERTO"] / total * 100,
                "valor": float(row["SALDO_EM_ABERTO"]),
                "barw": row["SALDO_EM_ABERTO"] / maximo * 100,
            }
            for i, (_, row) in enumerate(df_r.iterrows())
        ]

    _rankings_img = {
        "mi": {"titulo": "Ranking MI", "cor": (28, 174, 133),  "linhas": _montar_ranking_img(df_mi)},
        "me": {"titulo": "Ranking ME", "cor": (232, 114, 74), "linhas": _montar_ranking_img(df_me)},
    }

    # ── Dados de faturamento para o print ─────────────────────────────────────
    _fat_grafico = None
    try:
        _df_fat_img = carregar_total_faturado_cliente()
        if not _df_fat_img.empty and "ANO" in _df_fat_img.columns and "MERCADO" in _df_fat_img.columns:
            _df_fat_img["VALOR_TOTAL_FATURADO"] = pd.to_numeric(
                _df_fat_img["VALOR_TOTAL_FATURADO"], errors="coerce"
            ).fillna(0)
            _df_fat_img["ANO"] = pd.to_numeric(_df_fat_img["ANO"], errors="coerce")
            _df_fat_img = _df_fat_img.dropna(subset=["ANO"])
            _df_fat_img["ANO"] = _df_fat_img["ANO"].astype(int)
            _mi_s = _df_fat_img[_df_fat_img["MERCADO"] == "MI"].groupby("ANO")["VALOR_TOTAL_FATURADO"].sum().sort_index()
            _me_s = _df_fat_img[_df_fat_img["MERCADO"] == "ME"].groupby("ANO")["VALOR_TOTAL_FATURADO"].sum().sort_index()
            _anos_fat = sorted(set(_mi_s.index) | set(_me_s.index))
            if _anos_fat:
                _fat_grafico = {
                    "anos": _anos_fat,
                    "mi": [float(_mi_s.get(a, 0)) for a in _anos_fat],
                    "me": [float(_me_s.get(a, 0)) for a in _anos_fat],
                }
    except Exception:
        pass

    imagem_png = gerar_imagem_visao_geral(
        "Contas a Receber - Visão Geral", cards_img, blocos_img,
        faturamento_grafico=_fat_grafico, rankings=_rankings_img,
    )
    botoes_acao_row(
        imagem={"data": imagem_png, "file_name": "Contas_a_Receber_Visao_Geral.png", "key": "crp_export_imagem"},
        copiar={"data": imagem_png, "key": "crp_copiar"},
    )
    st.caption(
        "Valores em reais (mercado externo convertido pela cotação do faturamento). "
        "Passe o mouse em uma barra do Mercado Externo para ver os valores em cada moeda."
    )


# ── Entry point ───────────────────────────────────────────────────────────────

TITULOS_SECAO = {"geral": "Visão Geral MI-ME", "mi": "Mercado Interno", "me": "Mercado Externo"}


def render(df_cr: pd.DataFrame, df_grupo_agentes=None, df_grupo_geral=None, secao: str = "geral") -> None:
    """`secao`: "geral" (visão geral), "mi" (mercado interno) ou "me" (mercado externo); cada uma é um item do menu."""
    if "cr_ocultar" not in st.session_state:
        st.session_state["cr_ocultar"] = False

    _ocultar_atual = st.session_state["cr_ocultar"]
    col_t, col_btn, col_atualizar = st.columns([9, 1.4, 1.4])
    with col_t:
        st.title(f"Contas a Receber · {TITULOS_SECAO[secao]}")
    with col_btn:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button(
            "🙈 Ocultar" if not _ocultar_atual else "👁 Exibir",
            key="btn_ocultar_cr", use_container_width=True,
            help="Ocultar/exibir valores nas telas de Contas a Receber",
        ):
            st.session_state["cr_ocultar"] = not _ocultar_atual
            st.rerun()
    with col_atualizar:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="cr_painel_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if df_cr.empty or "MERCADO" not in df_cr.columns:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return

    if secao == "mi":
        contas_receber.render(df_cr[df_cr["MERCADO"] == "MI"], mostrar_titulo=False, df_grupo_agentes=df_grupo_agentes, df_grupo_geral=df_grupo_geral)
    elif secao == "me":
        contas_receber_externo.render(df_cr, mostrar_titulo=False)
    else:
        _visao_geral(df_cr.copy())
