"""
views/faturamento_estado.py
===========================
Painel Comercial "Faturamento por Estado": mapa do Brasil colorido por UF, com seletor de métrica
(Faturado, Em aberto, Inadimplência, Variação) e de período (ano atual / últimos 12 meses). Ao escolher
um estado (clique no mapa ou lista), mostra o detalhe e a lista de clientes dele.

Fontes (as mesmas do painel Faturamento Cliente/Grupo):
  • Faturado: faturado mensal por cliente (24 meses), usando só meses fechados.
  • Em aberto / vencido / prazo: títulos em aberto do Contas a Receber.
  • Estado do cliente: cadastro de agentes (COD_AGENTE -> UF).
Clientes sem estado brasileiro (exterior ou sem cadastro) ficam fora do mapa e aparecem no aviso abaixo dele.
"""

import json
import math
import re
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import render_tabela_html
from utils.exporters import exportar_excel
from views.faturamento_ano import (dados_faturamento_ano, dados_faturamento_mes, html_grafico_faturamento,
                                   html_grafico_faturamento_mes)

_GEO_ARQUIVO = Path(__file__).resolve().parent.parent / "assets" / "brasil_estados.geojson"
_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_SEM_ROTULO = {"DF", "SE", "AL", "RN", "PB"}   # estados pequenos: sem texto no mapa (os números ficam no detalhe ao clicar)

_CSS_LAYOUT = """<style>
.st-key-fe_filtros { position:relative; z-index:10; }                     /* filtros sempre acima da caixa do mapa */
.st-key-fe_mapa_box { margin-top:-140px; position:relative; z-index:1; }   /* puxa o mapa para junto dos filtros */
</style>"""

_METRICAS = {"fat": "Faturado", "abe": "Em aberto", "ina": "Inadimplência", "var": "Variação"}
_PERIODOS = {"ano": "Ano atual"}


@st.cache_resource(show_spinner=False)
def _geo() -> dict:
    return json.loads(_GEO_ARQUIVO.read_text(encoding="utf-8"))


# ── formatação (pt-BR, 2 casas) ──────────────────────────────────────────────────

def _num(v, casas: int = 2) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _brl(v) -> str:
    return "—" if v is None or pd.isna(v) else f"R$ {_num(v)}"


def _mi(v) -> str:
    return "—" if v is None or pd.isna(v) else f"R$ {_num(math.floor(v / 1e6 * 100 + 1e-9) / 100)} mi"   # cortado, não arredondado


def _pct(v, sinal: bool = False) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{'+' if sinal and v > 0 else ''}{_num(v)}%"


# ── períodos (somente meses fechados) ────────────────────────────────────────────

def _janelas(periodo: str):
    """(máscara do período atual, do anterior, descrição) sobre colunas ANO/MES do faturado mensal."""
    hoje = date.today()
    ref_ano, ref_mes = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
    if periodo.isdigit():                                  # ano fechado escolhido (ex.: "2025"): jan–dez vs ano anterior
        ano = int(periodo)
        atual = lambda d: d["ANO"] == ano
        anterior = lambda d: d["ANO"] == ano - 1
        desc = f"jan–dez/{ano} vs {ano - 1}"
        return atual, anterior, desc
    if periodo == "ano":
        atual = lambda d: (d["ANO"] == ref_ano) & (d["MES"] <= ref_mes)
        anterior = lambda d: (d["ANO"] == ref_ano - 1) & (d["MES"] <= ref_mes)
        desc = f"{_MESES[0]}–{_MESES[ref_mes - 1]}/{ref_ano} vs mesmo período de {ref_ano - 1}"
    else:
        ref = ref_ano * 12 + ref_mes
        idx = lambda d: d["ANO"] * 12 + d["MES"]
        atual = lambda d: idx(d).between(ref - 11, ref)
        anterior = lambda d: idx(d).between(ref - 23, ref - 12)
        ini = ref - 11
        desc = (f"{_MESES[(ini - 1) % 12]}/{(ini - 1) // 12}–{_MESES[ref_mes - 1]}/{ref_ano} "
                "vs os 12 meses anteriores")
    return atual, anterior, desc + " (meses fechados)"


def _rotulo_curto(periodo: str) -> str:
    """Período do faturado em poucas palavras, ex.: 'jan–set/2026' ou 'out/2025–set/2026'."""
    if periodo.isdigit():
        return periodo
    hoje = date.today()
    ref_ano, ref_mes = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
    if periodo == "ano":
        return f"jan–{_MESES[ref_mes - 1]}/{ref_ano}" if ref_mes > 1 else f"jan/{ref_ano}"
    ref = ref_ano * 12 + ref_mes
    ini = ref - 11
    return f"{_MESES[(ini - 1) % 12]}/{(ini - 1) // 12}–{_MESES[ref_mes - 1]}/{ref_ano}"


