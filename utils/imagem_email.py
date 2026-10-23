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
import math
from datetime import datetime
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont



# Fator de qualidade: desenha tudo numa tela FATOR vezes maior (fonte "de verdade"
# maior, não upscale borrado), pra imagem ficar nítida em zoom/impressão. O resto do
# arquivo continua calculando posições em unidades "lógicas" 1x, sem precisar mexer
# em nenhuma conta — quem escala é o _DrawEscalado (abaixo) e o _carregar_fonte.
_FATOR_QUALIDADE = 1.5


def _carregar_fonte(tamanho: int, negrito: bool = False) -> ImageFont.FreeTypeFont:
    """Tenta carregar uma fonte TrueType comum; cai para a fonte padrão do
    Pillow se nenhuma das opções estiver disponível no servidor. Carrega já no
    tamanho físico (tamanho lógico × _FATOR_QUALIDADE)."""
    candidatos = (
        ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"]
        if negrito else
        ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]
    )
    tamanho_fisico = max(1, round(tamanho * _FATOR_QUALIDADE))
    for nome in candidatos:
        try:
            return ImageFont.truetype(nome, tamanho_fisico)
        except Exception:
            continue
    return ImageFont.load_default()


class _DrawEscalado:
    """Envolve um ImageDraw.Draw real e desenha numa tela _FATOR_QUALIDADE vezes
    maior, SEM exigir mudar as contas de posição já existentes no arquivo (que
    continuam em unidades lógicas 1x). Coordenadas de desenho (.text/.rectangle/
    .line/.ellipse/.pieslice) são multiplicadas pelo fator antes de chegar no PIL
    de verdade; medição de texto (.textlength/.textbbox) devolve o valor DIVIDIDO
    pelo fator, pra continuar batendo com o resto da conta em 1x."""

    def __init__(self, draw_real, fator: float):
        self._d = draw_real
        self._f = fator

    def _esc(self, xy):
        if isinstance(xy, (list, tuple)) and xy and isinstance(xy[0], (list, tuple)):
            return [(x * self._f, y * self._f) for x, y in xy]
        return type(xy)(v * self._f for v in xy)

    def text(self, xy, *args, **kwargs):
        return self._d.text(self._esc(xy), *args, **kwargs)

    def rectangle(self, xy, *args, width: int = 1, **kwargs):
        return self._d.rectangle(self._esc(xy), *args, width=max(1, round(width * self._f)), **kwargs)

    def line(self, xy, *args, width: int = 1, **kwargs):
        return self._d.line(self._esc(xy), *args, width=max(1, round(width * self._f)), **kwargs)

    def ellipse(self, xy, *args, **kwargs):
        return self._d.ellipse(self._esc(xy), *args, **kwargs)

    def pieslice(self, xy, *args, **kwargs):
        return self._d.pieslice(self._esc(xy), *args, **kwargs)

    def textlength(self, *args, **kwargs):
        return self._d.textlength(*args, **kwargs) / self._f

    def textbbox(self, xy, *args, **kwargs):
        bbox = self._d.textbbox(xy, *args, **kwargs)
        return tuple(v / self._f for v in bbox)


# Paleta (RGB) — mesma linguagem visual dos cards do painel, mas em tons
# compatíveis com fundo branco (evita cores muito claras/ilegíveis).
_COR_TEXTO   = (17, 24, 39)
_COR_MUTED   = (95, 94, 90)
_COR_FUNDO_CARD = (243, 244, 246)
_COR_BORDA_TAB  = (211, 209, 199)
_COR_LINHA_TAB  = (230, 228, 220)
_COR_VENCIDO    = (162, 45, 45)
_COR_AVISO_FUNDO = (250, 235, 235)
_COR_OK_TEXTO   = (21, 128, 61)
_COR_OK_FUNDO   = (224, 244, 231)

# Peso relativo de cada coluna — "Cliente" precisa de bem mais espaço que
# "Dias", por exemplo. Colunas não listadas aqui usam peso 1.0.
_PESO_COLUNA = {
    "Cliente": 3.0,
    "Complemento": 2.5,
    "Banco": 1.6,
    "Situação": 1.4,
    "Valor Total": 1.6,
    "Saldo Total": 1.6,
    "Saldo em Aberto": 1.6,
    "Vencimento": 1.3,
    "NF": 0.9,
    "Dias": 0.9,
    "Entrada": 1.3,
    "Dias p/ Vencer": 1.3,
    "Prazo": 1.0,
    "Classificação": 1.9,
    "Cód. Agente": 1.2,
    "ESTADO": 0.7,
    "Consumido em PV": 1.5,
    "PV": 1.3,
    "Total": 1.3,
    "Faturado": 1.5,
    "Consumido em NF": 1.5,
    "Total Consumido": 1.5,
    "Atraso": 0.9,
    "Organização": 3.7,
    "Agente": 3.6,
    "Natureza": 1.1,
    "Documento": 1.9,
    "Data": 1.1,
    "Valor Lançado": 1.5,
    "Saldo em Aberto (Moeda)": 2.3,
    "Saldo em Aberto (R$)": 2.1,
    "Moeda": 0.8,
}


def _larguras_colunas(colunas: list, largura_util: float) -> list:
    """Retorna a largura (em px) de cada coluna, proporcional ao peso dela,
    evitando que colunas de texto longo (Cliente) espremam as vizinhas."""
    pesos = [_PESO_COLUNA.get(c, 1.0) for c in colunas]
    soma_pesos = sum(pesos) or 1.0
    return [largura_util * (p / soma_pesos) for p in pesos]


def _sanitizar_linha(texto) -> str:
    """Remove quebras de linha do texto — o Pillow não consegue medir/desenhar
    texto multilinha com draw.textlength()/draw.text() numa única chamada."""
    return str(texto).replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


def _truncar_texto(draw: ImageDraw.ImageDraw, texto: str, fonte, largura_max: float) -> str:
    """Corta o texto com '...' no final se ele não couber em largura_max px."""
    texto = _sanitizar_linha(texto)
    if draw.textlength(texto, font=fonte) <= largura_max:
        return texto
    reticencias = "..."
    while texto and draw.textlength(texto + reticencias, font=fonte) > largura_max:
        texto = texto[:-1]
    return texto + reticencias if texto else reticencias

def _valor_celula(valor) -> str:
    """Converte o valor da célula em texto, trocando vazios (None/NaN/'')
    por '-' — evita aparecer 'nan' ou 'None' na imagem."""
    if valor is None:
        return "-"
    try:
        if pd.isna(valor):
            return "-"
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if texto.lower() in ("", "nan", "none", "nat"):
        return "-"
    return texto

def _linhas_paineis(paineis: list) -> list:
    """Agrupa os painéis em linhas: dois por linha, ou um sozinho se for de largura total."""
    linhas, atual = [], []
    for q in paineis:
        if q.get("largura_total"):
            if atual:
                linhas.append(atual)
                atual = []
            linhas.append([q])
        else:
            atual.append(q)
            if len(atual) == 2:
                linhas.append(atual)
                atual = []
    if atual:
        linhas.append(atual)
    return linhas


def _altura_painel(p: dict) -> int:
    if p.get("tipo") == "colunas":
        return 150
    if p.get("tipo") == "linha":
        return 142 if any(len(pt) > 3 for pt in p["pontos"]) else 124
    if p.get("tipo") == "rosca":
        return 12 + 24 + max(120, len(p["fatias"]) * 24 + 8) + 8 + 26 + 12
    legenda = 20 if p.get("legenda") else 4
    nota = 18 if p.get("nota") else 0
    return 12 + 24 + legenda + len(p["linhas"]) * 22 + 8 + 26 + nota + 12


