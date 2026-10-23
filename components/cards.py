"""
components/cards.py
====================
Cards HTML reutilizáveis — Painel Financeiro
Mantém a função original `card()` e os cards animados do Painel de
Saldo Financeiro, e adiciona um padrão único de card com largura/altura
configuráveis (`card_html`) + helper de layout (`render_cards_row`),
usado em todas as telas do painel para manter consistência visual.
"""

import streamlit as st
from datetime import date

# ── Paleta de cores ─────────────────────────────────────────────────────────────
C = {
    "teal":    "#1BADA6",
    "azul":    "#4A7FB5",
    "roxo":    "#7B68B5",
    "laranja": "#E8724A",
    "verde":   "#2ECC71",
    "card":    "#252D3F",
    "cinza":   "#8892A4",
    "borda":   "#323D56",
    "texto":   "#E8EAF0",
}

# Tamanho padrão dos cards em todas as telas do painel.
# Ajuste aqui para mudar globalmente, ou passe largura/altura por chamada.
LARGURA_PADRAO = "240px"
ALTURA_PADRAO  = "104px"


# ── Card original (mantido sem alteração, usado internamente por card_html) ───

def card(label, valor, cor_borda, cor_texto, cor_label, cor_fundo):
    """Retorna um card HTML estilizado para uso com st.markdown."""
    return f"""
    <div style="background:{cor_fundo}; border-left:4px solid {cor_borda};
                border-radius:8px; padding:16px 20px; margin-bottom:8px;">
        <div style="font-size:13px; color:{cor_label}; margin-bottom:4px;">{label}</div>
        <div class="cv" style="font-size:26px; font-weight:600; color:{cor_texto}; white-space:nowrap;">{valor}</div>
    </div>
    """


# ── Padrão único de card (largura/altura fixas, subtítulo opcional) ───────────

def tamanho_auto(texto: str, max_px: int = 26, min_px: int = 14, fator: float = 0.5, reserva: int = 34) -> str:
    """Fonte do valor que cresce até max_px sem quebrar linha: encolhe só se o texto
    não couber na largura do card (usa container query; fallback fixo se o navegador
    não suportar). Passe o retorno em tamanho_valor de card_html."""
    n = max(len(str(texto)), 1)
    fallback = max(min_px, min(max_px, int(200 / (n * fator))))
    return (f"{fallback}px;font-size:min({max_px}px, max({min_px}px, "
            f"calc((100cqw - {reserva}px) / {n * fator:.2f})))")


def card_html(
    label: str,
    valor,
    subtitulo: str = "",
    cor_borda: str = "#6366f1",
    cor_fundo: str = "#1e1e2e",
    cor_texto: str = "#ffffff",
    cor_label: str = "#aaaaaa",
    largura: str = LARGURA_PADRAO,
    altura: str = ALTURA_PADRAO,
    truncar_label: bool = False,
    tamanho_valor: str = "",
    padding: str = "",
    alinhar: str = "",
    topo: bool = False,
) -> str:
    """
    Retorna o HTML de UM card (não renderiza) — use com render_cards_row()
    para montar uma linha de vários cards lado a lado, ou com st.markdown()
    para um card isolado.

    Parâmetros
    ----------
    label         : título do card (pode incluir emoji, ex: "Erros")
    valor         : valor grande exibido (número, texto, %, etc.)
    subtitulo     : linha secundária pequena abaixo do título (opcional)
    cor_borda     : cor da borda lateral esquerda
    largura       : largura fixa do card (padrão: LARGURA_PADRAO)
    altura        : altura mínima fixa do card (padrão: ALTURA_PADRAO)
    tamanho_valor : tamanho da fonte do valor (ex.: "22px"); vazio mantém o padrão (26px)
    padding       : espaçamento interno do card (ex.: "12px 20px"); vazio mantém o padrão (16px 20px)
    truncar_label : se True, o título fica em uma linha só, cortando com
                    "..." se for muito longo (útil para nomes de categoria
                    longos). Não deve ser usado junto com subtitulo.
    """
    label_html = label
    if truncar_label:
        label_html = (
            f'<span style="white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis;display:block;">{label}</span>'
        )

    sub = f"<br><span style='font-size:12px;color:{cor_label}'>{subtitulo}</span>" if subtitulo else ""
    html = card(
        label=f"{label_html}{sub}", valor=valor,
        cor_borda=cor_borda, cor_texto=cor_texto,
        cor_label=cor_label, cor_fundo=cor_fundo,
    )

    if tamanho_valor:
        html = html.replace("font-size:26px;", f"font-size:{tamanho_valor};", 1)
    if padding:
        html = html.replace("padding:16px 20px;", f"padding:{padding};", 1)

    if altura:
        # O fundo colorido é do card interno: ele precisa esticar até a altura da caixa
        # externa, senão cards com menos conteúdo ficam mais baixos que os vizinhos.
        html = html.replace(
            "margin-bottom:8px;\">",
            "margin-bottom:0; flex:1; display:flex; flex-direction:column; justify-content:center; box-sizing:border-box;\">",
            1,
        )

    if alinhar:
        html = html.replace("border-radius:8px;", f"border-radius:8px;text-align:{alinhar};", 1)

    if topo:
        # conteúdo colado ao topo: títulos de cards vizinhos ficam na mesma altura
        # mesmo quando o valor tem fonte/linhas diferentes.
        html = html.replace("justify-content:center;", "justify-content:flex-start;")
        # entrelinha justa: valor em 2 linhas (26px) cabe na mesma altura dos vizinhos
        html = html.replace("white-space:nowrap;\">", "white-space:nowrap; line-height:1.2;\">")

    estilo_extra = f"width:{largura};max-width:{largura};"
    if "cqw" in tamanho_valor:
        estilo_extra += "container-type:inline-size;"
    if altura:
        estilo_extra += (
            f"min-height:{altura};box-sizing:border-box;"
            f"display:flex;flex-direction:column;justify-content:{'flex-start' if topo else 'center'};overflow:hidden;"
        )
    return f'<div style="{estilo_extra}">{html}</div>'


