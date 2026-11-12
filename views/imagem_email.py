"""
utils/imagem_email.py
======================
Gera imagens PNG com fundo branco (bem diferente do tema escuro do painel),
pensadas para anexar/colar em e-mails. Usa Pillow (PIL) puro, sem depender
de screenshot da tela.
"""

import io
import base64
import html as _html
from datetime import datetime
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont


def _carregar_fonte(tamanho: int, negrito: bool = False) -> ImageFont.FreeTypeFont:
    """Tenta carregar uma fonte TrueType comum; cai para a fonte padrão do
    Pillow se nenhuma das opções estiver disponível no servidor."""
    candidatos = (
        ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"]
        if negrito else
        ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]
    )
    for nome in candidatos:
        try:
            return ImageFont.truetype(nome, tamanho)
        except Exception:
            continue
    return ImageFont.load_default()


# Paleta (RGB) — mesma linguagem visual dos cards do painel, mas em tons
# compatíveis com fundo branco (evita cores muito claras/ilegíveis).
_COR_TEXTO   = (17, 24, 39)
_COR_MUTED   = (95, 94, 90)
_COR_FUNDO_CARD = (243, 244, 246)
_COR_BORDA_TAB  = (211, 209, 199)
_COR_LINHA_TAB  = (230, 228, 220)
_COR_VENCIDO    = (162, 45, 45)
_COR_AVISO_FUNDO = (250, 235, 235)

# Peso relativo de cada coluna — "Cliente" precisa de bem mais espaço que
# "Dias", por exemplo. Colunas não listadas aqui usam peso 1.0.
_PESO_COLUNA = {
    "Cliente": 3.0,
    "Banco": 1.6,
    "Situação": 1.4,
    "Valor Total": 1.6,
    "Saldo Total": 1.6,
    "Saldo em Aberto": 1.6,
    "Vencimento": 1.3,
    "NF": 0.9,
    "Dias Vencto.": 0.9,
    "Cód. Agente": 1.0,
    "ESTADO": 0.7,
    "Consumido em PV": 1.5,
    "Consumido em NF": 1.5,
    "Total Consumido": 1.5,
}


def _larguras_colunas(colunas: list, largura_util: float) -> list:
    """Retorna a largura (em px) de cada coluna, proporcional ao peso dela,
    evitando que colunas de texto longo (Cliente) espremam as vizinhas."""
    pesos = [_PESO_COLUNA.get(c, 1.0) for c in colunas]
    soma_pesos = sum(pesos) or 1.0
    return [largura_util * (p / soma_pesos) for p in pesos]


def _truncar_texto(draw: ImageDraw.ImageDraw, texto: str, fonte, largura_max: float) -> str:
    """Corta o texto com '...' no final se ele não couber em largura_max px."""
    if draw.textlength(texto, font=fonte) <= largura_max:
        return texto
    reticencias = "..."
    while texto and draw.textlength(texto + reticencias, font=fonte) > largura_max:
        texto = texto[:-1]
    return texto + reticencias if texto else reticencias