def _desenhar_painel(draw, x: float, y: float, larg: float, altura: float, p: dict) -> None:
    """Painel genérico (barras empilhadas ou rosca com legenda) para a imagem de e-mail."""
    fonte_valor = _carregar_fonte(14, negrito=True)
    fonte_label = _carregar_fonte(11)
    fonte_pct = _carregar_fonte(11, negrito=True)
    draw.rectangle([x, y, x + larg, y + altura], outline=_COR_BORDA_TAB, width=1)
    if p.get("tipo") == "colunas":
        # total à esquerda e 12 colunas à direita (valor, variação e mês)
        fonte_grande = _carregar_fonte(18, negrito=True)
        draw.text((x + 14, y + 14), _sanitizar_linha(p["titulo"]), font=fonte_label, fill=_COR_MUTED)
        draw.text((x + 14, y + 34), _sanitizar_linha(p["total_texto"]), font=fonte_grande, fill=_COR_TEXTO)
        draw.text((x + 14, y + 62), _sanitizar_linha(p.get("nota", "")), font=fonte_label, fill=_COR_MUTED)
        pontos = p["pontos"]
        n = len(pontos)
        x0, x1 = x + 250, x + larg - 14
        base = y + altura - 22
        maximo = max((q["valor"] for q in pontos), default=0) or 1
        passo = (x1 - x0) / n
        for k, q in enumerate(pontos):
            cx = x0 + passo * (k + 0.5)
            alt = max(2, q["valor"] / maximo * 44)
            cor_b = (127, 184, 209) if q.get("parcial") else (46, 134, 171)
            draw.rectangle([cx - passo * 0.32, base - alt, cx + passo * 0.32, base], fill=cor_b)
            tv = _sanitizar_linha(q["texto"])
            draw.text((cx - draw.textlength(tv, font=fonte_pct) / 2, base - alt - 30), tv, font=fonte_pct, fill=_COR_TEXTO)
            tp = _sanitizar_linha(q["var_texto"])
            draw.text((cx - draw.textlength(tp, font=fonte_label) / 2, base - alt - 16), tp, font=fonte_label, fill=q["var_cor"])
            lm = _sanitizar_linha(q["label"])
            draw.text((cx - draw.textlength(lm, font=fonte_label) / 2, base + 5), lm, font=fonte_label, fill=_COR_MUTED)
        return
    if p.get("tipo") == "linha":
        # total à esquerda e linha dos anos à direita (largura total, altura baixa)
        fonte_grande = _carregar_fonte(18, negrito=True)
        draw.text((x + 14, y + 14), _sanitizar_linha(p["titulo"]), font=fonte_label, fill=_COR_MUTED)
        draw.text((x + 14, y + 34), _sanitizar_linha(p["total_texto"]), font=fonte_grande, fill=_COR_TEXTO)
        draw.text((x + 14, y + 62), _sanitizar_linha(p.get("nota", "")), font=fonte_label, fill=_COR_MUTED)
        pontos = p["pontos"]
        n = len(pontos)
        com_extra = any(len(pt) > 3 for pt in pontos)   # variação sob cada ponto (gráfico mensal)
        x0, x1 = x + 250, x + larg - 20
        topo, base = y + 38, y + altura - (44 if com_extra else 26)
        maximo = max((pt[1] for pt in pontos), default=0) or 1
        draw.line([(x0 - 10, base), (x1 + 10, base)], fill=_COR_BORDA_TAB, width=1)
        coords = []
        for k, pt in enumerate(pontos):
            cx = x0 + (x1 - x0) * (k + 0.5) / n
            cy = base - pt[1] / maximo * (base - topo)
            coords.append((cx, cy))
        cor_linha, cor_parcial = (46, 134, 171), (127, 184, 209)
        for k in range(1, n):
            ultimo = p.get("parcial") and k == n - 1
            draw.line([coords[k - 1], coords[k]], fill=cor_parcial if ultimo else cor_linha, width=2)
        for k, (pt, (cx, cy)) in enumerate(zip(pontos, coords)):
            rotulo, valor, texto = pt[0], pt[1], pt[2]
            if len(pt) > 3:
                var_texto, var_cor = pt[3]
                vw = draw.textlength(_sanitizar_linha(var_texto), font=fonte_label)
                draw.text((cx - vw / 2, base + 4), _sanitizar_linha(var_texto), font=fonte_label, fill=var_cor)
            cor_p = cor_parcial if (p.get("parcial") and k == n - 1) else cor_linha
            draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=cor_p)
            tw = draw.textlength(_sanitizar_linha(texto), font=fonte_pct)
            draw.text((cx - tw / 2, cy - 20), _sanitizar_linha(texto), font=fonte_pct, fill=_COR_TEXTO)
            lw = draw.textlength(_sanitizar_linha(rotulo), font=fonte_label)
            draw.text((cx - lw / 2, base + (18 if len(pt) > 3 else 6)), _sanitizar_linha(rotulo), font=fonte_label, fill=_COR_MUTED)
        return
    yy = y + 12
    draw.text((x + 14, yy), _sanitizar_linha(p["titulo"]), font=fonte_valor, fill=_COR_TEXTO)
    yy += 24

    if p.get("tipo") == "rosca":
        diam = 110
        furo = 0.62 * diam
        fatias = p["fatias"]
        total = sum(f["valor"] for f in fatias if f["valor"] > 0) or 1
        cx0, cy0 = x + 14, yy + 4
        ang = -90.0
        for f in fatias:
            if f["valor"] <= 0:
                continue
            var = 360.0 * f["valor"] / total
            draw.pieslice([cx0, cy0, cx0 + diam, cy0 + diam], ang, ang + var, fill=f["cor"])
            ang += var
        draw.ellipse([cx0 + (diam - furo) / 2, cy0 + (diam - furo) / 2,
                      cx0 + (diam + furo) / 2, cy0 + (diam + furo) / 2], fill="white")
        centro = _sanitizar_linha(p.get("centro_texto", ""))
        if centro:
            bb = draw.textbbox((0, 0), centro, font=fonte_pct)
            draw.text((cx0 + diam / 2 - (bb[2] - bb[0]) / 2, cy0 + diam / 2 - (bb[3] - bb[1]) / 2 - 1),
                      centro, font=fonte_pct, fill=_COR_TEXTO)
        xl = cx0 + diam + 18
        yl = yy + 6
        for f in fatias:
            draw.rectangle([xl, yl + 3, xl + 9, yl + 12], fill=f["cor"])
            draw.text((xl + 15, yl + 1), _sanitizar_linha(f["label"]), font=fonte_label, fill=_COR_TEXTO)
            txt = _sanitizar_linha(f["texto"])
            xv = x + larg - 14 - draw.textlength(txt, font=fonte_label)
            draw.text((xv, yl + 1), txt, font=fonte_label, fill=_COR_TEXTO)
            pct = f"{max(f['valor'], 0) / total * 100:.2f}%".replace(".", ",")
            draw.text((xv - 12 - draw.textlength(pct, font=fonte_pct), yl + 1), pct, font=fonte_pct, fill=f["cor"])
            yl += 24
        yy += max(diam + 8, len(fatias) * 24 + 8)
    else:
        if p.get("legenda"):
            xl = x + 14
            for nome_leg, cor_leg in p["legenda"]:
                draw.rectangle([xl, yy + 3, xl + 9, yy + 12], fill=cor_leg)
                draw.text((xl + 14, yy), _sanitizar_linha(nome_leg), font=fonte_label, fill=_COR_MUTED)
                xl += 14 + draw.textlength(_sanitizar_linha(nome_leg), font=fonte_label) + 14
            yy += 20
        else:
            yy += 4
        larg_rot = p.get("larg_rotulo", 150)
        larg_val = p.get("larg_valor", 120)
        larg_barra = larg - 28 - larg_rot - larg_val - 12
        maximo = max((sum(v for v, _ in ln["segmentos"]) for ln in p["linhas"]), default=0) or 1
        for ln in p["linhas"]:
            draw.text((x + 14, yy + 4),
                      _truncar_texto(draw, _sanitizar_linha(ln["label"]), fonte_label, larg_rot - 6),
                      font=fonte_label, fill=_COR_TEXTO)
            xb = x + 14 + larg_rot
            draw.rectangle([xb, yy + 7, xb + larg_barra, yy + 15], fill=(236, 235, 230))
            for valor, cor in ln["segmentos"]:
                if valor <= 0:
                    continue
                comp = max(1, larg_barra * valor / maximo)
                draw.rectangle([xb, yy + 7, xb + comp, yy + 15], fill=cor)
                xb += comp
            txt = _sanitizar_linha(ln["texto"])
            draw.text((x + larg - 14 - draw.textlength(txt, font=fonte_label), yy + 4), txt,
                      font=fonte_label, fill=_COR_TEXTO)
            yy += 22

    draw.line([(x + 14, yy + 4), (x + larg - 14, yy + 4)], fill=_COR_BORDA_TAB, width=1)
    draw.text((x + 14, yy + 12), _sanitizar_linha(p.get("total_rotulo", "Total")), font=fonte_valor, fill=_COR_TEXTO)
    tot = _sanitizar_linha(p["total_texto"])
    draw.text((x + larg - 14 - draw.textlength(tot, font=fonte_valor), yy + 12), tot,
              font=fonte_valor, fill=_COR_TEXTO)
    if p.get("nota"):
        draw.text((x + 14, yy + 38), _sanitizar_linha(p["nota"]), font=fonte_label, fill=_COR_MUTED)


