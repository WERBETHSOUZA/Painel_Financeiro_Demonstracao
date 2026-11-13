"""
utils/pendencias.py
===================
Card "Notas Pendentes de Validação" da Situação Cliente e do Grupo de Crédito (Mercado Interno), colorido pela situação mais
grave das notas (consulta QUERY_PENDENCIAS_BLOQUEANTES.sql):

    VERMELHO  há nota com pendência BLOQUEANTE (prazo documental vencido)
    AZUL      não há bloqueio, mas há nota com VALIDAÇÃO MANUAL pendente (documento aguardando validação OCR/revisão)
    VERDE     nenhuma pendência
    CINZA     banco indisponível ("—")

O número grande é o total de notas que precisam de atenção (bloqueantes + validação manual); o detalhe de cada situação e o Prazo
ficam abaixo. É só informação: não muda a regra do Status do Faturamento (Liberado/Bloqueado), que vem do crédito.
"""

from __future__ import annotations

import re
from html import escape

import pandas as pd

ROTULO = "Notas Pendentes de Validação"

# (cor da borda, cor do fundo do card, cor do rótulo)
_VERMELHO = ("#E24B4A", "rgba(226,75,74,0.20)", "#f3c9c9")
_AZUL = ("#378ADD", "rgba(55,138,221,0.22)", "#c4dcf5")
_VERDE = ("#22c55e", "rgba(34,197,94,0.10)", "#aaaaaa")
_CINZA = ("#6b7280", "#1e1e2e", "#aaaaaa")
_PONTO_VERMELHO = "<span style='color:#ff6b6b'>●</span>"
_PONTO_AZUL = "<span style='color:#6db3f5'>●</span>"


# Card estreito (janela pequena): o subtítulo troca para a versão compacta (sem o ano, "bloq." e "manual") para não quebrar de linha
# e deixar o card mais alto que os vizinhos. O próprio subtítulo (.pv-box) é o contêiner da consulta de largura, então funciona
# em qualquer tela (o card em si só vira contêiner em alguns casos).
_CSS_COMPACTO = ("<style>.pv-box{display:block;container-type:inline-size}"
                 ".pv-rot{display:inline-block;width:100%;vertical-align:top;container-type:inline-size}"
                 "@container (max-width: 220px){.pv-l{display:none}}"
                 "@container (min-width: 221px){.pv-c{display:none}}"
                 "@container (max-width: 185px){.pv-ll{display:none}}"
                 "@container (min-width: 186px){.pv-lc{display:none}}</style>")
# Título: "Notas Pendentes de Validação" no card largo e "Pendentes de Validação" no estreito (para caber numa linha só)
_ROTULO_HTML = ("<span class='pv-rot'><span class='pv-ll'>Notas Pendentes de Validação</span>"
                "<span class='pv-lc'>Pendentes de Validação</span></span>")


def _v(longo: str, curto: str) -> str:
    """Texto em duas versões: a longa (card largo) e a compacta (card estreito)."""
    return f"<span class='pv-l'>{longo}</span><span class='pv-c'>{curto}</span>"


def _prazo(serie) -> str:
    menor = pd.to_datetime(serie, errors="coerce").min()
    if pd.isna(menor):
        return "sem prazo"
    return _v(menor.strftime("%d/%m/%Y"), menor.strftime("%d/%m"))


def _soma(df: pd.DataFrame, coluna: str) -> int:
    return int(pd.to_numeric(df[coluna], errors="coerce").fillna(0).sum()) if len(df) else 0