def render_cards_row(cards: list, gap: str = "12px", distribuir_igual: bool = False) -> None:
    """
    Renderiza uma lista de HTMLs de card (gerados por card_html) lado a lado.

    distribuir_igual=True: usa CSS grid — todos os cards ficam exatamente do
    mesmo tamanho, dividindo o espaço disponível em partes iguais.
    distribuir_igual=False (padrão): flex-wrap, largura fixa por card.
    """
    conteudo = "".join(cards)
    if distribuir_igual:
        n = len(cards) or 1
        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat({n},1fr);'
            f'gap:{gap};align-items:stretch;">' + conteudo + '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div style="display:flex;gap:{gap};flex-wrap:wrap;">' + conteudo + '</div>',
            unsafe_allow_html=True
        )


def render_ranking_barras(
    itens: list,
    cor: str = "#E8724A",
    altura_barra: str = "12px",
    total_para_pct=None,
) -> None:
    """
    Renderiza um ranking de barras horizontais simples, em HTML puro.

    itens: lista de (rótulo, valor_numérico, texto_já_formatado), maior primeiro
           ou não — a barra é proporcional ao maior valor da lista, na ordem
           dada (não reordena).
    total_para_pct: quando fornecido, exibe uma coluna de % (valor/total) entre
                    o rótulo e a barra, na cor da barra.
    """
    if not itens:
        return
    maximo = max((v for _, v, _ in itens), default=0) or 1
    html = ""
    for rotulo, valor, texto in itens:
        pct_barra = valor / maximo * 100 if maximo else 0
        if total_para_pct:
            pct_val = valor / total_para_pct * 100
            html += (
                '<div style="display:grid;grid-template-columns:200px 42px 220px 110px;gap:8px;'
                'align-items:center;font-size:13px;padding:3px 0">'
                f'<div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e0e0e0;">{rotulo}</div>'
                f'<div style="text-align:right;color:{cor};font-size:11px;font-weight:600;white-space:nowrap">{pct_val:.2f}%</div>'
                f'<div style="height:{altura_barra};border-radius:3px;overflow:hidden;background:rgba(128,128,128,0.15)">'
                f'<div style="width:{pct_barra:.1f}%;height:100%;background:{cor}"></div></div>'
                f'<div style="text-align:right;color:#e0e0e0;">{texto}</div></div>'
            )
        else:
            html += (
                '<div style="display:grid;grid-template-columns:260px 280px 110px 1fr;gap:8px;'
                'align-items:center;font-size:13px;padding:3px 0">'
                f'<div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e0e0e0;">{rotulo}</div>'
                f'<div style="height:{altura_barra};border-radius:3px;overflow:hidden;background:rgba(128,128,128,0.15)">'
                f'<div style="width:{pct_barra:.1f}%;height:100%;background:{cor}"></div></div>'
                f'<div style="text-align:right;color:#e0e0e0;">{texto}</div></div>'
            )
    st.markdown(html, unsafe_allow_html=True)