def _rotulo_curto_ant(periodo: str) -> str:
    """Período comparado (anterior), ex.: 'jan–set/2025' ou 'out/2024–set/2025'."""
    if periodo.isdigit():
        return str(int(periodo) - 1)
    hoje = date.today()
    ref_ano, ref_mes = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
    if periodo == "ano":
        return f"jan–{_MESES[ref_mes - 1]}/{ref_ano - 1}" if ref_mes > 1 else f"jan/{ref_ano - 1}"
    ref = ref_ano * 12 + ref_mes - 12
    ini = ref - 11
    return f"{_MESES[(ini - 1) % 12]}/{(ini - 1) // 12}–{_MESES[ref_mes - 1]}/{ref_ano - 1}"


# ── preparação dos dados ─────────────────────────────────────────────────────────

def _mapa_txt(df, col_cod, col_val) -> dict:
    """{código do cliente (texto): valor (texto)} sem vazios; vazio se o DataFrame não tiver as colunas."""
    if df is None or df.empty or not {col_cod, col_val}.issubset(df.columns):
        return {}
    d = df[[col_cod, col_val]].dropna()
    d = d.assign(_v=d[col_val].astype(str).str.strip())
    d = d[d["_v"] != ""]
    return dict(zip(d[col_cod].astype(str), d["_v"]))


def _base_clientes(df_cr, df_mensal, df_agentes, periodo, df_fat=None):
    """DataFrame por cliente: UF, CLIENTE, FAT, FAT_ANT, ABERTO, VENCIDO, PRAZO.
    UF: a de destino gravada na NF (vem nas consultas do faturado mensal e do Contas a Receber); o cadastro de
    agentes (Grupo de Crédito) só entra como reserva. Nome: agentes, depois Contas a Receber, depois o faturado anual."""
    uf_map = {k: v.upper() for k, v in _mapa_txt(df_agentes, "COD_AGENTE", "UF").items()}
    uf_map.update({k: v.upper() for k, v in _mapa_txt(df_cr, "COD_CLIENTE", "UF").items()})
    uf_map.update({k: v.upper() for k, v in _mapa_txt(df_mensal, "COD_CLIENTE", "UF").items()})
    nome_map = {**_mapa_txt(df_fat, "COD_CLIENTE", "CLIENTE"), **_mapa_txt(df_cr, "COD_CLIENTE", "CLIENTE"),
                **_mapa_txt(df_agentes, "COD_AGENTE", "NOME_AGENTE")}

    m = df_mensal.copy()
    m["ANO"] = pd.to_numeric(m["ANO"], errors="coerce")
    m["MES"] = pd.to_numeric(m["MES"], errors="coerce")
    m["COD"] = m["COD_CLIENTE"].astype(str)
    atual, anterior, desc = _janelas(periodo)
    fat = m[atual(m)].groupby("COD")["VALOR_TOTAL_FATURADO"].sum()
    fat_ant = m[anterior(m)].groupby("COD")["VALOR_TOTAL_FATURADO"].sum()

    cr = df_cr.copy()
    cr["COD"] = cr["COD_CLIENTE"].astype(str)
    cr["SALDO"] = pd.to_numeric(cr["SALDO_EM_ABERTO"], errors="coerce").fillna(0)
    cr = cr[cr["SALDO"] > 0]
    aberto = cr.groupby("COD")["SALDO"].sum()
    vencido = cr[cr["SITUACAO"].astype(str).str.upper() == "VENCIDO"].groupby("COD")["SALDO"].sum()
    prazo = pd.Series(dtype=float)
    if {"ENTRADA", "VENCIMENTO"}.issubset(cr.columns):
        dias = (pd.to_datetime(cr["VENCIMENTO"], errors="coerce") - pd.to_datetime(cr["ENTRADA"], errors="coerce")).dt.days
        cr = cr.assign(_DIAS=dias).dropna(subset=["_DIAS"])
        if not cr.empty:   # média do prazo ponderada pelo saldo, por cliente (vetorizada)
            peso = cr.assign(_P=cr["_DIAS"] * cr["SALDO"]).groupby("COD")[["_P", "SALDO"]].sum()
            prazo = (peso["_P"] / peso["SALDO"]).where(peso["SALDO"] > 0)

    cods = sorted(set(fat.index) | set(fat_ant.index) | set(aberto.index))
    base = pd.DataFrame({"COD": cods})
    base["UF"] = base["COD"].map(uf_map).fillna("-")
    base["CLIENTE"] = base["COD"].map(nome_map).fillna(base["COD"])
    base["FAT"] = base["COD"].map(fat).fillna(0.0)
    base["FAT_ANT"] = base["COD"].map(fat_ant).fillna(0.0)
    base["ABERTO"] = base["COD"].map(aberto).fillna(0.0)
    base["VENCIDO"] = base["COD"].map(vencido).fillna(0.0)
    base["PRAZO"] = base["COD"].map(prazo)
    # cliente do exterior (não entra em nada): país diferente de Brasil, ou título do mercado externo
    pais = {**_mapa_txt(df_agentes, "COD_AGENTE", "PAIS"), **_mapa_txt(df_cr, "COD_CLIENTE", "PAIS")}
    me = set(cr.loc[cr["MERCADO"].astype(str).str.upper() == "ME", "COD"]) if "MERCADO" in cr.columns else set()
    base["EXT"] = [(pais.get(c, "BRA").upper() not in ("BRA", "BR", "BRASIL")) or (c in me) for c in base["COD"]]
    return base, desc


