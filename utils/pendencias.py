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
from urllib.parse import quote_plus

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


_ABERTOS = (0, 1, 2, 6)   # status de pendência ainda aberta (3 = regularizada: documento em ordem)
_GRAVIDADE = {"VENCIDO": 4, "VALIDANDO": 3, "NAO_ANEXADO": 2, "PENDENTE": 1, "OK": 0}
# nomes iguais aos da Gestão documental do SyncProcess: Pendente (sem documento), Em validação, Inválido (prazo vencido, bloqueio ativo) e Válido
ESTADO_ROTULO = {"VENCIDO": "Inválido", "VALIDANDO": "Em validação", "NAO_ANEXADO": "Pendente", "PENDENTE": "Pendente", "OK": "Válido"}
# documentos que aparecem como coluna (os que bloqueiam e o Pedido de venda, que aparece Válido), nesta ordem: (código no SyncProcess, nome na coluna larga, sigla na coluna estreita)
_DOCS_ORDEM = [("CNH", "CNH do motorista", "CNH"), ("NFCANHOTO", "NF com canhoto", "NF"), ("CARTATEMP", "Carta de temperatura", "Cart."),
               ("PEDVENDA", "Pedido de venda", "PV"), ("ACEITEPED", "Aceite do pedido", "Ac."), ("PEDCOMPRA", "Pedido de compra", "Ped.")]


def _estado_documento(status, bloqueia) -> str:
    """Estado de um documento pela pendência dele: vencido (bloqueia), validando (revisão), não anexado, pendente ou OK."""
    st = pd.to_numeric(status, errors="coerce")
    st = int(st) if pd.notna(st) else -1
    if st in _ABERTOS:
        bl = pd.to_numeric(bloqueia, errors="coerce")
        if pd.notna(bl) and int(bl) == 1:
            return "VENCIDO"
        return {1: "VALIDANDO", 0: "NAO_ANEXADO"}.get(st, "PENDENTE")
    return "OK"