def render_card(label, valor, subtitulo="", cor_borda="#6366f1",
                 cor_fundo="#1e1e2e", cor_texto="#ffffff", cor_label="#aaaaaa",
                 largura=LARGURA_PADRAO, altura=ALTURA_PADRAO, truncar_label=False):
    """Renderiza um único card isolado (atalho para card_html + st.markdown)."""
    st.markdown(
        card_html(label, valor, subtitulo, cor_borda, cor_fundo, cor_texto,
                  cor_label, largura, altura, truncar_label),
        unsafe_allow_html=True
    )


# ── Cards do Painel de Saldo (HTML animado) ───────────────────────────────────

def card_saldo(
    titulo: str,
    valor: str,
    cor: str = C["teal"],
    subtitulo: str = "",
    icone: str = "",
    delay: float = 0.0,
    valor_cor: str = "",
) -> str:
    """
    Card principal com borda superior colorida e animação fadeUp.

    Parâmetros
    ----------
    titulo    : rótulo do card
    valor     : valor formatado (ex: "R$ 68.511.460,75")
    cor       : cor da borda superior e do glow
    subtitulo : linha secundária abaixo do valor
    icone     : emoji opcional no label
    delay     : delay da animação em segundos (escalonamento visual)
    valor_cor : cor do texto do valor (padrão = var(--texto))
    """
    icone_html = f'<span style="margin-right:5px;">{icone}</span>' if icone else ""
    sub_html   = (
        f'<div style="font-size:.7rem;color:{C["cinza"]};margin-top:5px;">{subtitulo}</div>'
        if subtitulo else ""
    )
    vc = f"color:{valor_cor};" if valor_cor else ""

    return f"""
    <div style="
        background:{C['card']};
        border:1px solid {C['borda']};
        border-top:3px solid {cor};
        border-radius:12px;
        padding:16px 18px;
        position:relative;
        overflow:hidden;
        transition:transform .15s, box-shadow .15s;
        height:100%;
    "
    onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 24px rgba(0,0,0,.35)'"
    onmouseout="this.style.transform='';this.style.boxShadow=''">
        <div style="
            position:absolute;top:-40px;right:-40px;
            width:110px;height:110px;border-radius:50%;
            background:{cor};opacity:.06;pointer-events:none;">
        </div>
        <div style="font-size:.68rem;font-weight:600;color:{C['cinza']};
                    text-transform:uppercase;letter-spacing:.09em;margin-bottom:8px;">
            {icone_html}{titulo}
        </div>
        <div style="font-size:1.3rem;font-weight:700;{vc}color:{C['texto']};
                    opacity:0;transform:translateY(6px);
                    animation:fadeUp .5s ease forwards {delay}s;">
            {valor}
        </div>
        {sub_html}
    </div>
    <style>
    @keyframes fadeUp {{
        to {{ opacity:1; transform:translateY(0); }}
    }}
    </style>
    """


def card_indicador(
    titulo: str,
    valor: str,
    cor: str = C["teal"],
    subtitulo: str = "",
    icone: str = "",
    delay: float = 0.0,
    largura: str = "100%",
) -> str:
    """
    Card com borda lateral colorida (estilo "Inadimplência"):
    ícone + título no topo, subtítulo logo abaixo, e valor grande
    já na cor do indicador.

    Parâmetros
    ----------
    titulo    : rótulo do card
    valor     : valor formatado (ex: "3.3%", "42")
    cor       : cor da borda lateral e do valor
    subtitulo : linha secundária entre o título e o valor
    icone     : emoji opcional antes do título
    delay     : delay da animação em segundos (escalonamento visual)
    largura   : largura fixa do card (ex: "280px"). Padrão "100%"
                preenche a coluna do Streamlit normalmente.
    """
    icone_html = f'<span style="margin-right:6px;">{icone}</span>' if icone else ""
    sub_html   = (
        f'<div style="font-size:.72rem;color:{C["cinza"]};margin-top:2px;margin-bottom:10px;">{subtitulo}</div>'
        if subtitulo else ""
    )

    return f"""
    <div style="
        background:{C['card']};
        border:1px solid {C['borda']};
        border-left:3px solid {cor};
        border-radius:12px;
        padding:16px 18px;
        width:{largura};
        max-width:{largura};
        height:100%;
        transition:transform .15s, box-shadow .15s;
    "
    onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 24px rgba(0,0,0,.35)'"
    onmouseout="this.style.transform='';this.style.boxShadow=''">
        <div style="font-size:.75rem;font-weight:600;color:{C['cinza']};margin-bottom:2px;">
            {icone_html}{titulo}
        </div>
        {sub_html}
        <div style="font-size:1.5rem;font-weight:700;color:{cor};
                    opacity:0;transform:translateY(6px);
                    animation:fadeUp .5s ease forwards {delay}s;">
            {valor}
        </div>
    </div>
    <style>
    @keyframes fadeUp {{
        to {{ opacity:1; transform:translateY(0); }}
    }}
    </style>
    """