def gerar_imagem_resumo_titulos(
    titulo_principal: str,
    cards_resumo: list,
    df_titulos: pd.DataFrame,
    titulo_tabela: str = "Títulos",
    destacar_vencidos: bool = True,
    ordem_colunas: list | None = None,
    largura_imagem: int = 1100,
    aging: dict | None = None,
    max_linhas_tabela: int | None = None,
    faturamento_ano: dict | None = None,
    rosca: dict | None = None,
    mensagem_vazia: str | None = None,
    bloco_direita: dict | None = None,
    rankings: list | None = None,
    nota_rodape: str | None = None,
    paineis: list | None = None,
    cards_por_linha: int = 4,
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
    aging             : (opcional) bloco de aging em barras entre os cards e a tabela:
                         {"titulo", "legenda": [(nome, rgb)], "total_texto",
                          "linhas": [{"label", "segmentos": [(valor, rgb)], "texto", "separador"}]}
    max_linhas_tabela : (opcional) limita a tabela às primeiras N linhas e avisa quantas ficaram de fora
    rosca             : (opcional) gráfico de rosca à esquerda do faturamento por ano:
                         {"titulo", "fatias": [{"label", "valor", "cor" (rgb), "texto"}]}
    faturamento_ano   : (opcional) quadro de barras ao lado do aging:
                         {"titulo", "linhas": [{"label", "valor", "texto"}], "total_texto", "nota"}
    mensagem_vazia    : (opcional) texto exibido num bloco verde quando não há
                         título nenhum (ex.: "Nenhum título em aberto para este cliente.")

    Retorna
    -------
    bytes do PNG gerado, prontos para st.download_button.
    """
    LARGURA = largura_imagem
    MARGEM = 24
    CARDS_POR_LINHA = cards_por_linha
    GAP_CARD = 10
    tem_card_com_sub = any(c.get("sub") for c in cards_resumo if c)
    ALTURA_CARD = 68 if tem_card_com_sub else 56

    fonte_titulo   = _carregar_fonte(18, negrito=True)
    fonte_sub      = _carregar_fonte(11)
    fonte_label    = _carregar_fonte(11)
    fonte_card_sub = _carregar_fonte(10, negrito=True)
    fonte_valor    = _carregar_fonte(14, negrito=True)
    fonte_aviso    = _carregar_fonte(12, negrito=True)
    fonte_tab_head = _carregar_fonte(11, negrito=True)
    fonte_tab_cel  = _carregar_fonte(11)

    # ── Colunas da tabela ────────────────────────────────────────────────────
    colunas_permitidas = [
        "Cód. Cliente", "Cliente", "NF", "Complemento", "Valor Total", "Saldo Total",
        "Saldo em Aberto", "Entrada", "Vencimento", "Prazo", "Dias", "Dias p/ Vencer", "Atraso", "Situação", "Classificação", "Banco",
        "Moeda", "Cotação", "Saldo (Moeda)",
        "Cód. Agente", "ESTADO", "Consumido em PV", "Consumido em NF", "Total Consumido", "PV", "Total", "Faturado",
        "Agente Financeiro", "Grupo Financeiro", "Tipo Conta Financeira", "Extenso", "Reduzido",
        "Saldo Anterior", "Débito", "Crédito", "IOF", "IRRF", "Rendimentos", "Aplicação",
        "Resgate", "Saldo Atual",
    ]
    ordem = ordem_colunas if ordem_colunas else colunas_permitidas
    colunas = [c for c in ordem if c in df_titulos.columns]
    total_titulos = len(df_titulos)
    tem_vencido = destacar_vencidos and "Situação" in df_titulos.columns \
        and (df_titulos["Situação"] == "VENCIDO").any()
    qtd_vencidos = int((df_titulos["Situação"] == "VENCIDO").sum()) if tem_vencido else 0
    # (os vencidos são contados antes de cortar a tabela)
    if max_linhas_tabela is not None and total_titulos > max_linhas_tabela:
        df_titulos = df_titulos.head(max_linhas_tabela)
    n_linhas_tab = len(df_titulos)
    linhas_omitidas = total_titulos - n_linhas_tab

    # ── Cálculo de altura total da imagem ──────────────────────────────────
    n_cards = len(cards_resumo)
    linhas_cards = -(-n_cards // CARDS_POR_LINHA)  # arredonda pra cima
    altura_bloco_cards = linhas_cards * (ALTURA_CARD + GAP_CARD)

    altura_aviso = 34 if (tem_vencido or mensagem_vazia) else 0
    altura_tab_head = 28
    altura_linha_tab = 22
    tem_tabela = total_titulos > 0
    altura_tabela = (altura_tab_head + n_linhas_tab * altura_linha_tab + (22 if linhas_omitidas else 0)) if tem_tabela else 0

    ALTURA_LINHA_AGING = 22
    altura_aging = 0
    if aging:
        altura_aging = 12 + 24 + 20 + len(aging["linhas"]) * ALTURA_LINHA_AGING + 8 + 26 + 12 + 16
    if bloco_direita:
        altura_bd = 12 + 24 + 20 + len(bloco_direita["linhas"]) * ALTURA_LINHA_AGING + 8 + 26 + 12 + 16
        altura_aging = max(altura_aging, altura_bd)
    if rosca:
        altura_aging = max(altura_aging, 12 + 32 + 230 + 12 + len(rosca["fatias"]) * 20 + 12 + 16)
    if faturamento_ano:
        altura_fat = 12 + 32 + len(faturamento_ano["linhas"]) * ALTURA_LINHA_AGING + 8 + 26 + 24 + 12 + 16
        altura_aging = max(altura_aging, altura_fat)

    ALTURA_LINHA_RANK = 22
    altura_rankings = 0
    if rankings:
        max_linhas_rank = max((len(r["linhas"]) for r in rankings), default=0)
        altura_rankings = 28 + max_linhas_rank * ALTURA_LINHA_RANK + 16

    altura_nota_rodape = 24 if nota_rodape else 0

    altura_paineis = 0
    if paineis:
        for linha_p in _linhas_paineis(paineis):
            altura_paineis += max(_altura_painel(q) for q in linha_p) + 12

    altura_total = int(
        MARGEM + 30 + 20 + 16          # cabeçalho + linha divisória
        + altura_bloco_cards + 16
        + altura_aging
        + altura_paineis
        + altura_rankings
        + altura_nota_rodape
        + altura_aviso
        + (22 if tem_tabela else 0) + altura_tabela           # título da seção + tabela
        + MARGEM
    )

    _f = _FATOR_QUALIDADE
    img = Image.new("RGB", (round(LARGURA * _f), round(max(altura_total, 300) * _f)), "white")
    draw = _DrawEscalado(ImageDraw.Draw(img), _f)

    y = MARGEM

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    draw.text((MARGEM, y), _sanitizar_linha(titulo_principal), font=fonte_titulo, fill=_COR_TEXTO)
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
        if card is None:   # célula vazia (alinha a linha seguinte)
            continue
        col = i % CARDS_POR_LINHA
        linha = i // CARDS_POR_LINHA
        x0 = MARGEM + col * (largura_card + GAP_CARD)
        y0 = y + linha * (ALTURA_CARD + GAP_CARD)
        x1 = x0 + largura_card
        y1 = y0 + ALTURA_CARD

        draw.rectangle([x0, y0, x1, y1], fill=card.get("fundo", _COR_FUNDO_CARD))
        draw.rectangle([x0, y0, x0 + 4, y1], fill=card["cor"])
        draw.text((x0 + 12, y0 + 8), _sanitizar_linha(card["label"]), font=fonte_label, fill=_COR_MUTED)
        if "\n" in str(card["valor"]):
            # valor em duas linhas (ex.: "Faturamento" / "Liberado")
            for j, linha_v in enumerate(str(card["valor"]).split("\n")):
                draw.text((x0 + 12, y0 + 20 + j * 16), _sanitizar_linha(linha_v), font=fonte_valor, fill=_COR_TEXTO)
        elif card.get("sub"):
            draw.text((x0 + 12, y0 + 22), _sanitizar_linha(card["sub"]), font=fonte_card_sub, fill=card["cor"])
            draw.text((x0 + 12, y0 + 38), _sanitizar_linha(card["valor"]), font=fonte_valor, fill=_COR_TEXTO)
        else:
            draw.text((x0 + 12, y0 + 26), _sanitizar_linha(card["valor"]), font=fonte_valor, fill=_COR_TEXTO)

    y += altura_bloco_cards + 16

    # ── Aging em barras (bloco à esquerda, largura limitada) ────────────────
    if aging or faturamento_ano or rosca or bloco_direita:
        larg_aging = (largura_util - 12) / 2 if (rosca or bloco_direita) else min(largura_util, 640)
        y_ini = y
    if rosca:
        draw.rectangle([MARGEM, y_ini, MARGEM + larg_aging, y_ini + altura_aging - 16], outline=_COR_BORDA_TAB, width=1)
        draw.text((MARGEM + 14, y_ini + 12), _sanitizar_linha(rosca["titulo"]), font=fonte_valor, fill=_COR_TEXTO)
        total_r = sum(f["valor"] for f in rosca["fatias"]) or 1
        diametro = 220
        furo = 0.55 * diametro
        cx0 = MARGEM + (larg_aging - diametro) / 2
        cy0 = y_ini + 12 + 32
        centro_x, centro_y = cx0 + diametro / 2, cy0 + diametro / 2
        raio_texto = (diametro / 2 + furo / 2) / 2
        fonte_pct = _carregar_fonte(12, negrito=True)
        angulo = -90.0
        for f in rosca["fatias"]:
            if f["valor"] <= 0:
                continue
            varredura = 360.0 * f["valor"] / total_r
            draw.pieslice([cx0, cy0, cx0 + diametro, cy0 + diametro], angulo, angulo + varredura, fill=f["cor"])
            if varredura >= 8:  # fatia fina demais não cabe o texto
                meio = math.radians(angulo + varredura / 2)
                pct_txt = f"{f['valor'] / total_r * 100:.2f}%"
                bbox = draw.textbbox((0, 0), pct_txt, font=fonte_pct)
                lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                tx = centro_x + raio_texto * math.cos(meio) - lw / 2
                ty = centro_y + raio_texto * math.sin(meio) - lh / 2
                draw.text((tx, ty), pct_txt, font=fonte_pct, fill="white")
            angulo += varredura
        draw.ellipse([cx0 + (diametro - furo) / 2, cy0 + (diametro - furo) / 2,
                      cx0 + (diametro + furo) / 2, cy0 + (diametro + furo) / 2], fill="white")
        yl = cy0 + diametro + 12
        for f in rosca["fatias"]:
            draw.rectangle([MARGEM + 14, yl + 4, MARGEM + 24, yl + 14], fill=f["cor"])
            draw.text((MARGEM + 32, yl + 2), _sanitizar_linha(f["label"]), font=fonte_label, fill=_COR_TEXTO)
            txt = _sanitizar_linha(f["texto"])
            draw.text((MARGEM + larg_aging - 14 - draw.textlength(txt, font=fonte_label), yl + 2), txt,
                      font=fonte_label, fill=_COR_TEXTO)
            yl += 20
    if aging:
        draw.rectangle([MARGEM, y, MARGEM + larg_aging, y + altura_aging - 16], outline=_COR_BORDA_TAB, width=1)
        yy = y + 12
        draw.text((MARGEM + 14, yy), _sanitizar_linha(aging["titulo"]), font=fonte_valor, fill=_COR_TEXTO)
        yy += 24
        xl = MARGEM + 14
        for nome_leg, cor_leg in aging.get("legenda", []):
            draw.rectangle([xl, yy + 3, xl + 9, yy + 12], fill=cor_leg)
            draw.text((xl + 14, yy), _sanitizar_linha(nome_leg), font=fonte_label, fill=_COR_MUTED)
            xl += 14 + draw.textlength(_sanitizar_linha(nome_leg), font=fonte_label) + 14
        yy += 20
        larg_rot, larg_val = 150, 120
        larg_barra = larg_aging - 28 - larg_rot - larg_val - 12
        maximo = max((sum(v for v, _ in ln["segmentos"]) for ln in aging["linhas"]), default=0) or 1
        for ln in aging["linhas"]:
            draw.text((MARGEM + 14, yy + 4), _sanitizar_linha(ln["label"]), font=fonte_label, fill=_COR_TEXTO)
            xb = MARGEM + 14 + larg_rot
            draw.rectangle([xb, yy + 7, xb + larg_barra, yy + 15], fill=(236, 235, 230))
            for valor, cor in ln["segmentos"]:
                if valor <= 0:
                    continue
                comp = max(1, larg_barra * valor / maximo)
                draw.rectangle([xb, yy + 7, xb + comp, yy + 15], fill=cor)
                xb += comp
            txt = _sanitizar_linha(ln["texto"])
            draw.text((MARGEM + larg_aging - 14 - draw.textlength(txt, font=fonte_label), yy + 4), txt,
                      font=fonte_label, fill=_COR_TEXTO)
            yy += ALTURA_LINHA_AGING
        draw.line([(MARGEM + 14, yy + 4), (MARGEM + larg_aging - 14, yy + 4)], fill=_COR_BORDA_TAB, width=1)
        draw.text((MARGEM + 14, yy + 12), "Saldo em aberto", font=fonte_valor, fill=_COR_TEXTO)
        tot = _sanitizar_linha(aging["total_texto"])
        draw.text((MARGEM + larg_aging - 14 - draw.textlength(tot, font=fonte_valor), yy + 12), tot,
                  font=fonte_valor, fill=_COR_TEXTO)
    if bloco_direita:
        x_bd = MARGEM + larg_aging + 12
        larg_bd = LARGURA - MARGEM - x_bd
        draw.rectangle([x_bd, y_ini, x_bd + larg_bd, y_ini + altura_aging - 16], outline=_COR_BORDA_TAB, width=1)
        yy_bd = y_ini + 12
        draw.text((x_bd + 14, yy_bd), _sanitizar_linha(bloco_direita["titulo"]), font=fonte_valor, fill=_COR_TEXTO)
        yy_bd += 24
        xl_bd = x_bd + 14
        for nome_leg, cor_leg in bloco_direita.get("legenda", []):
            draw.rectangle([xl_bd, yy_bd + 3, xl_bd + 9, yy_bd + 12], fill=cor_leg)
            draw.text((xl_bd + 14, yy_bd), _sanitizar_linha(nome_leg), font=fonte_label, fill=_COR_MUTED)
            xl_bd += 14 + draw.textlength(_sanitizar_linha(nome_leg), font=fonte_label) + 14
        yy_bd += 20
        larg_rot_bd, larg_val_bd = 130, 110
        larg_barra_bd = larg_bd - 28 - larg_rot_bd - larg_val_bd - 12
        maximo_bd = max((sum(v for v, _ in ln["segmentos"]) for ln in bloco_direita["linhas"]), default=0) or 1
        for ln in bloco_direita["linhas"]:
            draw.text((x_bd + 14, yy_bd + 4), _sanitizar_linha(ln["label"]), font=fonte_label, fill=_COR_TEXTO)
            xb = x_bd + 14 + larg_rot_bd
            draw.rectangle([xb, yy_bd + 7, xb + larg_barra_bd, yy_bd + 15], fill=(236, 235, 230))
            for valor, cor in ln["segmentos"]:
                if valor <= 0:
                    continue
                comp = max(1, larg_barra_bd * valor / maximo_bd)
                draw.rectangle([xb, yy_bd + 7, xb + comp, yy_bd + 15], fill=cor)
                xb += comp
            txt = _sanitizar_linha(ln["texto"])
            draw.text((x_bd + larg_bd - 14 - draw.textlength(txt, font=fonte_label), yy_bd + 4), txt,
                      font=fonte_label, fill=_COR_TEXTO)
            yy_bd += ALTURA_LINHA_AGING
        draw.line([(x_bd + 14, yy_bd + 4), (x_bd + larg_bd - 14, yy_bd + 4)], fill=_COR_BORDA_TAB, width=1)
        draw.text((x_bd + 14, yy_bd + 12), "Total em aberto", font=fonte_valor, fill=_COR_TEXTO)
        tot_bd = _sanitizar_linha(bloco_direita["total_texto"])
        draw.text((x_bd + larg_bd - 14 - draw.textlength(tot_bd, font=fonte_valor), yy_bd + 12), tot_bd,
                  font=fonte_valor, fill=_COR_TEXTO)

    if aging or faturamento_ano or rosca or bloco_direita:
        # ── Faturamento por ano (ao lado do aging ou da rosca; sozinho, fica à esquerda) ──
        if faturamento_ano:
            x_f = MARGEM + larg_aging + 12 if (aging or rosca) else MARGEM
            larg_f = LARGURA - MARGEM - x_f if (aging or rosca) else larg_aging
            draw.rectangle([x_f, y_ini, x_f + larg_f, y_ini + altura_aging - 16], outline=_COR_BORDA_TAB, width=1)
            yf = y_ini + 12
            draw.text((x_f + 14, yf), _sanitizar_linha(faturamento_ano["titulo"]), font=fonte_valor, fill=_COR_TEXTO)
            yf += 32
            maximo_f = max((ln["valor"] for ln in faturamento_ano["linhas"]), default=0) or 1
            larg_rot_f, larg_val_f = 110, 90
            larg_barra_f = larg_f - 28 - larg_rot_f - larg_val_f - 12
            for ln in faturamento_ano["linhas"]:
                draw.text((x_f + 14, yf + 4), _sanitizar_linha(ln["label"]), font=fonte_label, fill=_COR_TEXTO)
                xb = x_f + 14 + larg_rot_f
                draw.rectangle([xb, yf + 6, xb + larg_barra_f, yf + 16], fill=(236, 235, 230))
                cor_f = (127, 184, 209) if "parcial" in ln["label"] else (46, 134, 171)
                draw.rectangle([xb, yf + 6, xb + max(1, larg_barra_f * ln["valor"] / maximo_f), yf + 16], fill=cor_f)
                txt = _sanitizar_linha(ln["texto"])
                draw.text((x_f + larg_f - 14 - draw.textlength(txt, font=fonte_label), yf + 4), txt,
                          font=fonte_label, fill=_COR_TEXTO)
                yf += ALTURA_LINHA_AGING
            draw.line([(x_f + 14, yf + 4), (x_f + larg_f - 14, yf + 4)], fill=_COR_BORDA_TAB, width=1)
            draw.text((x_f + 14, yf + 12), "Total faturado", font=fonte_valor, fill=_COR_TEXTO)
            tot_f = _sanitizar_linha(faturamento_ano["total_texto"])
            draw.text((x_f + larg_f - 14 - draw.textlength(tot_f, font=fonte_valor), yf + 12), tot_f,
                      font=fonte_valor, fill=_COR_TEXTO)
            draw.text((x_f + 14, yf + 36), _sanitizar_linha(faturamento_ano.get("nota", "")),
                      font=fonte_label, fill=_COR_MUTED)
        y = y_ini + altura_aging

    # ── Painéis genéricos (barras / rosca), dois por linha ───────────────────
    if paineis:
        larg_p = (largura_util - 12) / 2
        for linha_p in _linhas_paineis(paineis):
            alt_p = max(_altura_painel(q) for q in linha_p)
            for j, painel in enumerate(linha_p):
                larg_painel = largura_util if painel.get("largura_total") else larg_p
                _desenhar_painel(draw, MARGEM + j * (larg_p + 12), y, larg_painel, alt_p, painel)
            y += alt_p + 12

    # ── Rankings de clientes (dois blocos side-by-side) ──────────────────────
    if rankings:
        larg_util_r = largura_util
        n_rank = len(rankings)
        larg_col = (larg_util_r - (n_rank - 1) * 12) / n_rank
        y_rank = y
        max_y_rank = y
        for col_i, rank in enumerate(rankings):
            x_col = MARGEM + col_i * (larg_col + 12)
            yy = y_rank
            draw.text((x_col, yy), _sanitizar_linha(rank["titulo"]), font=fonte_valor, fill=_COR_TEXTO)
            yy += 24
            linhas_rank = rank.get("linhas", [])
            cor_bar = rank.get("cor", (74, 127, 181))
            if linhas_rank:
                maximo_r = max(v for _, v, _ in linhas_rank) or 1
                larg_rot_r = int(larg_col * 0.42)
                larg_val_r = 100
                larg_bar_r = larg_col - larg_rot_r - larg_val_r - 10
                for idx, (rotulo, valor, texto) in enumerate(linhas_rank):
                    num_txt = f"{idx + 1}."
                    draw.text((x_col, yy + 4), num_txt, font=fonte_label, fill=_COR_MUTED)
                    draw.text((x_col + 22, yy + 4),
                              _truncar_texto(draw, rotulo, fonte_label, larg_rot_r - 24),
                              font=fonte_label, fill=_COR_TEXTO)
                    comp = max(2, larg_bar_r * (valor / maximo_r))
                    draw.rectangle([x_col + larg_rot_r, yy + 6, x_col + larg_rot_r + comp, yy + 16], fill=cor_bar)
                    draw.text((x_col + larg_rot_r + comp + 4, yy + 4), _sanitizar_linha(texto),
                              font=fonte_label, fill=_COR_TEXTO)
                    yy += ALTURA_LINHA_RANK
            max_y_rank = max(max_y_rank, yy)
        y = max_y_rank + 12

    # ── Nota de rodapé (representatividade, etc.) ─────────────────────────────
    if nota_rodape:
        draw.rectangle([MARGEM, y, LARGURA - MARGEM, y + 20], fill=(58, 46, 0))
        draw.text((MARGEM + 8, y + 4), _sanitizar_linha(nota_rodape), font=fonte_label, fill=(239, 159, 39))
        y += 24

    # ── Aviso de títulos vencidos, ou mensagem de "sem títulos" ──────────────
    if tem_vencido:
        draw.rectangle([MARGEM, y, LARGURA - MARGEM, y + 26], fill=_COR_AVISO_FUNDO)
        draw.text(
            (MARGEM + 10, y + 6),
            f"Atenção: {qtd_vencidos} título(s) vencido(s)" + (" no total." if linhas_omitidas else " nesta lista."),
            font=fonte_aviso, fill=_COR_VENCIDO,
        )
        y += 34
    elif mensagem_vazia:
        draw.rectangle([MARGEM, y, LARGURA - MARGEM, y + 26], fill=_COR_OK_FUNDO)
        draw.text((MARGEM + 10, y + 6), _sanitizar_linha(mensagem_vazia), font=fonte_aviso, fill=_COR_OK_TEXTO)
        y += 34

    # ── Tabela de títulos ────────────────────────────────────────────────────
    if tem_tabela:
        draw.text((MARGEM, y), _sanitizar_linha(titulo_tabela), font=fonte_tab_head, fill=_COR_TEXTO)
        y += 22

    if colunas and tem_tabela:
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
                valor = _valor_celula(row.get(col, "-"))
                valor = _truncar_texto(draw, valor, fonte_tab_cel, larguras_col[i] - 12)
                draw.text((posicoes_col[i] + 6, y + 4), valor, font=fonte_tab_cel, fill=cor_linha)
            y += altura_linha_tab
            draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=_COR_LINHA_TAB, width=1)

    if linhas_omitidas:
        draw.text((MARGEM, y + 5),
                  f"Mostrando {n_linhas_tab} de {total_titulos} títulos. Veja a lista completa no painel.",
                  font=fonte_label, fill=_COR_MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def gerar_imagem_painel_externo(
    titulo_principal: str,
    cards_resumo: list,
    ranking: list,
    titulo_ranking: str,
    aging: list,
    titulo_aging: str,
    resumo_aging: str = "",
    cotacoes: list = None,
    impacto: dict = None,
    total_ranking: float = None,
    total_aging_texto: str = "",
) -> bytes:
    """Imagem (fundo branco) do painel Contas a Receber Externo: cards de saldo, cotações PTAX
    com sparkline, impacto cambial, ranking de clientes (barras com %) e aging (barras horizontais).

    cards_resumo : lista de dicts {label, valor, cor} (4 por linha)
    cotacoes     : lista de dicts {label, valor, subtitulo, cor, serie, maxima, minima} (cards com sparkline)
    impacto      : dict {"titulo": str, "cabecalho": [...], "linhas": [[...], ...]}; célula que começa com ▲/▼ é colorida
    ranking      : lista de (rotulo, valor_numerico, texto_do_valor)
    total_ranking: total de referência para o % de cada cliente (None = sem coluna de %)
    aging        : lista de dicts {label, valor, texto, pct, cor}
    """
    LARGURA, MARGEM, GAP = 1300, 24, 10
    CARDS_POR_LINHA, ALTURA_CARD = 4, 56
    ALTURA_COT = 86
    cor_track = (229, 231, 235)
    fonte_titulo = _carregar_fonte(18, negrito=True)
    fonte_sub = _carregar_fonte(11)
    fonte_secao = _carregar_fonte(14, negrito=True)
    fonte_label = _carregar_fonte(12)
    fonte_valor = _carregar_fonte(14, negrito=True)
    fonte_peq = _carregar_fonte(11)
    fonte_negrito = _carregar_fonte(12, negrito=True)

    largura_util = LARGURA - 2 * MARGEM
    largura_card = (largura_util - GAP * (CARDS_POR_LINHA - 1)) / CARDS_POR_LINHA

    linhas_cards = -(-len(cards_resumo) // CARDS_POR_LINHA) if cards_resumo else 0
    altura_cards = linhas_cards * (ALTURA_CARD + GAP)
    altura_cot = (ALTURA_COT + 26 + GAP) if cotacoes else 0
    altura_imp = (26 + 18 + len(impacto["linhas"]) * 26 + 22 + 14) if impacto else 0
    altura_secao = 40 + max(len(ranking) * 32, len(aging) * 36 + 40) + 10
    altura_total = MARGEM + 26 + 20 + 16 + altura_cards + altura_cot + altura_imp + altura_secao + MARGEM

    _f = _FATOR_QUALIDADE
    img = Image.new("RGB", (round(LARGURA * _f), round(altura_total * _f)), "white")
    draw = _DrawEscalado(ImageDraw.Draw(img), _f)
    y = MARGEM

    draw.text((MARGEM, y), _sanitizar_linha(titulo_principal), font=fonte_titulo, fill=_COR_TEXTO)
    y += 26
    draw.text((MARGEM, y), f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", font=fonte_sub, fill=_COR_MUTED)
    y += 20
    draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=(12, 68, 123), width=2)
    y += 16

    for i, card in enumerate(cards_resumo):
        col, linha = i % CARDS_POR_LINHA, i // CARDS_POR_LINHA
        x0 = MARGEM + col * (largura_card + GAP)
        y0 = y + linha * (ALTURA_CARD + GAP)
        draw.rectangle([x0, y0, x0 + largura_card, y0 + ALTURA_CARD], fill=_COR_FUNDO_CARD)
        draw.rectangle([x0, y0, x0 + 4, y0 + ALTURA_CARD], fill=card["cor"])
        draw.text((x0 + 12, y0 + 8), _sanitizar_linha(card["label"]), font=fonte_sub, fill=_COR_MUTED)
        draw.text((x0 + 12, y0 + 26), _sanitizar_linha(card["valor"]), font=fonte_valor, fill=_COR_TEXTO)
    y += altura_cards

    if cotacoes:
        draw.text((MARGEM, y + 4), "Cotação PTAX com variação vs D-2", font=fonte_sub, fill=_COR_MUTED)
        y += 26
        for i, c in enumerate(cotacoes):
            x0 = MARGEM + i * (largura_card + GAP)
            draw.rectangle([x0, y, x0 + largura_card, y + ALTURA_COT], fill=_COR_FUNDO_CARD)
            draw.rectangle([x0, y, x0 + 4, y + ALTURA_COT], fill=c["cor"])
            draw.text((x0 + 12, y + 8), _sanitizar_linha(c["label"]), font=fonte_sub, fill=_COR_MUTED)
            draw.text((x0 + 12, y + 24), _sanitizar_linha(c["valor"]), font=fonte_valor, fill=_COR_TEXTO)
            draw.text((x0 + 12, y + 46), _sanitizar_linha(c.get("subtitulo", "")), font=fonte_peq, fill=_COR_MUTED)
            serie = c.get("serie") or []
            if len(serie) >= 2:
                lo, hi = min(serie), max(serie)
                span = (hi - lo) or 1
                pts = []
                for k, v in enumerate(serie):
                    px = x0 + 12 + k / (len(serie) - 1) * (largura_card - 24)
                    py = y + ALTURA_COT - 24 - ((v - lo) / span) * 14
                    pts.append((px, py))
                draw.line(pts, fill=c["cor"], width=2)
            draw.text((x0 + 12, y + ALTURA_COT - 16), f"máx {c.get('maxima', '')}", font=fonte_peq, fill=_COR_MUTED)
            txt_min = f"mín {c.get('minima', '')}"
            draw.text((x0 + largura_card - 12 - draw.textlength(txt_min, font=fonte_peq), y + ALTURA_COT - 16),
                      txt_min, font=fonte_peq, fill=_COR_MUTED)
        y += ALTURA_COT + GAP

    if impacto:
        draw.rectangle([MARGEM, y, LARGURA - MARGEM, y + altura_imp - 14], fill=_COR_FUNDO_CARD)
        draw.text((MARGEM + 12, y + 10), _sanitizar_linha(impacto["titulo"]), font=fonte_negrito, fill=_COR_TEXTO)
        cab = impacto["cabecalho"]
        larg_col = (largura_util - 24) / len(cab)
        ty = y + 36
        for j, titulo_col in enumerate(cab):
            draw.text((MARGEM + 12 + j * larg_col, ty), _sanitizar_linha(titulo_col), font=fonte_sub, fill=_COR_MUTED)
        for r, linha_imp in enumerate(impacto["linhas"]):
            yy = ty + 22 + r * 26
            for j, val in enumerate(linha_imp):
                txt = _sanitizar_linha(val)
                if txt.startswith("▼"):
                    cor = (226, 75, 74)
                elif txt.startswith("▲"):
                    cor = (34, 197, 94)
                else:
                    cor = _COR_TEXTO
                draw.text((MARGEM + 12 + j * larg_col, yy), txt, font=fonte_label, fill=cor)
        y += altura_imp

    meio = LARGURA // 2

    # ── Ranking de clientes (barras, com % do total quando informado) ────────
    draw.text((MARGEM, y), _sanitizar_linha(titulo_ranking), font=fonte_secao, fill=_COR_TEXTO)
    if total_ranking:
        draw.text((MARGEM, y + 20), "% sobre saldo total em aberto", font=fonte_sub, fill=_COR_MUTED)
    y_r = y + 40
    if ranking:
        maximo = max(v for _, v, _ in ranking) or 1
        x_rot, x_pct = MARGEM + 24, MARGEM + 330
        x_b0, x_b1 = MARGEM + 380, meio - 40
        for i, (rotulo, valor, texto) in enumerate(ranking):
            yy = y_r + i * 32
            draw.text((MARGEM, yy + 6), str(i + 1), font=fonte_sub, fill=_COR_MUTED)
            draw.text((x_rot, yy + 6), _truncar_texto(draw, rotulo, fonte_label, x_pct - x_rot - 44),
                      font=fonte_label, fill=_COR_TEXTO)
            if total_ranking:
                pct = f"{valor / total_ranking * 100:.2f}%".replace(".", ",")
                draw.text((x_pct - 40, yy + 6), pct, font=fonte_sub, fill=(74, 127, 181))
            draw.rectangle([x_b0, yy + 8, x_b1, yy + 24], fill=cor_track)
            draw.rectangle([x_b0, yy + 8, x_b0 + (x_b1 - x_b0) * valor / maximo, yy + 24], fill=(74, 127, 181))
            draw.text((meio - 12 - draw.textlength(texto, font=fonte_negrito), yy + 6), texto,
                      font=fonte_negrito, fill=_COR_TEXTO)

    # ── Aging (barras horizontais) ───────────────────────────────────────────
    x_ag = meio + 12
    draw.text((x_ag, y), _sanitizar_linha(titulo_aging), font=fonte_secao, fill=_COR_TEXTO)
    if aging:
        y_a = y + 40
        maximo = max(a["valor"] for a in aging) or 1
        tb0, tb1 = x_ag + 190, LARGURA - MARGEM - 170
        for i, a in enumerate(aging):
            yy = y_a + i * 36
            draw.text((x_ag, yy + 6), _sanitizar_linha(a["label"]), font=fonte_label, fill=_COR_TEXTO)
            draw.rectangle([tb0, yy + 8, tb1, yy + 24], fill=cor_track)
            draw.rectangle([tb0, yy + 8, tb0 + (tb1 - tb0) * a["valor"] / maximo, yy + 24], fill=a["cor"])
            draw.text((LARGURA - MARGEM - draw.textlength(a["texto"], font=fonte_peq), yy + 6), a["texto"],
                      font=fonte_peq, fill=_COR_MUTED)
        yb = y_a + len(aging) * 36 + 4
        draw.line([(x_ag, yb), (LARGURA - MARGEM, yb)], fill=_COR_BORDA_TAB, width=1)
        if resumo_aging:
            draw.text((x_ag, yb + 8), _sanitizar_linha(resumo_aging), font=fonte_peq, fill=_COR_MUTED)
        if total_aging_texto:
            draw.text((LARGURA - MARGEM - draw.textlength(total_aging_texto, font=fonte_negrito), yb + 8),
                      _sanitizar_linha(total_aging_texto), font=fonte_negrito, fill=_COR_TEXTO)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def gerar_imagem_visao_geral(titulo_principal: str, cards_resumo: list, blocos: list,
                             faturamento_grafico: dict | None = None,
                             rankings: dict | None = None) -> bytes:
    """Imagem (fundo branco) da Visão Geral do Contas a Receber: uma linha de cartões e,
    abaixo, os painéis de mercado lado a lado, cada um com o aging em barras.

    cards_resumo        : lista de dicts {label, valor, sub, cor}
    blocos              : lista de dicts {nome, tag, legenda [(nome, cor)], total_texto,
                          linhas [{label, segmentos [(valor, cor)], texto, separador}]}
    faturamento_grafico : dict {anos: [...], mi: [...], me: [...]} (valores em R$, não em M)
    rankings            : dict {mi: {titulo, cor, linhas: [{pos, nome, pct, valor, barw}]}, me: ...}
    """
    LARGURA, MARGEM, GAP = 1500, 24, 12
    ALTURA_CARD, ALTURA_LINHA = 78, 26
    f_titulo, f_sub = _carregar_fonte(20, negrito=True), _carregar_fonte(12)
    f_secao, f_label = _carregar_fonte(16, negrito=True), _carregar_fonte(13)
    f_valor, f_card = _carregar_fonte(14, negrito=True), _carregar_fonte(19, negrito=True)
    f_peq = _carregar_fonte(11)
    f_val_peq = _carregar_fonte(10, negrito=True)

    n_linhas = max((len(b["linhas"]) for b in blocos), default=0)
    altura_bloco = 16 + 28 + 22 + n_linhas * ALTURA_LINHA + 12 + 34 + 12
    ALTURA_GRAFICO_FAT = 230 if faturamento_grafico else 0
    n_rank = max(
        (len(rankings["mi"]["linhas"]) if rankings else 0),
        (len(rankings["me"]["linhas"]) if rankings else 0),
    ) if rankings else 0
    ALTURA_RANK = (16 + 22 + 22 + n_rank * 22 + 12) if n_rank > 0 else 0
    altura_total = (
        MARGEM + 30 + 22 + 18 + ALTURA_CARD + 18 + altura_bloco
        + (ALTURA_GRAFICO_FAT + 16 if faturamento_grafico else 0)
        + (ALTURA_RANK + 16 if ALTURA_RANK else 0)
        + MARGEM
    )

    _f = _FATOR_QUALIDADE
    img = Image.new("RGB", (round(LARGURA * _f), round(altura_total * _f)), "white")
    draw = _DrawEscalado(ImageDraw.Draw(img), _f)
    y = MARGEM
    draw.text((MARGEM, y), _sanitizar_linha(titulo_principal), font=f_titulo, fill=_COR_TEXTO)
    y += 30
    draw.text((MARGEM, y), f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", font=f_sub, fill=_COR_MUTED)
    y += 22
    draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=(12, 68, 123), width=2)
    y += 18

    # ── Cartões ──
    largura_util = LARGURA - 2 * MARGEM
    n = max(len(cards_resumo), 1)
    larg_card = (largura_util - GAP * (n - 1)) / n
    for i, card in enumerate(cards_resumo):
        x0 = MARGEM + i * (larg_card + GAP)
        draw.rectangle([x0, y, x0 + larg_card, y + ALTURA_CARD], fill=_COR_FUNDO_CARD)
        draw.rectangle([x0, y, x0 + 4, y + ALTURA_CARD], fill=card["cor"])
        draw.text((x0 + 14, y + 8), _sanitizar_linha(card["label"]), font=f_label, fill=_COR_MUTED)
        draw.text((x0 + 14, y + 27), _sanitizar_linha(card["valor"]), font=f_card, fill=_COR_TEXTO)
        draw.text((x0 + 14, y + 56), _truncar_texto(draw, card.get("sub", ""), f_peq, larg_card - 24),
                  font=f_peq, fill=_COR_MUTED)
    y += ALTURA_CARD + 18

    # ── Painéis de mercado (larguras 1 : 1,2) ──
    total_pesos = 2.2
    larg1 = (largura_util - GAP) * 1.0 / total_pesos
    larguras = [larg1, (largura_util - GAP) - larg1]
    x = MARGEM
    for bloco, larg in zip(blocos, larguras):
        draw.rectangle([x, y, x + larg, y + altura_bloco], outline=_COR_BORDA_TAB, width=1)
        yy = y + 14
        draw.text((x + 14, yy), _sanitizar_linha(bloco["nome"]), font=f_secao, fill=_COR_TEXTO)
        tag = _sanitizar_linha(bloco["tag"])
        draw.text((x + larg - 14 - draw.textlength(tag, font=f_peq), yy + 4), tag, font=f_peq, fill=_COR_MUTED)
        yy += 28
        xl = x + 14
        for nome_leg, cor_leg in bloco.get("legenda", []):
            draw.rectangle([xl, yy + 3, xl + 9, yy + 12], fill=cor_leg)
            draw.text((xl + 14, yy), _sanitizar_linha(nome_leg), font=f_peq, fill=_COR_MUTED)
            xl += 14 + draw.textlength(_sanitizar_linha(nome_leg), font=f_peq) + 14
        yy += 22
        larg_rotulo, larg_valor = 170, 130
        larg_barra = larg - 28 - larg_rotulo - larg_valor - 16
        maximo = max((sum(v for v, _ in ln["segmentos"]) for ln in bloco["linhas"]), default=0) or 1
        for ln in bloco["linhas"]:
            if ln.get("separador"):
                yy += 4
            draw.text((x + 14, yy + 4), _sanitizar_linha(ln["label"]), font=f_label, fill=_COR_TEXTO)
            xb = x + 14 + larg_rotulo
            draw.rectangle([xb, yy + 7, xb + larg_barra, yy + 17], fill=(236, 235, 230))
            for valor, cor in ln["segmentos"]:
                if valor <= 0:
                    continue
                comp = max(1, larg_barra * valor / maximo)
                draw.rectangle([xb, yy + 7, xb + comp, yy + 17], fill=cor)
                xb += comp
            texto = _sanitizar_linha(ln["texto"])
            draw.text((x + larg - 14 - draw.textlength(texto, font=f_valor), yy + 4), texto, font=f_valor, fill=_COR_TEXTO)
            yy += ALTURA_LINHA
        draw.line([(x + 14, yy + 6), (x + larg - 14, yy + 6)], fill=_COR_BORDA_TAB, width=1)
        draw.text((x + 14, yy + 14), "Total em reais", font=f_valor, fill=_COR_TEXTO)
        total = _sanitizar_linha(bloco["total_texto"])
        draw.text((x + larg - 14 - draw.textlength(total, font=f_valor), yy + 14), total, font=f_valor, fill=_COR_TEXTO)
        x += larg + GAP

    # ── Gráfico de faturamento MI × ME ──────────────────────────────────────
    if faturamento_grafico:
        anos_f = faturamento_grafico.get("anos", [])
        mi_f   = faturamento_grafico.get("mi", [])
        me_f   = faturamento_grafico.get("me", [])
        n_pts  = min(len(anos_f), len(mi_f), len(me_f))
        if n_pts >= 2:
            y_bloco = y + altura_bloco + 16
            COR_MI_I  = (55, 138, 221)   # #378ADD
            COR_ME_I  = (139, 92, 246)   # #8B5CF6
            COR_GRID  = (220, 218, 210)
            BX0 = MARGEM
            BX1 = LARGURA - MARGEM
            BY0 = y_bloco
            BY1 = y_bloco + ALTURA_GRAFICO_FAT
            draw.rectangle([BX0, BY0, BX1, BY1], outline=_COR_BORDA_TAB, width=1)

            # título + legenda
            yy = BY0 + 14
            draw.text((BX0 + 14, yy), "Faturamento por ano (MI × ME)", font=f_secao, fill=_COR_TEXTO)
            yy += 26
            # MI dot
            draw.ellipse([BX0 + 14, yy + 3, BX0 + 22, yy + 11], fill=COR_MI_I)
            draw.text((BX0 + 27, yy), "Mercado Interno", font=f_peq, fill=_COR_MUTED)
            # ME dot
            draw.ellipse([BX0 + 175, yy + 3, BX0 + 183, yy + 11], fill=COR_ME_I)
            draw.text((BX0 + 188, yy), "Mercado Externo", font=f_peq, fill=_COR_MUTED)
            yy += 18

            # área útil do gráfico
            PL, PR, PT, PB = 12, 12, 28, 22
            CW = (BX1 - BX0 - 28) - PL - PR
            CH = BY1 - yy - PB - PT - 6
            XO = BX0 + 14 + PL
            YO = yy + PT

            max_v = max(max(mi_f[:n_pts], default=0), max(me_f[:n_pts], default=0)) or 1

            def _xp(i):
                return XO + i * CW / max(n_pts - 1, 1)

            def _yp(v):
                return YO + CH - (v / max_v) * CH

            # grade
            for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
                gy = round(YO + CH * (1.0 - frac))
                draw.line([(XO, gy), (XO + CW, gy)], fill=COR_GRID, width=1)

            # linhas MI e ME
            pts_mi = [(round(_xp(i)), round(_yp(mi_f[i]))) for i in range(n_pts)]
            pts_me = [(round(_xp(i)), round(_yp(me_f[i]))) for i in range(n_pts)]
            draw.line(pts_mi, fill=COR_MI_I, width=2)
            draw.line(pts_me, fill=COR_ME_I, width=2)

            def _fmt_v(v):
                if v >= 1e9:    # cortado, nunca arredondado para cima (igual aos painéis)
                    return f"{math.floor(v/1e7 + 1e-9)/100:.2f}B".replace(".", ",")
                if v >= 1e6:
                    return f"{math.floor(v/1e5 + 1e-9)/10:.1f}M".replace(".", ",")
                if v >= 1e3:
                    return f"{math.floor(v/1e3 + 1e-9):.0f}K"
                return str(int(v))

            # pontos + rótulos
            for i in range(n_pts):
                xp_mi, yp_mi = pts_mi[i]
                xp_me, yp_me = pts_me[i]
                r = 4
                draw.ellipse([xp_mi - r, yp_mi - r, xp_mi + r, yp_mi + r], fill=COR_MI_I)
                draw.ellipse([xp_me - r, yp_me - r, xp_me + r, yp_me + r], fill=COR_ME_I)
                if mi_f[i] > 0:
                    draw.text((xp_mi, yp_mi + 8), _fmt_v(mi_f[i]),
                              font=f_val_peq, fill=COR_MI_I, anchor="mt")
                if me_f[i] > 0:
                    draw.text((xp_me, yp_me - 10), _fmt_v(me_f[i]),
                              font=f_val_peq, fill=COR_ME_I, anchor="mb")
                # rótulo do ano
                draw.text((_xp(i), YO + CH + 5), str(anos_f[i]),
                          font=f_peq, fill=_COR_MUTED, anchor="mt")

    # ── Rankings de clientes (MI esq. · ME dir.) — abaixo do gráfico ────────
    if rankings and ALTURA_RANK > 0:
        y_rank = (
            y + altura_bloco + ALTURA_GRAFICO_FAT + 32
            if faturamento_grafico else
            y + altura_bloco + 16
        )
        col_w = (largura_util - GAP) / 2
        # larguras fixas de cada coluna (em px lógicos)
        L_NUM  = 22    # posição
        L_NOME = 220   # nome cliente
        L_PCT  = 50    # percentual
        L_BAR  = 180   # barra
        L_VAL  = 155   # valor monetário
        # gaps entre colunas: 4 4 6 6
        for col_i, chave in enumerate(("mi", "me")):
            blk = rankings[chave]
            linhas_r = blk["linhas"]
            if not linhas_r:
                continue
            cor_r = blk["cor"]
            bx0 = MARGEM + col_i * (col_w + GAP)
            bx1 = bx0 + col_w
            draw.rectangle([bx0, y_rank, bx1, y_rank + ALTURA_RANK], outline=_COR_BORDA_TAB, width=1)
            yy = y_rank + 14
            draw.text((bx0 + 14, yy), blk["titulo"], font=f_secao, fill=_COR_TEXTO)
            yy += 22
            draw.text((bx0 + 14, yy), "% sobre saldo em aberto · em reais", font=f_peq, fill=_COR_MUTED)
            yy += 22
            for ln in linhas_r:
                xi = bx0 + 14
                # número
                draw.text((xi, yy + 4), str(ln["pos"]), font=f_peq, fill=_COR_MUTED)
                xi += L_NUM + 4
                # nome (truncado ao espaço alocado)
                nome = ln["nome"]
                while len(nome) > 1 and draw.textlength(nome, font=f_peq) > L_NOME:
                    nome = nome[:-2] + "…"
                draw.text((xi, yy + 4), nome, font=f_peq, fill=_COR_TEXTO)
                xi += L_NOME + 6
                # pct
                pct_txt = f"{ln['pct']:.2f}%"
                draw.text((xi + L_PCT - draw.textlength(pct_txt, font=f_peq), yy + 4),
                          pct_txt, font=f_peq, fill=cor_r)
                xi += L_PCT + 6
                # barra (trilho cinza claro + fill colorido)
                draw.rectangle([xi, yy + 8, xi + L_BAR, yy + 16], fill=(220, 218, 210))
                fill_w = max(2, L_BAR * ln["barw"] / 100)
                draw.rectangle([xi, yy + 8, xi + fill_w, yy + 16], fill=cor_r)
                xi += L_BAR + 6
                # valor
                val_txt = _sanitizar_linha(
                    f"R$ {ln['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                draw.text((bx1 - 14 - draw.textlength(val_txt, font=f_peq), yy + 4),
                          val_txt, font=f_peq, fill=_COR_TEXTO)
                yy += 22

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def gerar_imagem_situacao_cliente(
    codigo_agente: str,
    cliente: str,
    cards_resumo: list,
    df_titulos: pd.DataFrame,
    aging: dict | None = None,
    max_linhas_tabela: int | None = None,
    faturamento_ano: dict | None = None,
    rosca: dict | None = None,
    mensagem_vazia: str | None = None,
    nota_rodape: str | None = None,
    paineis: list | None = None,
    cards_por_linha: int = 4,
) -> bytes:
    """Atalho mantido por compatibilidade — usa a função genérica acima."""
    return gerar_imagem_resumo_titulos(
        titulo_principal=f"Situação Cliente — {codigo_agente} — {cliente}",
        cards_resumo=cards_resumo,
        df_titulos=df_titulos,
        titulo_tabela="Títulos em Aberto",
        destacar_vencidos=True,
        aging=aging,
        max_linhas_tabela=max_linhas_tabela,
        largura_imagem=1250,
        faturamento_ano=faturamento_ano,
        rosca=rosca,
        mensagem_vazia=mensagem_vazia,
        nota_rodape=nota_rodape,
        paineis=paineis,
        cards_por_linha=cards_por_linha,
    )






# ── Texto copiável (para colar direto no corpo do e-mail) ─────────────────────



def gerar_imagem_inconsistencias(
    df: pd.DataFrame,
    titulo: str = "Inconsistências de Lançamentos",
) -> bytes:
    """PNG (fundo branco) com cabeçalho + tabela de inconsistências.

    Colunas exibidas: Filial · AP · Documento · Data · Favorecido ·
                      Valor · Categoria Erro · Observação
    """
    from services.email_service import obter_obs_inconsistencia as _obs

    # Colunas chegam em maiúsculas (data_service faz .upper() nos aliases do SQL)
    MAP = {
        "NOME_FILIAL":    "Filial",
        "AP":             "AP",
        "DOCUMENTO":      "Documento",
        "DATA":           "Data",
        "NOME_AGENTE":    "Favorecido",
        "SALDO":          "Valor",
        "CATEGORIA_ERRO": "Categoria Erro",
    }
    # fallback: procura a coluna de categoria pelo nome parcial
    _col_cat_img = next((c for c in df.columns if "CATEGORIA" in c and "ERRO" in c), None)
    if _col_cat_img and _col_cat_img not in MAP:
        MAP[_col_cat_img] = "Categoria Erro"
    colunas_src   = [c for c in MAP if c in df.columns]
    colunas_label = [MAP[c] for c in colunas_src] + ["Observação"]

    LARGURA, MARGEM = 1400, 24
    largura_util    = LARGURA - 2 * MARGEM
    _f              = _FATOR_QUALIDADE

    fonte_titulo = _carregar_fonte(18, negrito=True)
    fonte_sub    = _carregar_fonte(11)
    fonte_th     = _carregar_fonte(11, negrito=True)
    fonte_td     = _carregar_fonte(11)

    ALTURA_CAB = 30 + 18 + 18 + 4
    ALTURA_TH  = 28
    ALTURA_LIN = 22
    n           = len(df)
    altura_total = MARGEM + ALTURA_CAB + ALTURA_TH + n * ALTURA_LIN + MARGEM

    img  = Image.new("RGB", (round(LARGURA * _f), round(altura_total * _f)), "white")
    draw = _DrawEscalado(ImageDraw.Draw(img), _f)

    y = MARGEM
    draw.text((MARGEM, y), _sanitizar_linha(titulo), font=fonte_titulo, fill=_COR_TEXTO)
    y += 30
    draw.text((MARGEM, y), f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", font=fonte_sub, fill=_COR_MUTED)
    y += 18
    draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=(12, 68, 123), width=2)
    y += 22

    pesos_inc = {
        "Filial": 1.8, "AP": 0.8, "Documento": 1.4, "Data": 1.1,
        "Favorecido": 2.5, "Valor": 1.2, "Categoria Erro": 2.0, "Observação": 2.5,
    }
    pesos = [pesos_inc.get(c, 1.0) for c in colunas_label]
    soma  = sum(pesos) or 1.0
    largs = [largura_util * p / soma for p in pesos]
    xs    = [MARGEM + sum(largs[:i]) for i in range(len(largs))]

    draw.rectangle([MARGEM, y, LARGURA - MARGEM, y + ALTURA_TH],
                   outline=_COR_BORDA_TAB, fill=_COR_FUNDO_CARD)
    for i, col in enumerate(colunas_label):
        draw.text((xs[i] + 6, y + 7),
                  _truncar_texto(draw, col, fonte_th, largs[i] - 12),
                  font=fonte_th, fill=_COR_MUTED)
    y += ALTURA_TH

    _COR_ERRO_IMG  = (162, 45, 45)
    _COR_AVISO_IMG = (183, 96, 14)
    _CORES_CAT = {
        "ERRO CLASSE ADIANTAMENTO":     _COR_AVISO_IMG,
        "ERRO ACAO SEGMENTO":           _COR_AVISO_IMG,
        "ERRO TIPO FAVORECIDO CLIENTE": _COR_ERRO_IMG,
    }

    _col_cat_loop = _col_cat_img or "CATEGORIA_ERRO"
    for _, row in df.iterrows():
        cat    = str(row.get(_col_cat_loop, ""))
        cor_cat = _COR_TEXTO
        for chave, cor in _CORES_CAT.items():
            if chave in cat.upper():
                cor_cat = cor
                break

        valores = []
        for c in colunas_src:
            val = _valor_celula(row.get(c, "-"))
            if c == "SALDO":
                try:
                    val = f"R$ {float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except (ValueError, TypeError):
                    pass
            elif c == "DATA":
                try:
                    val = pd.to_datetime(val).strftime("%d/%m/%Y")
                except Exception:
                    pass
            valores.append(val)
        valores.append(_obs(cat))

        for i, val in enumerate(valores):
            cor = cor_cat if colunas_label[i] in ("Categoria Erro", "Observação") else _COR_TEXTO
            txt = _truncar_texto(draw, val, fonte_td, largs[i] - 12)
            draw.text((xs[i] + 6, y + 4), txt, font=fonte_td, fill=cor)
        y += ALTURA_LIN
        draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=_COR_LINHA_TAB, width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()



def render_botao_copiar_imagem(imagem_bytes: bytes, label: str = "Copiar", key: str = "copiar_img") -> None:
    """Renderiza um botão que copia a imagem PNG (bytes) direto para a
    área de transferência do usuário, usando a Clipboard API do navegador
    (navigator.clipboard.write com ClipboardItem). Assim é só colar
    (Ctrl+V) direto no corpo de um e-mail ou editor de imagem.

    Requer navegador moderno com suporte a ClipboardItem (Chrome/Edge/
    Firefox recentes) e clique do usuário (exigido pela API).
    """
    imagem_b64 = base64.b64encode(imagem_bytes).decode("ascii")
    st.iframe(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        html, body {{
            margin:0; padding:0; overflow:hidden;
            background:transparent;
            font-family:"Source Sans Pro", sans-serif;
        }}
        #btn_{key} {{
            width:100%;
            height:38.4px;
            border-radius:8px;
            border:1px solid rgba(250,250,250,0.2);
            background-color:transparent;
            color:rgb(250,250,250);
            cursor:pointer;
            font-size:14px;
            font-weight:400;
            line-height:1;
            box-sizing:border-box;
            display:flex;
            align-items:center;
            justify-content:center;
            gap:8px;
            white-space:nowrap;
            transition:border-color .15s ease, background-color .15s ease;
        }}
        #btn_{key} svg {{
            flex-shrink:0;
            color:#1E88E5;
        }}
        #btn_{key}:hover {{
            border-color:rgba(250,250,250,0.5);
            background-color:rgba(250,250,250,0.05);
        }}
        #btn_{key}:active {{
            background-color:rgba(250,250,250,0.1);
        }}
        #msg_{key} {{
            font-size:12px;
            min-height:14px;
            margin-top:4px;
            text-align:center;
        }}
    </style>
    </head>
    <body>
        <button id="btn_{key}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            <span>{label}</span>
        </button>
        <div id="msg_{key}"></div>
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
                    msg.innerText = 'Não foi possível copiar.';
                }}
                setTimeout(function() {{ msg.innerText = ''; }}, 3000);
            }});
        </script>
    </body>
    </html>
    """, height=60)