def gerar_imagem_resumo_titulos(
    titulo_principal: str,
    cards_resumo: list,
    df_titulos: pd.DataFrame,
    titulo_tabela: str = "Títulos",
    destacar_vencidos: bool = True,
) -> bytes:
    """
    Gera uma imagem PNG (fundo branco), com:
      - Cabeçalho com título da tela/cliente e data de geração
      - Cards de resumo (4 por linha)
      - Aviso destacado se houver título(s) vencido(s) (opcional)
      - Tabela de títulos, com linhas vencidas em vermelho (se destacar_vencidos)

    Parâmetros
    ----------
    titulo_principal  : texto do cabeçalho (ex: "Situação Cliente — 1969 — ...",
                         ou "Contas a Receber — Títulos Vencidos")
    cards_resumo      : lista de dicts {"label": str, "valor": str, "cor": (r,g,b)}
    df_titulos        : DataFrame já formatado para exibição, com colunas
                         "NF", "Vencimento", "Saldo em Aberto", "Situação", "Banco"
                         (mesmos nomes já usados nas tabelas das telas)
    titulo_tabela     : rótulo acima da tabela (ex: "Títulos em Aberto", "Títulos Vencidos")
    destacar_vencidos : se True, mostra o aviso e pinta linhas VENCIDO de vermelho

    Retorna
    -------
    bytes do PNG gerado, prontos para st.download_button.
    """
    LARGURA = 1100
    MARGEM = 24
    CARDS_POR_LINHA = 4
    GAP_CARD = 10
    ALTURA_CARD = 56

    fonte_titulo   = _carregar_fonte(18, negrito=True)
    fonte_sub      = _carregar_fonte(11)
    fonte_label    = _carregar_fonte(11)
    fonte_valor    = _carregar_fonte(14, negrito=True)
    fonte_aviso    = _carregar_fonte(12, negrito=True)
    fonte_tab_head = _carregar_fonte(11, negrito=True)
    fonte_tab_cel  = _carregar_fonte(11)

    # ── Colunas da tabela ────────────────────────────────────────────────────
    colunas = [c for c in ["Cliente", "NF", "Valor Total", "Saldo Total", "Saldo em Aberto", "Vencimento", "Dias Vencto.", "Situação", "Banco",
                            "Cód. Agente", "ESTADO", "Consumido em PV", "Consumido em NF", "Total Consumido"]
               if c in df_titulos.columns]
    n_linhas_tab = len(df_titulos)

    tem_vencido = destacar_vencidos and "Situação" in df_titulos.columns \
        and (df_titulos["Situação"] == "VENCIDO").any()
    qtd_vencidos = int((df_titulos["Situação"] == "VENCIDO").sum()) if tem_vencido else 0

    # ── Cálculo de altura total da imagem ──────────────────────────────────
    n_cards = len(cards_resumo)
    linhas_cards = -(-n_cards // CARDS_POR_LINHA)  # arredonda pra cima
    altura_bloco_cards = linhas_cards * (ALTURA_CARD + GAP_CARD)

    altura_aviso = 34 if tem_vencido else 0
    altura_tab_head = 28
    altura_linha_tab = 22
    altura_tabela = altura_tab_head + n_linhas_tab * altura_linha_tab

    altura_total = int(
        MARGEM + 30 + 20 + 16          # cabeçalho + linha divisória
        + altura_bloco_cards + 16
        + altura_aviso
        + 22 + altura_tabela           # título da seção + tabela
        + MARGEM
    )

    img = Image.new("RGB", (LARGURA, max(altura_total, 300)), "white")
    draw = ImageDraw.Draw(img)

    y = MARGEM

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    draw.text((MARGEM, y), titulo_principal, font=fonte_titulo, fill=_COR_TEXTO)
    y += 26
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    draw.text((MARGEM, y), f"Gerado em {agora}", font=fonte_sub, fill=_COR_MUTED)
    y += 20
    draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=(12, 68, 123), width=2)
    y += 16

    # ── Cards de resumo ──────────────────────────────────────────────────────
    largura_util = LARGURA - 2 * MARGEM
    largura_card = (largura_util - GAP_CARD * (CARDS_POR_LINHA - 1)) / CARDS_POR_LINHA

    for i, card in enumerate(cards_resumo):
        col = i % CARDS_POR_LINHA
        linha = i // CARDS_POR_LINHA
        x0 = MARGEM + col * (largura_card + GAP_CARD)
        y0 = y + linha * (ALTURA_CARD + GAP_CARD)
        x1 = x0 + largura_card
        y1 = y0 + ALTURA_CARD

        draw.rectangle([x0, y0, x1, y1], fill=_COR_FUNDO_CARD)
        draw.rectangle([x0, y0, x0 + 4, y1], fill=card["cor"])
        draw.text((x0 + 12, y0 + 8), card["label"], font=fonte_label, fill=_COR_MUTED)
        draw.text((x0 + 12, y0 + 26), card["valor"], font=fonte_valor, fill=_COR_TEXTO)

    y += altura_bloco_cards + 16

    # ── Aviso de títulos vencidos ────────────────────────────────────────────
    if tem_vencido:
        draw.rectangle([MARGEM, y, LARGURA - MARGEM, y + 26], fill=_COR_AVISO_FUNDO)
        draw.text(
            (MARGEM + 10, y + 6),
            f"Atenção: {qtd_vencidos} título(s) vencido(s) nesta lista.",
            font=fonte_aviso, fill=_COR_VENCIDO,
        )
        y += 34

    # ── Tabela de títulos ────────────────────────────────────────────────────
    draw.text((MARGEM, y), titulo_tabela, font=fonte_tab_head, fill=_COR_TEXTO)
    y += 22

    if colunas:
        larguras_col = _larguras_colunas(colunas, largura_util)
        posicoes_col = [MARGEM]
        for w in larguras_col[:-1]:
            posicoes_col.append(posicoes_col[-1] + w)

        draw.rectangle([MARGEM, y, LARGURA - MARGEM, y + altura_tab_head],
                       outline=_COR_BORDA_TAB, fill=_COR_FUNDO_CARD)
        for i, col in enumerate(colunas):
            texto_col = _truncar_texto(draw, col, fonte_tab_head, larguras_col[i] - 12)
            draw.text((posicoes_col[i] + 6, y + 7), texto_col, font=fonte_tab_head, fill=_COR_MUTED)
        y += altura_tab_head

        for _, row in df_titulos.iterrows():
            situacao = str(row.get("Situação", "-"))
            cor_linha = _COR_VENCIDO if (destacar_vencidos and situacao.upper() == "VENCIDO") else _COR_TEXTO
            for i, col in enumerate(colunas):
                valor = str(row.get(col, "-"))
                valor = _truncar_texto(draw, valor, fonte_tab_cel, larguras_col[i] - 12)
                draw.text((posicoes_col[i] + 6, y + 4), valor, font=fonte_tab_cel, fill=cor_linha)
            y += altura_linha_tab
            draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=_COR_LINHA_TAB, width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def gerar_imagem_situacao_cliente(
    codigo_agente: str,
    cliente: str,
    cards_resumo: list,
    df_titulos: pd.DataFrame,
) -> bytes:
    """Atalho mantido por compatibilidade — usa a função genérica acima."""
    return gerar_imagem_resumo_titulos(
        titulo_principal=f"Situação Cliente — {codigo_agente} — {cliente}",
        cards_resumo=cards_resumo,
        df_titulos=df_titulos,
        titulo_tabela="Títulos em Aberto",
        destacar_vencidos=True,
    )