def card_status(
    titulo: str,
    status: str,
    positivo: bool,
    detalhe: str = "",
    delay: float = 0.0,
) -> str:
    """Card de status com dot pulsante verde/laranja."""
    cor      = C["verde"] if positivo else C["laranja"]
    dot_anim = "pulse-verde" if positivo else "pulse-laranja"
    det_html = (
        f'<div style="font-size:.7rem;color:{C["cinza"]};margin-top:4px;">{detalhe}</div>'
        if detalhe else ""
    )

    return f"""
    <div style="
        background:{C['card']};
        border:1px solid {C['borda']};
        border-top:3px solid {cor};
        border-radius:12px;
        padding:16px 18px;
        height:100%;
        transition:transform .15s, box-shadow .15s;
    "
    onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 24px rgba(0,0,0,.35)'"
    onmouseout="this.style.transform='';this.style.boxShadow=''">
        <div style="font-size:.68rem;font-weight:600;color:{C['cinza']};
                    text-transform:uppercase;letter-spacing:.09em;margin-bottom:8px;">
            {titulo}
        </div>
        <div style="display:flex;align-items:center;gap:8px;
                    font-size:1rem;font-weight:700;color:{cor};
                    opacity:0;transform:translateY(6px);
                    animation:fadeUp .5s ease forwards {delay}s;">
            <span class="{dot_anim}" style="
                width:9px;height:9px;border-radius:50%;
                background:{cor};display:inline-block;"></span>
            {status}
        </div>
        {det_html}
    </div>
    <style>
    @keyframes pulse-verde {{
        0%   {{ box-shadow:0 0 0 0 rgba(46,204,113,.4); }}
        70%  {{ box-shadow:0 0 0 7px rgba(46,204,113,0); }}
        100% {{ box-shadow:0 0 0 0 rgba(46,204,113,0); }}
    }}
    @keyframes pulse-laranja {{
        0%   {{ box-shadow:0 0 0 0 rgba(232,114,74,.4); }}
        70%  {{ box-shadow:0 0 0 7px rgba(232,114,74,0); }}
        100% {{ box-shadow:0 0 0 0 rgba(232,114,74,0); }}
    }}
    .pulse-verde   {{ animation:pulse-verde 2s infinite; }}
    .pulse-laranja {{ animation:pulse-laranja 2s infinite; }}
    </style>
    """


def card_pct(
    titulo: str,
    valor_pct: float,
    cor: str = C["teal"],
    detalhe: str = "",
    delay: float = 0.0,
) -> str:
    """Card com percentual e barra de progresso animada."""
    largura  = min(max(valor_pct, 0), 100)
    det_html = (
        f'<div style="font-size:.7rem;color:{C["cinza"]};margin-top:4px;">{detalhe}</div>'
        if detalhe else ""
    )
    bar_id = f"bar_{titulo.replace(' ','_').lower()}"

    return f"""
    <div style="
        background:{C['card']};
        border:1px solid {C['borda']};
        border-top:3px solid {cor};
        border-radius:12px;
        padding:16px 18px;
        height:100%;
        transition:transform .15s, box-shadow .15s;
    "
    onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 24px rgba(0,0,0,.35)'"
    onmouseout="this.style.transform='';this.style.boxShadow=''">
        <div style="font-size:.68rem;font-weight:600;color:{C['cinza']};
                    text-transform:uppercase;letter-spacing:.09em;margin-bottom:8px;">
            {titulo}
        </div>
        <div style="font-size:1.3rem;font-weight:700;color:{C['texto']};
                    opacity:0;transform:translateY(6px);
                    animation:fadeUp .5s ease forwards {delay}s;">
            {valor_pct:.2f}%
        </div>
        <div style="background:{C['borda']};border-radius:4px;height:5px;
                    margin-top:10px;overflow:hidden;">
            <div id="{bar_id}" style="height:100%;border-radius:4px;
                 background:{cor};width:0;
                 transition:width 1s cubic-bezier(.4,0,.2,1);"></div>
        </div>
        {det_html}
    </div>
    <script>
    setTimeout(function(){{
        var b = document.getElementById('{bar_id}');
        if(b) b.style.width = '{largura:.1f}%';
    }}, 400);
    </script>
    """