def _clientes_uf_ext(df_cr, df_mensal, df_agentes, siglas: set) -> pd.DataFrame:
    """Um registro por cliente do faturado mensal (todo o histórico): UF e se é do exterior. Mesma regra de _base_clientes."""
    uf_map = {k: v.upper() for k, v in _mapa_txt(df_agentes, "COD_AGENTE", "UF").items()}
    uf_map.update({k: v.upper() for k, v in _mapa_txt(df_cr, "COD_CLIENTE", "UF").items()})
    uf_map.update({k: v.upper() for k, v in _mapa_txt(df_mensal, "COD_CLIENTE", "UF").items()})
    pais = {**_mapa_txt(df_agentes, "COD_AGENTE", "PAIS"), **_mapa_txt(df_cr, "COD_CLIENTE", "PAIS")}
    me = set(df_cr.loc[df_cr["MERCADO"].astype(str).str.upper() == "ME", "COD_CLIENTE"].astype(str)) if "MERCADO" in df_cr.columns else set()
    cods = sorted(set(df_mensal["COD_CLIENTE"].astype(str)))
    d = pd.DataFrame({"COD": cods})
    d["UF"] = d["COD"].map(uf_map).fillna("-")
    d["EXT"] = [(pais.get(c, "BRA").upper() not in ("BRA", "BR", "BRASIL")) or (c in me) or (u not in siglas) for c, u in zip(d["COD"], d["UF"])]
    return d


def _serie_estado(base_cod: pd.DataFrame, df_mensal, uf_sel):
    """Faturado mensal (ANO, MES, VALOR_TOTAL_FATURADO, COD_CLIENTE) só dos clientes do estado escolhido, ou de
    todos os clientes brasileiros com estado no mapa (mesma regra do mapa; exterior e sem estado ficam de fora)."""
    ok = base_cod[~base_cod["EXT"]] if uf_sel is None else base_cod[(~base_cod["EXT"]) & (base_cod["UF"] == uf_sel)]
    return df_mensal[df_mensal["COD_CLIENTE"].astype(str).isin(set(ok["COD"]))]


def _por_estado(base: pd.DataFrame, siglas: set) -> pd.DataFrame:
    d = base[base["UF"].isin(siglas)]
    g = d.groupby("UF").agg(FAT=("FAT", "sum"), FAT_ANT=("FAT_ANT", "sum"), ABERTO=("ABERTO", "sum"),
                            VENCIDO=("VENCIDO", "sum"), CLIENTES=("COD", "nunique"))
    g["INA"] = (g["VENCIDO"] / g["ABERTO"] * 100).where(g["ABERTO"] > 0)
    g["VAR"] = ((g["FAT"] / g["FAT_ANT"] - 1) * 100).where(g["FAT_ANT"] > 0)
    # prazo médio do estado: média dos prazos dos clientes ponderada pelo saldo em aberto
    p = d.dropna(subset=["PRAZO"]).assign(_P=lambda x: x["PRAZO"] * x["ABERTO"])
    prazo = (p.groupby("UF")["_P"].sum() / p.groupby("UF")["ABERTO"].sum()).where(p.groupby("UF")["ABERTO"].sum() > 0)
    g["PRAZO"] = prazo
    return g


# ── mapa ─────────────────────────────────────────────────────────────────────────

_ESCALAS = {
    "fat": [[0, "#2a2347"], [1, "#8B7CF6"]],
    "abe": [[0, "#173028"], [1, "#1D9E75"]],
    "ina": [[0, "#3a2327"], [1, "#E24B4A"]],
    "var": [[0, "#E24B4A"], [0.5, "#2a2f3d"], [1, "#1D9E75"]],
}


def _valor_metrica(est: pd.DataFrame, metrica: str) -> pd.Series:
    return {"fat": est["FAT"], "abe": est["ABERTO"], "ina": est["INA"], "var": est["VAR"]}[metrica]


def _rotulo(est: pd.DataFrame, metrica: str, uf: str) -> str:
    v = _valor_metrica(est, metrica).get(uf)
    if v is None or pd.isna(v):
        return uf
    if metrica == "fat":
        return f"<b>{uf}</b><br>{_pct(v / est['FAT'].sum() * 100)}"
    if metrica == "abe":
        return f"<b>{uf}</b><br>{_pct(v / est['ABERTO'].sum() * 100)}"
    return f"<b>{uf}</b><br>{_pct(v, sinal=(metrica == 'var'))}"


