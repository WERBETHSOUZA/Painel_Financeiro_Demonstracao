"""
utils/ptax.py
=============
Busca cotações PTAX do Banco Central do Brasil (API pública, sem autenticação).
"""

from __future__ import annotations

import datetime
from typing import Optional

import requests
import streamlit as st

_BASE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"

_URL_DIA = (
    _BASE + "CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)"
    "?@moeda='{moeda}'&@dataCotacao='{data}'"
    "&$format=json&$top=5"
)

# Sem $select: o gateway do BCB responde 403 (página HTML) quando a URL traz $select.
_URL_PERIODO = (
    _BASE + "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@di,dataFinalCotacao=@df)"
    "?@moeda='{moeda}'&@di='{inicio}'&@df='{fim}'"
    "&$format=json&$filter=tipoBoletim eq 'Fechamento'&$top=100"
)

_BCB_LINK = "https://www.bcb.gov.br/estabilidadefinanceira/historicocotacoes"


def _ultimo_dia_util(ref: datetime.date) -> datetime.date:
    d = ref - datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


def _fmt(d: datetime.date) -> str:
    return d.strftime("%m-%d-%Y")


def _get(url: str) -> Optional[list]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json().get("value") or []
    except Exception:
        return None


def _buscar_dia(moeda: str, data: datetime.date) -> Optional[dict]:
    valores = _get(_URL_DIA.format(moeda=moeda, data=_fmt(data)))
    if valores:
        d = valores[-1]
        return {
            "compra": float(d["cotacaoCompra"]), "venda": float(d["cotacaoVenda"]),
            # no dia corrente o último boletim pode ser intermediário (ainda sem o fechamento)
            "parcial": not str(d.get("tipoBoletim", "Fechamento")).startswith("Fechamento"),
            "hora": str(d.get("dataHoraCotacao", ""))[11:16],
        }
    return None


def _candidatos(n: int, incluir_hoje: bool = False) -> list[datetime.date]:
    """Dias úteis candidatos, do mais recente para o mais antigo. Com `incluir_hoje`,
    o dia corrente (se for dia útil) vem primeiro; sem ele, começa em D-1."""
    cands, d = [], datetime.date.today()
    if incluir_hoje and d.weekday() < 5:
        cands.append(d)
    while len(cands) < n:
        d = _ultimo_dia_util(d)
        cands.append(d)
    return cands


class _PtaxIndisponivel(Exception):
    """BCB não respondeu para nenhuma data candidata. Exceção não fica no cache do Streamlit."""


@st.cache_data(ttl=900, show_spinner=False)
def _buscar_ptax_cache() -> dict:
    # Tenta a cotação do dia; se o BCB ainda não publicou (antes das ~10h, feriado), cai para o
    # último dia útil com cotação. A variação é sempre contra o dia útil anterior ao usado.
    cands = _candidatos(10, incluir_hoje=True)

    d1 = d2 = None
    d1_idx = 0
    for i, data in enumerate(cands):
        r = {m: _buscar_dia(m, data) for m in ("EUR", "GBP", "USD")}
        if any(v for v in r.values()):
            if d1 is None:
                d1 = {"data_ref": data, **r}
                d1_idx = i
            elif d2 is None and i > d1_idx:
                d2 = {"data_ref": data, **r}
                break

    if d1 is None:
        raise _PtaxIndisponivel()

    d1["data_anterior"] = d2["data_ref"] if d2 else None
    d1["anterior"] = {m: d2.get(m) for m in ("EUR", "GBP", "USD")} if d2 else {}
    d1["parcial"] = any(d1[m]["parcial"] for m in ("EUR", "GBP", "USD") if d1.get(m))
    d1["hora"] = max((d1[m]["hora"] for m in ("EUR", "GBP", "USD") if d1.get(m)), default="")
    for m in ("EUR", "GBP", "USD"):
        if d1.get(m) and d2 and d2.get(m):
            v1, v2 = d1[m]["venda"], d2[m]["venda"]
            d1[m]["var_venda"] = ((v1 - v2) / v2 * 100) if v2 else None
        elif d1.get(m):
            d1[m]["var_venda"] = None

    return d1


def buscar_ptax() -> dict:
    """
    Retorna a PTAX mais recente (a do dia, se já publicada; senão a do último dia útil)
    com variação vs o dia útil anterior (`data_anterior`). `parcial` indica boletim
    intermediário do dia, ainda sem o fechamento.

    Estrutura por moeda:
        {"compra": float, "venda": float, "var_venda": float | None}

    Falha do BCB não fica em cache: a próxima chamada tenta de novo.
    """
    try:
        return _buscar_ptax_cache()
    except _PtaxIndisponivel:
        return {"data_ref": datetime.date.today(), "data_anterior": None, "anterior": {}, "parcial": False,
                "hora": "", "EUR": None, "GBP": None, "USD": None}