def _agrupar_notas(x: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por nota (cliente + controle + NF) a partir das pendências de `x`: COD_CLIENTE, NF, CONTROLE, TIPO
    (BLOQUEANTE/MANUAL), QTD_DOCS (documentos ainda pendentes), PRAZO (o que define a situação: o menor prazo das pendências
    abertas que bloqueiam; na validação manual, das que aguardam validação), DOCUMENTOS (nomes dos pendentes), ESTADOS
    ({código do documento: estado}) e NOMES ({código: nome}). Bloqueantes primeiro, depois por prazo."""
    linhas = []
    for (cod, controle, nf), g in x.groupby(["COD_CLIENTE", "CONTROLE", "NF"], dropna=False):
        bloq = int(pd.to_numeric(g["NOTA_BLOQ"], errors="coerce").max()) == 1
        st_g = pd.to_numeric(g["STATUS"], errors="coerce")
        abertas = g[st_g.isin(_ABERTOS)]
        if bloq:
            ref = abertas[pd.to_numeric(abertas["BLOQUEIA"], errors="coerce") == 1]
        else:
            ref = abertas[pd.to_numeric(abertas["STATUS"], errors="coerce") == 1]
        # nome do tipo de documento (a regra); o texto do motivo só como reserva
        nomes_g = g["DOCUMENTO"] if "DOCUMENTO" in g.columns else g["MOTIVO"].map(_nome_documento)
        codigos_g = g["DOC_CODIGO"] if "DOC_CODIGO" in g.columns else nomes_g
        estados, nomes = {}, {}
        for c, n, s_, bl in zip(codigos_g, nomes_g, g["STATUS"], g["BLOQUEIA"]):
            c, e_ = str(c), _estado_documento(s_, bl)
            nomes[c] = str(n)
            if _GRAVIDADE[e_] >= _GRAVIDADE.get(estados.get(c), -1):
                estados[c] = e_
        docs = list(dict.fromkeys(str(n) for n in nomes_g[st_g.isin(_ABERTOS)]))
        linhas.append({"COD_CLIENTE": cod, "NF": str(nf), "CONTROLE": str(controle), "TIPO": "BLOQUEANTE" if bloq else "MANUAL",
                       "QTD_DOCS": len(abertas), "PRAZO": pd.to_datetime(ref["PRAZO"], errors="coerce").min(), "DOCUMENTOS": docs,
                       "ESTADOS": estados, "NOMES": nomes})
    cols = ["COD_CLIENTE", "NF", "CONTROLE", "TIPO", "QTD_DOCS", "PRAZO", "DOCUMENTOS", "ESTADOS", "NOMES"]
    out = pd.DataFrame(linhas, columns=cols)
    if out.empty:
        return out
    out["_ordem"] = (out["TIPO"] != "BLOQUEANTE").astype(int)
    return out.sort_values(["_ordem", "PRAZO", "NF"]).drop(columns="_ordem").reset_index(drop=True)


def colunas_documentos(notas) -> list:
    """Colunas do quadro: [(código, nome, sigla)] dos documentos que aparecem em alguma nota, na ordem fixa (CNH, NF com canhoto,
    Carta de temperatura, Aceite do pedido, Pedido de compra) e, depois, qualquer outro documento que passe a bloquear."""
    achados = {}
    for estados, nomes in zip(notas["ESTADOS"], notas["NOMES"]):
        for c in estados:
            achados.setdefault(c, nomes.get(c, c))
    cols = [(c, achados.get(c) or n, sg) for c, n, sg in _DOCS_ORDEM if c in achados]
    conhecidos = {x[0] for x in _DOCS_ORDEM}
    cols += [(c, achados[c], achados[c][:4]) for c in sorted(achados) if c not in conhecidos]
    return cols


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


URL_BUSCA_CONTROLES = "https://syncprocess.corporativo.demo.com.br/gestao-documental/controle-venda/?q={busca}"


def url_busca_controles(nome):
    """Link da lista de controles de venda do SyncProcess já pesquisada pelo nome do cliente (?q=MARIA+VITORIA+TELES+LIMA)."""
    return URL_BUSCA_CONTROLES.format(busca=quote_plus(str(nome).strip()))


def url_controle_venda(controle):
    """Link do controle de venda no SyncProcess: o número é o final do código (CTV-2026-003562 -> 3562). None se não achar."""
    m = re.search(r"(\d+)\s*$", str(controle))
    return URL_CONTROLE_VENDA.format(numero=int(m.group(1))) if m else None


_COR_BOLA = {"VENCIDO": "#E24B4A", "VALIDANDO": "#378ADD", "NAO_ANEXADO": "#9ca3af", "PENDENTE": "#9ca3af", "OK": "#22c55e"}
_CSS_NOTAS = ("<style>.pn-box{display:block;container-type:inline-size}"
              ".pn-d{width:14px;height:14px;border-radius:50%;display:inline-block}"
              ".pn-nd{background:transparent;border:1px dashed #4b5563;box-sizing:border-box}"
              "@container (max-width: 300px){.pn-l{display:none}}@container (min-width: 301px){.pn-c{display:none}}</style>")


def html_notas_pendentes(codigo):
    """Painel com uma linha por nota do cliente e uma bolinha por documento que bloqueia (vermelho = vencido, azul = validando,
    âmbar = não anexado, verde = em ordem, tracejado = a regra não vale para a nota), com rolagem quando há muitas. Passe o mouse
    na bolinha para ver o documento; a NF abre o controle de venda no SyncProcess. None se não há nota pendente ou o banco não
    respondeu (a tela então não mostra o painel)."""
    notas = notas_pendentes_do_cliente(codigo)
    if notas is None or notas.empty:
        return None
    cols = colunas_documentos(notas)
    n = len(cols)
    grade = f"grid-template-columns:70px repeat({n},18px) minmax(0,1fr);gap:7px;align-items:center"
    cab = (f'<div style="display:grid;{grade};font-size:10px;color:#8892A4;padding-bottom:4px;border-bottom:1px solid #2a2a3a">'
           f'<span></span>' + "".join(f'<span title="{escape(nome, quote=True)}">{escape(sg)}</span>' for _, nome, sg in cols)
           + '<span style="text-align:right">Prazo</span></div>')
    cor_topo = "#E24B4A" if (notas["TIPO"] == "BLOQUEANTE").any() else "#378ADD"
    linhas = ""
    for r in notas.itertuples(index=False):
        prazo = (f"<span class='pn-l'>{r.PRAZO.strftime('%d/%m/%Y')}</span><span class='pn-c'>{r.PRAZO.strftime('%d/%m')}</span>"
                 if pd.notna(r.PRAZO) else "—")
        bolas = ""
        for c, nome, _ in cols:
            e_ = r.ESTADOS.get(c)
            if e_ is None:
                bolas += f'<span class="pn-d pn-nd" title="{escape(nome, quote=True)}: não se aplica"></span>'
            else:
                bolas += f'<span class="pn-d" style="background:{_COR_BOLA[e_]}" title="{escape(nome, quote=True)}: {ESTADO_ROTULO[e_]}"></span>'
        url = url_controle_venda(r.CONTROLE)
        if url:
            nf = (f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="color:#fff;font-weight:500;text-decoration:none" '
                  f'title="{escape(str(r.CONTROLE), quote=True)}">NF {escape(r.NF)}</a>')
        else:
            nf = f'<span style="color:#fff;font-weight:500">NF {escape(r.NF)}</span>'
        linhas += (f'<div style="display:grid;{grade};padding:3px 0;font-size:12px">{nf}{bolas}'
                   f'<span style="color:#aaaaaa;text-align:right;white-space:nowrap">{prazo}</span></div>')
    legenda = ("<span style='color:#ff6b6b'>●</span> inválido &nbsp;<span style='color:#6db3f5'>●</span> em validação &nbsp;"
               "<span style='color:#9ca3af'>●</span> pendente &nbsp;<span style='color:#22c55e'>●</span> válido")
    return (
        f"{_CSS_NOTAS}"
        f'<div style="background:#1e1e2e;border-radius:12px;border-top:4px solid {cor_topo};box-sizing:border-box;padding:16px 18px;'
        f'width:100%;min-height:224px"><div class="pn-box">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
        f'<span style="color:#e0e0e0;font-size:13px;font-weight:600">Notas pendentes de validação</span>'
        f'<span style="font-size:11px;color:#8892A4">{legenda}</span></div>{cab}'
        f'<div style="max-height:118px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div>'
        f'<div style="height:1px;background:#2a2a3a;margin:8px 0 6px"></div>'
        f'<span style="color:#8892A4;font-size:11px">{len(notas)} nota(s) · passe o mouse na bolinha para ver o documento</span>'
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