def _figura(est: pd.DataFrame, metrica: str, selecionado: str | None = None) -> go.Figure:
    geo = _geo()
    siglas = [f["properties"]["sigla"] for f in geo["features"]]
    centros = {f["properties"]["sigla"]: (f["properties"]["cx"], f["properties"]["cy"]) for f in geo["features"]}
    nomes = {f["properties"]["sigla"]: f["properties"]["nome"] for f in geo["features"]}
    fig = go.Figure()
    fig.add_trace(go.Choropleth(geojson=geo, locations=siglas, z=[0] * len(siglas), featureidkey="properties.sigla",
                                colorscale=[[0, "#262b3b"], [1, "#262b3b"]], showscale=False, hoverinfo="skip",
                                marker_line_color="#0f1117", marker_line_width=0.8))
    com_dado = [u for u in est.index if not pd.isna(_valor_metrica(est, metrica).get(u))]
    z = [float(_valor_metrica(est, metrica)[u]) for u in com_dado]
    extra = {}
    if metrica == "var" and z:
        m = max(abs(min(z)), abs(max(z))) or 1
        extra = {"zmin": -m, "zmax": m}
    fig.add_trace(go.Choropleth(geojson=geo, locations=com_dado, z=z, featureidkey="properties.sigla",
                                colorscale=_ESCALAS[metrica], showscale=False, hoverinfo="none",
                                marker_line_color="#0f1117", marker_line_width=0.8, **extra))
    if selecionado in siglas:
        # destaque feito por camadas de cor (não depende do estilo de seleção do Plotly): os demais estados escurecem
        # e o selecionado fica mais claro, com contorno branco. As camadas não captam o mouse: o clique passa para o mapa.
        outros = [u for u in com_dado if u != selecionado]
        if outros:
            fig.add_trace(go.Choropleth(geojson=geo, locations=outros, z=[1] * len(outros), featureidkey="properties.sigla",
                                        colorscale=[[0, "rgba(15,17,23,0.6)"], [1, "rgba(15,17,23,0.6)"]], showscale=False,
                                        hoverinfo="skip", marker_line_width=0))
        fig.add_trace(go.Choropleth(geojson=geo, locations=[selecionado], z=[1], featureidkey="properties.sigla",
                                    colorscale=[[0, "rgba(255,255,255,0.2)"], [1, "rgba(255,255,255,0.2)"]], showscale=False,
                                    hoverinfo="skip", marker_line_color="#ffffff", marker_line_width=2.6))
    fig.add_trace(go.Scattergeo(lon=[centros[u][0] for u in com_dado], lat=[centros[u][1] for u in com_dado],
                                text=[("" if u in _SEM_ROTULO else _rotulo(est, metrica, u)) for u in com_dado],
                                mode="text", textfont=dict(size=15, color="#ffffff", family="Source Sans Pro, Arial, sans-serif"), hoverinfo="skip", showlegend=False))
    # fitbounds ajusta o Brasil ao quadro do gráfico em qualquer versão do Plotly/navegador (escala fixa estourava o quadro
    # em alguns ambientes): ele sempre aparece inteiro, centralizado e sem corte.
    fig.update_geos(visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator", fitbounds="locations")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=1100, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", dragmode=False)
    return fig


# ── blocos de tela ───────────────────────────────────────────────────────────────

def _legenda(metrica: str, periodo: str) -> str:
    return {
        "fat": f"Faturado ({_rotulo_curto(periodo)}) · % do total",
        "abe": "Em aberto (a receber) · % do total",
        "ina": "Inadimplência: % vencido sobre o saldo em aberto",
        "var": "Variação do faturado vs período anterior",
    }[metrica]


def _total_brasil(est: pd.DataFrame) -> pd.Series:
    """Mesma estrutura de uma linha de estado, somando todos os estados do mapa."""
    fat, ant, abe, ven = est["FAT"].sum(), est["FAT_ANT"].sum(), est["ABERTO"].sum(), est["VENCIDO"].sum()
    pz = est.dropna(subset=["PRAZO"])
    prazo = (pz["PRAZO"] * pz["ABERTO"]).sum() / pz["ABERTO"].sum() if pz["ABERTO"].sum() > 0 else float("nan")
    return pd.Series({"FAT": fat, "FAT_ANT": ant, "ABERTO": abe, "VENCIDO": ven, "CLIENTES": est["CLIENTES"].sum(),
                      "INA": ven / abe * 100 if abe > 0 else float("nan"),
                      "VAR": (fat / ant - 1) * 100 if ant > 0 else float("nan"), "PRAZO": prazo})