def card_pendencias(codigos, cartao) -> str:
    """HTML do card para um cliente ou para os clientes de um grupo.

    `codigos`: códigos de agente (cliente) a somar. `cartao`: função que monta o card da tela, no formato
    cartao(rotulo, valor, subtitulo=..., cor_borda=..., cor_fundo=..., cor_label=...) (cada tela tem o seu tamanho e padding).
    Se o banco não responder, o card mostra "—" e a tela continua normal."""
    from services.data_service import carregar_pendencias_bloqueantes   # import aqui: a tela não depende do banco para abrir

    def monta(valor, sub, cores, compacto=False):
        borda, fundo, rotulo = cores
        if compacto:   # subtítulo com duas versões (largo/estreito)
            sub = f"<span class='pv-box'>{sub}</span>"
        return cartao(_CSS_COMPACTO + _ROTULO_HTML, valor, subtitulo=sub, cor_borda=borda, cor_fundo=fundo, cor_label=rotulo)

    df = carregar_pendencias_bloqueantes()
    if df is None:
        return monta("—", "indisponível no momento", _CINZA)
    cods = {str(int(float(c))) for c in codigos if str(c).strip() not in ("", "nan", "None")}
    x = df[df["COD_CLIENTE"].astype(str).isin(cods)] if not df.empty else df
    bloq, manual = _soma(x, "QTD_BLOQUEANTES"), _soma(x, "QTD_MANUAL")
    if bloq + manual == 0:
        return monta("0", "nenhuma pendência", _VERDE)

    clientes = int(((pd.to_numeric(x["QTD_BLOQUEANTES"], errors="coerce").fillna(0) + pd.to_numeric(x["QTD_MANUAL"], errors="coerce").fillna(0)) > 0).sum())
    de_clientes = f" · {clientes} clientes" if clientes > 1 else ""
    if bloq and manual:      # as duas situações: vale o vermelho e o card mostra as duas contagens
        sub = (f"{_PONTO_VERMELHO} {bloq} " + _v(f"bloqueante{'s' if bloq > 1 else ''}", "bloq.")
               + f" · {_PONTO_AZUL} {manual} " + _v("validação manual", "manual")
               + f"<br>Prazo {_prazo(x['PRAZO_BLOQUEIO'])}{de_clientes}")
        return monta(str(bloq + manual), sub, _VERMELHO, compacto=True)
    if bloq:
        return monta(str(bloq), f"{_PONTO_VERMELHO} Bloqueante{de_clientes} · Prazo {_prazo(x['PRAZO_BLOQUEIO'])}", _VERMELHO, compacto=True)
    return monta(str(manual), f"{_PONTO_AZUL} " + _v("Validação manual", "Manual") + f"{de_clientes} · Prazo {_prazo(x['PRAZO_MANUAL'])}", _AZUL, compacto=True)


# ── Gráfico "Notas pendentes de validação" (Situação Cliente) ──────────────────────────────────────────────────────────
def _nome_documento(motivo) -> str:
    """Nome do documento a partir do texto do motivo ("Documento obrigatório CNH do motorista ainda não foi anexado...")."""
    m = re.match(r"^Documento(?: obrigatório)?\s+(.+?)\s+(?:ainda não foi anexado|aguardando conclusão|foi considerado inválido)", str(motivo))
    if m:
        return m.group(1).strip()
    if re.match(r"^Evid[êe]ncia do aceite da carga", str(motivo)):
        return "Evidência do aceite da carga"
    t = str(motivo).split(". Prazo")[0].strip()
    return t if len(t) <= 48 else t[:47] + "…"