# ── Tabela HTML estilizada ────────────────────────────────────────────────────

import pandas as _pd
import streamlit as _st

_DIAS_COR = [
    (10,  "rgba(34,197,94,0.15)",  "#22c55e"),
    (30,  "rgba(245,158,11,0.15)", "#f59e0b"),
    (60,  "rgba(251,146,60,0.15)", "#fb923c"),
    (999, "rgba(226,75,74,0.15)",  "#E24B4A"),
]

_COMP_DESTAQUE = {"PROTESTADO", "PROTESTO"}

_CSS_TABELA = """
<style>
.ibc-tbl-wrap{overflow-x:auto;border-radius:8px;background:#1e1e2e}
.ibc-tbl{width:100%;border-collapse:collapse;font-size:13px}
.ibc-tbl th{color:#8892A4;font-weight:500;font-size:11px;padding:7px 10px;
            text-align:left;border-bottom:1px solid #2a2a3a;white-space:nowrap;
            position:sticky;top:0;background:#1e1e2e;z-index:1}
.ibc-tbl td{padding:6px 10px;border-bottom:1px solid #23233a;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:240px}
.ibc-tbl tr:last-child td{border-bottom:none}
.ibc-tbl tr:hover td{background:#1a1a2e}
.ibc-badge{display:inline-block;font-size:11px;font-weight:600;border-radius:4px;
           padding:2px 8px;white-space:nowrap}
</style>
"""

def _cor_por_dias(dias_val):
    """Retorna (bg, cor) baseado na quantidade de dias — mesma lógica do badge de atraso."""
    try:
        d = int(float(str(dias_val).replace(" dias", "").strip()))
    except Exception:
        return None, None
    for limite, bg, cor in _DIAS_COR:
        if d <= limite:
            return bg, cor
    return "rgba(226,75,74,0.15)", "#E24B4A"

def _badge_dias(dias_val) -> str:
    bg, cor = _cor_por_dias(dias_val)
    if bg is None:
        return f'<span style="color:#8892A4;font-size:12px">{dias_val}</span>'
    try:
        d = int(float(str(dias_val).replace(" dias", "").strip()))
    except Exception:
        d = dias_val
    return f'<span class="ibc-badge" style="background:{bg};color:{cor}">{d} dias</span>'

def _badge_complemento(val, dias_val=None) -> str:
    v = str(val).strip()
    if not v or v in ("-", "nan", "None"):
        return '<span style="color:#8892A4;font-size:12px">—</span>'
    if dias_val is not None:
        bg, cor = _cor_por_dias(dias_val)
        if bg:
            return f'<span class="ibc-badge" style="background:{bg};color:{cor}">{v}</span>'
    return f'<span class="ibc-badge" style="background:rgba(99,102,241,0.15);color:#818cf8">{v}</span>'

def _badge_situacao(val) -> str:
    v = str(val).strip()
    mapa = {
        "VENCIDO":  ("rgba(226,75,74,0.15)",   "#E24B4A"),
        "A VENCER": ("rgba(34,197,94,0.15)",    "#22c55e"),
        "PAGO":     ("rgba(99,102,241,0.15)",   "#818cf8"),
    }
    bg, cor = mapa.get(v.upper(), ("rgba(128,128,128,0.15)", "#8892A4"))
    return f'<span class="ibc-badge" style="background:{bg};color:{cor}">{v}</span>'