def _detalhe_html(titulo: str, r: pd.Series, est: pd.DataFrame, periodo: str, metrica: str = "fat") -> str:
    var = r["VAR"]
    cor_var = "#9aa3b2" if pd.isna(var) else ("#4caf7a" if var >= 0 else "#E24B4A")
    seta = "" if pd.isna(var) else ("▲ " if var >= 0 else "▼ ")
    fat_tot, abe_tot = est["FAT"].sum(), est["ABERTO"].sum()
    ano_ref = int(periodo) if periodo.isdigit() else date.today().year
    grupos = {   # a métrica escolhida no topo vem primeiro; as demais seguem na ordem de sempre
        "fat": [(f"Faturado ({ano_ref})", _brl(r["FAT"]), "#e0e0e0"),
                ("% do faturado total", _pct(r["FAT"] / fat_tot * 100) if fat_tot else "—", "#e0e0e0")],
        "var": [(f"Variação ref. {ano_ref - 1}", f"{seta}{_pct(abs(var)) if not pd.isna(var) else '—'}", cor_var)],
        "abe": [("Em aberto", _brl(r["ABERTO"]), "#4caf7a")]
               + ([("% do em aberto total", _pct(r["ABERTO"] / abe_tot * 100) if abe_tot else "—", "#e0e0e0")] if metrica == "abe" else []),
        "ina": ([("Vencido", _brl(r["VENCIDO"]), "#E24B4A")] if metrica == "ina" else [])
               + [("Inadimplência", _pct(r["INA"]), "#E24B4A" if (not pd.isna(r["INA"]) and r["INA"] > 5) else "#e0e0e0")],
    }
    ordem = ["fat", "abe", "ina"] if metrica != "var" else ["fat", "var", "abe", "ina"]   # Variação só quando é a métrica escolhida
    if metrica in ("abe", "ina"):                    # a métrica escolhida substitui o bloco do Faturado (não se acrescenta)
        ordem = [metrica] + [g for g in ordem if g not in ("fat", metrica)]
    linhas = [l for g in ordem for l in grupos[g]] + [
        ("Clientes", f"{int(r['CLIENTES'])}", "#e0e0e0"),
        ("Prazo médio", "—" if pd.isna(r["PRAZO"]) else f"{_num(r['PRAZO'], 0)} dias", "#e0e0e0"),
    ]
    corpo = "".join(
        f'<div style="display:flex;justify-content:space-between;gap:8px;margin-top:8px;font-size:15px">'
        f'<span style="color:#8892A4">{k}</span><span style="color:{c};font-weight:500;white-space:nowrap">{v}</span></div>'
        for k, v, c in linhas)
    html = (f'<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px">'
            f'<div style="font-size:20px;font-weight:500;color:#fff">{titulo}</div>{corpo}</div>')
    return html.replace("$", "&#36;")


def _ranking_html(est: pd.DataFrame, metrica: str, uf_sel: str, nomes_ordem: list) -> str:
    serie = _valor_metrica(est, metrica).dropna().sort_values(ascending=False).head(8)
    if serie.empty:
        return ""
    mx = float(serie.abs().max()) or 1.0
    cor = {"fat": "#8B7CF6", "abe": "#1D9E75", "ina": "#E24B4A", "var": "#1D9E75"}[metrica]
    linhas = ""
    for uf, v in serie.items():
        c = ("#E24B4A" if v < 0 else "#1D9E75") if metrica == "var" else cor
        txt = _mi(v) if metrica in ("fat", "abe") else _pct(v, sinal=(metrica == "var"))
        borda = "font-weight:600;color:#fff" if uf == uf_sel else "color:#c9d1e6"
        linhas += (f'<div style="display:grid;grid-template-columns:34px 1fr 108px;gap:8px;align-items:center;'
                   f'font-size:14px;margin:7px 0"><span style="{borda}">{uf}</span>'
                   f'<div style="height:11px;border-radius:5px;background:#262b3b;overflow:hidden">'
                   f'<div style="width:{abs(v) / mx * 100:.1f}%;height:100%;background:{c}"></div></div>'
                   f'<span style="text-align:right;color:#e0e0e0">{txt}</span></div>')
    titulo = {"fat": "faturado", "abe": "em aberto", "ina": "inadimplência", "var": "variação"}[metrica]
    html = (f'<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px">'
            f'<div style="font-size:12.5px;color:#8892A4;margin:0 0 4px;letter-spacing:.3px;text-transform:uppercase">'
            f'Top 8 estados — {titulo}</div>{linhas}</div>')
    return html.replace("$", "&#36;")


def _trunca(v: float, divisor: float) -> float:
    """v / divisor cortado (não arredondado) na 2ª casa: 2.587.431,20 em milhões vira 2,58."""
    return math.floor(v / divisor * 100 + 1e-9) / 100


def _curto(v: float) -> str:
    """Valor compacto em reais, cortado na 2ª casa (nunca para cima): 'R$ 2,58 mi' ou 'R$ 372,80 mil'."""
    if v >= 1e6:
        return f"R$ {_num(_trunca(v, 1e6))} mi"
    return f"R$ {_num(_trunca(v, 1e3))} mil" if v >= 1e3 else f"R$ {_num(v)}"