# ── Texto copiável (para colar direto no corpo do e-mail) ─────────────────────

def gerar_texto_resumo_titulos(
    titulo_principal: str,
    cards_resumo: list,
    df_titulos: pd.DataFrame,
    titulo_tabela: str = "Títulos",
) -> str:
    """Monta uma versão em texto simples (não-imagem) do mesmo resumo,
    pronta para colar no corpo de um e-mail. Colunas separadas por ' | '."""
    linhas = [titulo_principal, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", ""]

    for card in cards_resumo:
        linhas.append(f"{card['label']}: {card['valor']}")
    linhas.append("")

    linhas.append(titulo_tabela)
    if not df_titulos.empty:
        colunas = list(df_titulos.columns)
        linhas.append(" | ".join(colunas))
        for _, row in df_titulos.iterrows():
            linhas.append(" | ".join(str(row.get(c, "-")) for c in colunas))
    else:
        linhas.append("(nenhum registro)")

    return "\n".join(linhas)


def render_botao_copiar_imagem(imagem_bytes: bytes, label: str = "📋 Copiar Imagem", key: str = "copiar_img") -> None:
    """Renderiza um botão que copia a imagem PNG (bytes) direto para a
    área de transferência do usuário, usando a Clipboard API do navegador
    (navigator.clipboard.write com ClipboardItem). Assim é só colar
    (Ctrl+V) direto no corpo de um e-mail ou editor de imagem.

    Requer navegador moderno com suporte a ClipboardItem (Chrome/Edge/
    Firefox recentes) e clique do usuário (exigido pela API).
    """
    imagem_b64 = base64.b64encode(imagem_bytes).decode("ascii")
    st.iframe(f"""
    <div style="font-family:'Source Sans Pro',sans-serif;">
        <button id="btn_{key}" style="
            width:100%; padding:8px 12px; border-radius:8px;
            border:1px solid #3a3a3a; background:#1c1c1c; color:#e0e0e0;
            cursor:pointer; font-size:14px; box-sizing:border-box;">
            {label}
        </button>
        <div id="msg_{key}" style="margin-top:4px; font-size:12px; min-height:16px;"></div>
    </div>
    <script>
        document.getElementById('btn_{key}').addEventListener('click', async function() {{
            var msg = document.getElementById('msg_{key}');
            try {{
                var res = await fetch('data:image/png;base64,{imagem_b64}');
                var blob = await res.blob();
                await navigator.clipboard.write([
                    new ClipboardItem({{ 'image/png': blob }})
                ]);
                msg.style.color = '#22c55e';
                msg.innerText = 'Imagem copiada!';
            }} catch (err) {{
                msg.style.color = '#E24B4A';
                msg.innerText = 'Não foi possível copiar (navegador sem suporte).';
            }}
            setTimeout(function() {{ msg.innerText = ''; }}, 3000);
        }});
    </script>
    """, height=70)