def _texto_celula(val) -> str:
    """Texto seguro para célula HTML: vazio para nulos e <br> no lugar de quebras de linha.
    Quebra de linha dentro do HTML faz o markdown do Streamlit encerrar o bloco e mostrar as tags como texto."""
    if val is None or (isinstance(val, float) and _pd.isna(val)):
        return ""
    return str(val).replace("\r\n", "\n").replace("\n", "<br>")


def render_tabela_html(
    df: "_pd.DataFrame",
    colunas_renomear: dict | None = None,
    colunas_moeda: list | None = None,
    coluna_dias: str | None = None,
    coluna_complemento: str | None = None,
    coluna_situacao: str | None = None,
    colunas_cinza: list | None = None,
    colunas_valor_destaque: list | None = None,
    colunas_centralizar: list | None = None,
    altura: int = 420,
) -> None:
    """Renderiza um DataFrame como tabela HTML estilizada via st.markdown."""
    if df is None or df.empty:
        _st.info("Sem dados para exibir.")
        return

    df = df.copy()
    renomear  = colunas_renomear or {}
    moeda     = set(colunas_moeda or [])
    cinza     = set(colunas_cinza or [])
    destaque  = set(colunas_valor_destaque or [])
    centraliz = set(colunas_centralizar or [])

    cabecalho = "".join(
        f'<th style="text-align:center">{renomear.get(c, c)}</th>'
        if c in centraliz else
        f'<th>{renomear.get(c, c)}</th>'
        for c in df.columns
    )

    linhas_html = ""
    for _, row in df.iterrows():
        celulas = ""
        _dias_row = row[coluna_dias] if coluna_dias and coluna_dias in df.columns else None
        for col in df.columns:
            val = row[col]
            centro = ' style="text-align:center"' if col in centraliz else ""
            if col == coluna_dias:
                celulas += f"<td{centro}>{_badge_dias(val)}</td>"
            elif col == coluna_complemento:
                celulas += f"<td{centro}>{_badge_complemento(val, _dias_row)}</td>"
            elif col == coluna_situacao:
                celulas += f"<td{centro}>{_badge_situacao(val)}</td>"
            elif col in destaque:
                celulas += f'<td style="color:#E24B4A;font-weight:600;{"text-align:center;" if col in centraliz else ""}">{_texto_celula(val)}</td>'
            elif col in cinza:
                celulas += f'<td style="color:#8892A4;font-size:12px;{"text-align:center;" if col in centraliz else ""}">{_texto_celula(val)}</td>'
            elif col in moeda:
                celulas += f'<td style="color:#ffffff;font-weight:500">{_texto_celula(val)}</td>'
            else:
                celulas += f"<td{centro}>{_texto_celula(val)}</td>"
        linhas_html += f"<tr>{celulas}</tr>"

    html = (
        _CSS_TABELA
        + f'<div class="ibc-tbl-wrap" style="max-height:{altura}px;overflow-y:auto">'
        + '<table class="ibc-tbl">'
        + f"<thead><tr>{cabecalho}</tr></thead>"
        + f"<tbody>{linhas_html}</tbody>"
        + "</table></div>"
    )
    # "$" no texto (R$ ...) faz o markdown do Streamlit tratar o trecho entre dois "$" como fórmula (LaTeX)
    # e o HTML da tabela vaza na tela; escapa para a entidade HTML.
    html = html.replace("$", "&#36;")
    _st.markdown(html, unsafe_allow_html=True)


def situacao_faturamento(df, hoje=None) -> tuple:
    """Card Situação Faturamento: (valor, subtitulo, cor_borda).
    Bloqueado quando algum título em aberto tem data prorrogada anterior a hoje.
    O valor mostra "Faturamento" e o estado em duas linhas, com inicial maiúscula."""
    hoje = _pd.Timestamp(hoje or date.today()).normalize()
    if df is None or df.empty or "PRORROGADO" not in df.columns or "SALDO_EM_ABERTO" not in df.columns:
        return ("Faturamento<br>Liberado", "", "#22c55e")
    abertos = df[_pd.to_numeric(df["SALDO_EM_ABERTO"], errors="coerce").fillna(0) > 0]
    prorrogados = _pd.to_datetime(abertos["PRORROGADO"], errors="coerce").dropna()
    atrasados = prorrogados[prorrogados < hoje]
    if atrasados.empty:
        return ("Faturamento<br>Liberado", "", "#22c55e")
    mais_antigo = atrasados.min()
    dias = (hoje - mais_antigo).days
    return ("Faturamento<br>Bloqueado", "", "#E24B4A")