def _clientes_html(base: pd.DataFrame, uf_sel: str | None, nome_uf: str, periodo: str, siglas: set,
                   metrica: str = "fat") -> str:
    """Card 'Maiores clientes': top 30 (lista com barra de rolagem, 5 visíveis) pela métrica escolhida, no Brasil ou no estado selecionado.
    Cor e ranking acompanham a métrica: faturado (azul), em aberto (verde), vencido/inadimplência (vermelho) e
    variação em R$ do faturado (verde para alta, vermelho para queda)."""
    d = base[(base["UF"] == uf_sel) if uf_sel else base["UF"].isin(siglas)].copy()
    d["VAR_R"] = d["FAT"] - d["FAT_ANT"]
    if metrica == "abe":
        col, titulo, cor = "ABERTO", "em aberto", "#1D9E75"
    elif metrica == "ina":
        col, titulo, cor = "VENCIDO", "vencido", "#E24B4A"
    elif metrica == "var":
        col, titulo, cor = "VAR_R", f"variação do faturado {_rotulo_curto(periodo)}", None
    else:
        col, titulo, cor = "FAT", f"faturado {_rotulo_curto(periodo)}", "#8B7CF6"
    d = d[d[col] != 0] if col == "VAR_R" else d[d[col] > 0]
    top = d.reindex(d[col].abs().sort_values(ascending=False).index).head(30)
    if top.empty:
        return ""
    mx = float(top[col].abs().max()) or 1.0
    linhas = ""
    for _, r in top.iterrows():
        v = float(r[col])
        c = cor or ("#1D9E75" if v >= 0 else "#E24B4A")
        txt = ("+" if (col == "VAR_R" and v > 0) else "-" if v < 0 else "") + _curto(abs(v))
        linhas += (f'<div style="display:flex;justify-content:space-between;gap:8px;margin-top:11px;font-size:14px">'
                   f'<span style="color:#c9d1e6;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{_html_txt(r["CLIENTE"])}</span>'
                   f'<span style="color:{c if col == "VAR_R" else "#e0e0e0"};white-space:nowrap">{txt}</span></div>'
                   f'<div style="height:10px;border-radius:5px;background:#262b3b;overflow:hidden;margin-top:4px">'
                   f'<div style="width:{abs(v) / mx * 100:.1f}%;height:100%;background:{c}"></div></div>')
    html = (f'<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px">'
            f'<div style="font-size:12.5px;color:#8892A4;letter-spacing:.3px;text-transform:uppercase">'
            f'Maiores clientes — {nome_uf} · {titulo}</div>'
            f'<div style="max-height:290px;overflow-y:auto;scrollbar-width:thin;padding-right:8px;margin-right:-8px">{linhas}</div></div>')
    return html.replace("$", "&#36;")


def _html_txt(texto) -> str:
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tabela_clientes(base: pd.DataFrame, uf: str | None, ordem: str, est_siglas=()) -> pd.DataFrame:
    d = base[base["UF"] == uf].copy() if uf else base[base["UF"].isin(est_siglas)].copy()
    d["INADIMPLENCIA"] = (d["VENCIDO"] / d["ABERTO"] * 100).where(d["ABERTO"] > 0)
    d["VARIACAO"] = ((d["FAT"] / d["FAT_ANT"] - 1) * 100).where(d["FAT_ANT"] > 0)
    chave = {"Faturado": "FAT", "Em aberto": "ABERTO", "Vencido": "VENCIDO", "Inadimplência": "INADIMPLENCIA",
             "Variação": "VARIACAO", "Cliente": "CLIENTE"}[ordem]
    return d.sort_values(chave, ascending=(chave == "CLIENTE"), na_position="last")