@st.cache_data(ttl=3600, show_spinner=False)
def _base_mes_cache() -> dict:
    ult = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    r = buscar_ptax_data(ult)
    if not any(r.get(m) for m in ("EUR", "GBP", "USD")):
        raise _PtaxIndisponivel()
    return r


def buscar_ptax_base_mes() -> dict:
    """PTAX de venda do último dia útil do mês anterior: base da variação cambial do mês.
    Retorna {"data_ref": date, "USD": {"venda": ...} | None, "EUR": ..., "GBP": ...}.
    Falha do BCB não fica em cache."""
    try:
        return _base_mes_cache()
    except _PtaxIndisponivel:
        return {"data_ref": None, "USD": None, "EUR": None, "GBP": None}


def limpar_cache_ptax() -> None:
    """Descarta a cotação e o histórico em cache para buscar de novo no BCB."""
    _buscar_ptax_cache.clear()
    _base_mes_cache.clear()
    buscar_historico_ptax.clear()


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_ptax_data(data: datetime.date) -> dict:
    """Retorna PTAX venda para USD, EUR e GBP na data informada.
    Se não houver cotação (feriado/fim de semana), usa o último dia útil anterior.
    Retorna: {"data_ref": date, "USD": {"venda": float} | None, "EUR": ..., "GBP": ...}
    """
    moedas = ("USD", "EUR", "GBP")
    data_ref = data
    for _ in range(10):
        r = {m: _buscar_dia(m, data_ref) for m in moedas}
        if any(v for v in r.values()):
            return {"data_ref": data_ref, **r}
        data_ref -= datetime.timedelta(days=1)
        while data_ref.weekday() >= 5:
            data_ref -= datetime.timedelta(days=1)
    return {"data_ref": data, "USD": None, "EUR": None, "GBP": None}


@st.cache_data(ttl=86400, show_spinner=False)
def buscar_historico_ptax(moeda: str, dias: int = 30) -> list[dict]:
    """
    Retorna histórico de fechamento PTAX dos últimos `dias` dias úteis.
    Lista ordenada do mais recente para o mais antigo.
    Cada item: {"data": date, "compra": float, "venda": float}
    """
    fim = _candidatos(1)[0]
    inicio = fim - datetime.timedelta(days=dias * 2)  # margem para fins de semana/feriados

    valores = _get(_URL_PERIODO.format(moeda=moeda, inicio=_fmt(inicio), fim=_fmt(fim)))
    if not valores:
        return []

    historico = []
    for v in valores:
        try:
            data_str = v["dataHoraCotacao"][:10]
            data = datetime.date.fromisoformat(data_str)
            historico.append({
                "data":   data,
                "compra": float(v["cotacaoCompra"]),
                "venda":  float(v["cotacaoVenda"]),
            })
        except Exception:
            continue

    historico.sort(key=lambda x: x["data"], reverse=True)
    return historico[:dias]


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_ptax_mes_anterior_e_vigente() -> list[dict]:
    """
    Cotações de fechamento PTAX do mês anterior e do mês vigente, até o último dia útil com cotação.
    Lista em ordem crescente de data. Cada item:
        {"data": date, "EUR": {"compra", "venda"}, "GBP": {...}, "USD": {...}}
    Dias sem cotação em alguma moeda ficam de fora. Falha do BCB não fica em cache.
    """
    fim = _candidatos(1)[0]
    hoje = datetime.date.today()
    primeiro_vigente = hoje.replace(day=1)
    primeiro_anterior = (primeiro_vigente - datetime.timedelta(days=1)).replace(day=1)
    # margem de 7 dias antes do mês anterior: precisa do último dia útil anterior para a variação
    inicio = primeiro_anterior - datetime.timedelta(days=7)

    por_data: dict[datetime.date, dict] = {}
    for m in ("EUR", "GBP", "USD"):
        valores = _get(_URL_PERIODO.format(moeda=m, inicio=_fmt(inicio), fim=_fmt(fim)))
        if valores is None:
            raise _PtaxIndisponivel()
        for v in valores:
            try:
                data = datetime.date.fromisoformat(v["dataHoraCotacao"][:10])
                linha = por_data.setdefault(data, {"data": data})
                linha[m] = {"compra": float(v["cotacaoCompra"]), "venda": float(v["cotacaoVenda"])}
            except Exception:
                continue

    # inclui a margem anterior ao mês anterior: serve só para calcular a variação do primeiro dia
    return [por_data[d] for d in sorted(por_data) if all(m in por_data[d] for m in ("EUR", "GBP", "USD"))]


def link_bcb() -> str:
    return _BCB_LINK