def _agrupar_notas(x: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por nota (cliente + controle + NF) a partir das pendências de `x`: COD_CLIENTE, NF, CONTROLE, TIPO
    (BLOQUEANTE/MANUAL), QTD_DOCS (documentos pendentes), PRAZO (o que define a situação: o menor prazo das pendências que
    bloqueiam; na validação manual, das que aguardam validação) e DOCUMENTOS (nomes). Bloqueantes primeiro, depois por prazo."""
    linhas = []
    for (cod, controle, nf), g in x.groupby(["COD_CLIENTE", "CONTROLE", "NF"], dropna=False):
        bloq = int(pd.to_numeric(g["NOTA_BLOQ"], errors="coerce").max()) == 1
        ref = g[pd.to_numeric(g["BLOQUEIA"], errors="coerce") == 1] if bloq else g[pd.to_numeric(g["STATUS"], errors="coerce") == 1]
        nomes = g["DOCUMENTO"] if "DOCUMENTO" in g.columns else g["MOTIVO"].map(_nome_documento)   # nome do tipo de documento (a regra); o texto do motivo só como reserva
        docs = list(dict.fromkeys(str(n) for n in nomes))
        linhas.append({"COD_CLIENTE": cod, "NF": str(nf), "CONTROLE": str(controle), "TIPO": "BLOQUEANTE" if bloq else "MANUAL",
                       "QTD_DOCS": len(g), "PRAZO": pd.to_datetime(ref["PRAZO"], errors="coerce").min(), "DOCUMENTOS": docs})
    out = pd.DataFrame(linhas, columns=["COD_CLIENTE", "NF", "CONTROLE", "TIPO", "QTD_DOCS", "PRAZO", "DOCUMENTOS"])
    if out.empty:
        return out
    out["_ordem"] = (out["TIPO"] != "BLOQUEANTE").astype(int)
    return out.sort_values(["_ordem", "PRAZO", "NF"]).drop(columns="_ordem").reset_index(drop=True)


def notas_pendentes_do_cliente(codigo):
    """Notas do cliente que estão bloqueadas ou em validação manual (ver `_agrupar_notas`). None se o banco não respondeu."""
    from services.data_service import carregar_notas_pendentes_validacao

    df = carregar_notas_pendentes_validacao()
    if df is None:
        return None
    x = df[df["COD_CLIENTE"].astype(str) == str(int(float(codigo)))] if len(df) else df
    return _agrupar_notas(x)


def notas_pendentes_todas():
    """Notas de TODOS os clientes do Mercado Interno que estão bloqueadas ou em validação manual (para o painel Resumo
    Pendências). None se o banco não respondeu."""
    from services.data_service import carregar_notas_pendentes_validacao

    df = carregar_notas_pendentes_validacao()
    return None if df is None else _agrupar_notas(df)


URL_CONTROLE_VENDA = "https://syncprocess.corporativo.demo.com.br/gestao-documental/controle-venda/{numero}/dados/"


def url_controle_venda(controle):
    """Link do controle de venda no SyncProcess: o número é o final do código (CTV-2026-003562 -> 3562). None se não achar."""
    m = re.search(r"(\d+)\s*$", str(controle))
    return URL_CONTROLE_VENDA.format(numero=int(m.group(1))) if m else None


_CSS_NOTAS = ("<style>.pn-box{display:block;container-type:inline-size}"
              "@container (max-width: 300px){.pn-l{display:none}.pn-row{grid-template-columns:64px minmax(0,1fr) 40px 44px !important}}"
              "@container (min-width: 301px){.pn-c{display:none}}</style>")


def html_notas_pendentes(codigo):
    """Painel com uma barra por nota pendente de validação (tamanho = documentos pendentes; vermelho = bloqueante, azul = validação
    manual), com rolagem quando há muitas. Passe o mouse na linha para ver os documentos. None se não há nota pendente ou o banco
    não respondeu (a tela então não mostra o painel)."""
    notas = notas_pendentes_do_cliente(codigo)
    if notas is None or notas.empty:
        return None
    maximo = max(int(notas["QTD_DOCS"].max()), 1)
    cor_topo = "#E24B4A" if (notas["TIPO"] == "BLOQUEANTE").any() else "#378ADD"
    linhas = ""
    for i, r in enumerate(notas.itertuples(index=False)):
        cor = "#E24B4A" if r.TIPO == "BLOQUEANTE" else "#378ADD"
        prazo = (f"<span class='pn-l'>{r.PRAZO.strftime('%d/%m/%Y')}</span><span class='pn-c'>{r.PRAZO.strftime('%d/%m')}</span>"
                 if pd.notna(r.PRAZO) else "—")
        dica = escape(f"{'Bloqueante' if r.TIPO == 'BLOQUEANTE' else 'Validação manual'} · NF {r.NF} · {r.CONTROLE} · " + " · ".join(r.DOCUMENTOS), quote=True)
        linhas += (
            f'<div class="pn-row" title="{dica}" style="display:grid;grid-template-columns:76px minmax(0,1fr) 46px 78px;gap:8px;'
            f'align-items:center;padding:3px 0;font-size:12px">'
            f'<span style="color:#fff;font-weight:500;white-space:nowrap">NF {escape(r.NF)}</span>'
            f'<div style="height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div class="an-wipe" style="animation-delay:{min(i, 14) * 45}ms;width:{r.QTD_DOCS / maximo * 100:.1f}%;height:100%;background:{cor}"></div></div>'
            f'<span style="color:#8892A4;text-align:right;white-space:nowrap">{r.QTD_DOCS} doc.</span>'
            f'<span style="color:#aaaaaa;text-align:right;white-space:nowrap">{prazo}</span></div>'
        )
    legenda = (f"<span style='color:#ff6b6b'>●</span> bloqueante &nbsp;<span style='color:#6db3f5'>●</span> validação manual")
    return (
        f"{_CSS_NOTAS}"
        f'<div style="background:#1e1e2e;border-radius:12px;border-top:4px solid {cor_topo};box-sizing:border-box;padding:16px 18px;'
        f'width:100%;min-height:224px"><div class="pn-box">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
        f'<span style="color:#e0e0e0;font-size:13px;font-weight:600">Notas pendentes de validação</span>'
        f'<span style="font-size:11px;color:#8892A4">{legenda}</span></div>'
        f'<div style="max-height:118px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div>'
        f'<div style="height:1px;background:#2a2a3a;margin:8px 0 6px"></div>'
        f'<span style="color:#8892A4;font-size:11px">{len(notas)} nota(s) · passe o mouse na linha para ver os documentos</span>'
        f'</div></div>'
    )


def fundo_por_cor(cor_borda) -> dict:
    """Fundo do card pela cor da borda: vermelho (#E24B4A) ou verde (#22c55e) pintam o fundo e o rótulo como no card de notas
    pendentes; qualquer outra cor devolve {} (o card fica como era)."""
    cor = str(cor_borda).lower()
    if cor == _VERMELHO[0].lower():
        return {"cor_fundo": _VERMELHO[1], "cor_label": _VERMELHO[2]}
    if cor == _VERDE[0].lower():
        return {"cor_fundo": _VERDE[1], "cor_label": _VERDE[2]}
    return {}