def render(df_cr: pd.DataFrame, df_mensal: pd.DataFrame, df_agentes: pd.DataFrame, df_fat: pd.DataFrame = None) -> None:
    c_t, c_b = st.columns([9, 1.4])
    with c_t:
        st.title("Faturamento por Estado — Mercado Interno")
    with c_b:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="fe_atualizar", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    precisa_mensal = {"COD_CLIENTE", "ANO", "MES", "VALOR_TOTAL_FATURADO"}
    if (df_mensal is None or df_mensal.empty or not precisa_mensal.issubset(df_mensal.columns)
            or df_cr is None or df_cr.empty):
        st.warning("Dados insuficientes para montar o painel (faturado mensal, cadastro de clientes e Contas a Receber).")
        return

    if "_fe_lista_pend" in st.session_state:                       # aplica a escolha feita pelo clique no mapa
        st.session_state["fe_uf_lista"] = st.session_state.pop("_fe_lista_pend")
    st.markdown(_CSS_LAYOUT, unsafe_allow_html=True)
    with st.container(key="fe_filtros"):
        c1, c_dir = st.columns([2.7, 1], gap="large", vertical_alignment="bottom")   # mesmas colunas do mapa/cards
        c2, c3 = c_dir.columns([1, 1.5], vertical_alignment="bottom")                 # Período e Estado sobre os cards
    with c1:
        metrica = st.segmented_control("Métrica", list(_METRICAS), format_func=_METRICAS.get, default="fat",
                                       key="fe_metrica", width="content") or "fat"
    with c2:
        if metrica in ("fat", "var"):
            anos = pd.to_numeric(df_mensal["ANO"], errors="coerce").dropna().astype(int)
            lista = list(_PERIODOS) + [str(a) for a in range(date.today().year - 1, int(anos.min()) - 1, -1)] if len(anos) else list(_PERIODOS)
            if st.session_state.get("fe_periodo") not in lista:
                st.session_state["fe_periodo"] = "ano"
            periodo = st.selectbox("Período", lista, key="fe_periodo", format_func=lambda k: str(date.today().year) if k == "ano" else k)
        else:
            periodo = st.session_state.get("fe_periodo") or "ano"

    base, desc = _base_clientes(df_cr, df_mensal, df_agentes, periodo, df_fat)
    siglas = {f["properties"]["sigla"] for f in _geo()["features"]}
    est = _por_estado(base, siglas)
    if est.empty:
        st.warning("Nenhum cliente com estado brasileiro encontrado.")
        return

    # ── seleção: um estado (clique no mapa ou lista) ou o Brasil inteiro (nada selecionado) ──────
    nomes = {f["properties"]["sigla"]: f["properties"]["nome"] for f in _geo()["features"]}
    ordem_uf = list(_valor_metrica(est, metrica).dropna().sort_values(ascending=False).index) or list(est.index)
    uf_sel = st.session_state.get("fe_uf")
    if uf_sel not in est.index:
        uf_sel = None
    chave_vis = (metrica, periodo)
    if st.session_state.get("fe_chave_vis") != chave_vis:        # outro mapa: a seleção dele recomeça
        st.session_state["fe_chave_vis"] = chave_vis
        st.session_state["fe_mapa_n"] = st.session_state.get("fe_mapa_n", 0) + 1
        st.session_state["fe_ult_clique"] = None

    with c3:
        opcoes = ["BR"] + ordem_uf + [u for u in est.index if u not in ordem_uf]
        if st.session_state.get("fe_uf_lista") not in opcoes:
            st.session_state["fe_uf_lista"] = uf_sel or "BR"
        escolha = st.selectbox("Estado", opcoes, key="fe_uf_lista",
                               format_func=lambda u: "Brasil (todos os estados)" if u == "BR" else f"{nomes[u]} ({u})")
    novo_uf = None if escolha == "BR" else escolha
    if novo_uf != uf_sel:                                         # escolheu na lista: o mapa recomeça sem seleção
        st.session_state["fe_uf"] = novo_uf
        st.session_state["fe_ult_clique"] = None
        st.session_state["fe_mapa_n"] = st.session_state.get("fe_mapa_n", 0) + 1
        st.rerun()

    # ── mapa à esquerda (altura total) e, à direita, os dois cards empilhados (nada sobre o mapa) ──
    col_mapa, col_cards = st.columns([2.7, 1], gap="large")
    with col_mapa.container(key="fe_mapa_box"):
        evento = st.plotly_chart(_figura(est, metrica, uf_sel), key=f"fe_mapa_{st.session_state.get('fe_mapa_n', 0)}",
                                 on_select="rerun", selection_mode="points", config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False},   # mapa fixo: sem zoom nem arrasto
                                 width="stretch")
    with col_cards:
        if uf_sel is None:
            st.markdown(_detalhe_html("Brasil — todos os estados", _total_brasil(est), est, periodo, metrica), unsafe_allow_html=True)
        else:
            st.markdown(_detalhe_html(f"{nomes[uf_sel]} ({uf_sel})", est.loc[uf_sel], est, periodo, metrica), unsafe_allow_html=True)
        st.markdown("<div style='height:6px'></div>" + _ranking_html(est, metrica, uf_sel, ordem_uf), unsafe_allow_html=True)
        st.markdown("<div style='height:6px'></div>" + _clientes_html(base, uf_sel, nomes[uf_sel] if uf_sel else "Brasil", periodo, siglas, metrica),
                    unsafe_allow_html=True)

    # ── Total Faturado (mesmo card do Faturamento Cliente/Grupo), do estado escolhido ou do Brasil ──
    cli = _clientes_uf_ext(df_cr, df_mensal, df_agentes, siglas)
    serie = _serie_estado(cli, df_mensal, uf_sel)
    codigos = list(serie["COD_CLIENTE"].astype(str).unique())
    por_ano = dados_faturamento_ano(serie, codigos)
    if por_ano:
        meses = dados_faturamento_mes(serie, codigos)
        st.markdown("<style>div[class*='st-key-fe_fat_wrap'] { position:relative !important; }"
                    "div[class*='st-key-fe_fat_modo'] { position:absolute !important; top:8px !important; right:14px !important;"
                    " z-index:10; margin:0 !important; gap:6px !important; width:96px !important; }"
                    "div[class*='st-key-fe_fat_modo'] button { min-height:28px !important; padding:2px 8px !important; }"
                    "div[class*='st-key-fe_fat_modo'] button p { font-size:12px !important; }</style>", unsafe_allow_html=True)
        rot = "Total Faturado — " + ("Brasil — todos os estados" if uf_sel is None else f"{nomes[uf_sel]} ({uf_sel})")
        with st.container(key="fe_fat_wrap"):
            modo = "Por ano"
            faixa = st.empty()
            if meses:
                modo = st.session_state.get("fe_fat_modo_sel", "Por ano")
                with st.container(key="fe_fat_modo"):
                    for r, k in (("Por ano", "fe_fat_btn_ano"), ("Por mês", "fe_fat_btn_mes")):
                        if st.button(r, key=k, use_container_width=True, type="primary" if modo == r else "secondary"):
                            st.session_state["fe_fat_modo_sel"] = r
                            st.rerun()
            if modo == "Por mês" and meses:
                html = html_grafico_faturamento_mes(meses, com_botao=True).replace("Faturado nos últimos 12 meses", rot + " — 12 meses", 1)
            else:
                html = html_grafico_faturamento(por_ano, sum(v for _, v in por_ano), com_botao=bool(meses)).replace("Total Faturado", rot, 1)
            faixa.html(html)

    st.caption(f"Período: {desc} · " + _legenda(metrica, periodo)
               + " · clique no estado para ver os clientes; clique de novo para voltar ao Brasil")
    # exterior não é medido: fora do mapa só aparece o que é brasileiro e ficou sem estado no cadastro
    ext = base["EXT"] | (~base["UF"].isin(siglas) & ~base["UF"].isin(["-", "", "NAN", "NONE"]))
    fora = base[~base["UF"].isin(siglas) & ~ext & ((base["FAT"] > 0) | (base["ABERTO"] > 0))]
    if not fora.empty:
        st.caption((f"Sem estado no cadastro (fora do mapa): {len(fora)} cliente(s), "
                    f"faturado {_brl(fora['FAT'].sum())} e em aberto {_brl(fora['ABERTO'].sum())}.").replace("$", "&#36;"))
    pontos = [p for p in (evento.selection.points if evento and evento.selection else [])
              if p.get("curve_number") == 1 and p.get("location") in est.index]
    clicado = pontos[0]["location"] if pontos else None
    if clicado:     # o gráfico é recriado a cada mudança, então qualquer ponto vindo dele é um clique novo
        novo = None if clicado == uf_sel else clicado        # clicar de novo no mesmo estado volta ao Brasil
        st.session_state["fe_uf"] = novo
        st.session_state["_fe_lista_pend"] = novo or "BR"
        st.session_state["fe_mapa_n"] = st.session_state.get("fe_mapa_n", 0) + 1
        st.rerun()

    # ── clientes do estado (ou de todos os estados) ─────────────────────────────────
    st.divider()
    ct, co = st.columns([3, 2], vertical_alignment="center")
    ct.subheader("Clientes — Brasil (todos os estados)" if uf_sel is None else f"Clientes — {nomes[uf_sel]} ({uf_sel})")
    ordem = co.selectbox("Ordenar por", ["Faturado", "Em aberto", "Vencido", "Inadimplência", "Variação", "Cliente"],
                         key="fe_ordem")
    tab = _tabela_clientes(base, uf_sel, ordem, siglas)
    rot, rot_ant = _rotulo_curto(periodo), _rotulo_curto_ant(periodo)
    st.caption(f"{len(tab)} cliente(s) · Faturamento: {rot_ant} e {rot} (meses fechados) · "
               "Em aberto, vencido e inadimplência: posição de hoje")
    col_ant, col_fat = f"Faturamento {rot_ant} (R$)", f"Faturamento {rot} (R$)"
    exib = pd.DataFrame({
        "Cliente": tab["CLIENTE"],
        **({"UF": tab["UF"]} if uf_sel is None else {}),
        col_ant: tab["FAT_ANT"].map(_num),
        col_fat: tab["FAT"].map(_num),
        "Em aberto (R$)": tab["ABERTO"].map(_num),
        "Vencido (R$)": tab["VENCIDO"].map(_num),
        "Inadimplência": tab["INADIMPLENCIA"].map(_pct),
        "Variação": tab["VARIACAO"].map(lambda v: _pct(v, sinal=True)),
        "Prazo médio": tab["PRAZO"].map(lambda v: "—" if pd.isna(v) else f"{_num(v, 0)} dias"),
        "SITUACAO": [("VENCIDO" if v > 0 else ("A VENCER" if a > 0 else "—")) for v, a in zip(tab["VENCIDO"], tab["ABERTO"])],
    })
    render_tabela_html(exib, colunas_renomear={"SITUACAO": "Situação"}, colunas_moeda=[col_ant, col_fat, "Em aberto (R$)"],
                       coluna_situacao="SITUACAO", altura=460, colunas_centralizar=["UF"])

    # ── Excel: todos os clientes, de todos os estados ──────────────────────────────
    todos = base[base["UF"].isin(siglas)].copy()
    todos["Inadimplência %"] = (todos["VENCIDO"] / todos["ABERTO"] * 100).where(todos["ABERTO"] > 0).round(2)
    todos["Variação %"] = ((todos["FAT"] / todos["FAT_ANT"] - 1) * 100).where(todos["FAT_ANT"] > 0).round(2)
    todos["Estado"] = todos["UF"].map(nomes)
    xl = todos.sort_values(["UF", "FAT"], ascending=[True, False]).rename(columns={
        "UF": "UF", "CLIENTE": "Cliente", "FAT": col_fat, "FAT_ANT": col_ant,
        "ABERTO": "Em aberto (R$)", "VENCIDO": "Vencido (R$)", "PRAZO": "Prazo médio (dias)"})
    xl["Prazo médio (dias)"] = xl["Prazo médio (dias)"].round(0)
    xl = xl[["UF", "Estado", "Cliente", col_ant, col_fat, "Variação %",
             "Em aberto (R$)", "Vencido (R$)", "Inadimplência %", "Prazo médio (dias)"]]
    botao_exportar_excel(
        exportar_excel(xl, "FATURAMENTO_ESTADO",
                       colunas_moeda=(col_ant, col_fat, "Em aberto (R$)", "Vencido (R$)"),
                       colunas_percentual=("Variação %", "Inadimplência %"),
                       colunas_verde_vermelho=("Variação %",)),
        "Faturamento por Estado.xlsx", key="fe_excel",
    )
