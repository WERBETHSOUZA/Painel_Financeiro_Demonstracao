import re

import streamlit as st
import pandas as pd
from functools import partial
from components.buttons import botao_exportar_excel, botoes_acao_row
from components.cards import card_html, render_cards_row, render_tabela_html, situacao_faturamento, tamanho_auto
from utils.pendencias import card_pendencias, html_notas_pendentes
from services.data_service import carregar_regra_desconto_cliente
from utils.exporters import exportar_excel
from utils.mercado import sufixo_mercado
from utils.prazos import calcular_dias_prazo, formatar_dias_html, formatar_dias_unificado_html, texto_dias_para_imagem, VERDE_DIAS, VERMELHO_DIAS
from datetime import date

from views.contas_receber_painel import (
    _COR_COMPL, _COR_MI, _COR_VENCIDO, _abrev, _bloco, _completo, _espaco, _faixas, _legenda, _linha, _na_faixa,
)
from views.grupo_credito import _adiantamento_recebido_por_agente, _texto_representatividade
from utils.imagem_email import gerar_imagem_situacao_cliente

# Mesmo motivo do Grupo de Crédito: sem cache, a imagem (Pillow) era refeita em todo
# rerun da página, mesmo sem o usuário pedir. Com cache, só é gerada de novo quando os
# dados do cliente mudam.
_gerar_imagem_situacao_cached = st.cache_data(show_spinner=False, max_entries=50)(gerar_imagem_situacao_cliente)


def _formatar_moeda(valor) -> str:
    try:
        v = float(valor)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


# Cards da Situação Cliente: mais largos e com valor menor, para caber valores como
# R$ 254.170.458,49 em uma linha só e manter todos com a mesma altura.
# 236 px: cabe "R$ 296.887.874,36" (202 px na fonte de 26 px) em uma linha, com recuo de 12 px.
_ESTILO_CARD_SC = dict(largura="236px", altura="96px", padding="12px 12px")

_SIMBOLOS_MOEDA = {"USD": "US$", "EUR": "€", "GBP": "£"}
_NOMES_MOEDA = {"USD": "Dólar", "EUR": "Euro", "GBP": "Libra"}


def _formatar_cotacao(valor) -> str:
    """Cotação sempre com 4 casas decimais (ex.: 5,6666)."""
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _formatar_numero(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


# ── Aging em barras e faturamento por ano ─────────────────────────────────────

_MAX_LINHAS_IMAGEM = 12   # a imagem mostra só as primeiras linhas da tabela
_COR_MOEDA = {"USD": "#378ADD", "EUR": "#1D9E75", "GBP": "#7F77DD"}


def _html_situacao_titulos(a_vencer, vencido, qtd_a_vencer, qtd_vencidos) -> str:
    """Rosca do saldo em aberto: a vencer x vencido, com valor e quantidade de títulos."""
    a_vencer, vencido = max(float(a_vencer or 0), 0.0), max(float(vencido or 0), 0.0)
    total = a_vencer + vencido
    if total <= 0:
        return _bloco("Situação dos títulos", "R$", _COR_MI, "",
                      '<div style="padding:30px 0">Sem saldo em aberto.</div>', 0.0,
                      ocultar=False).replace("Total em reais", "Total em aberto")
    pct_av = a_vencer / total * 100
    pct_v = 100 - pct_av
    cor_av, cor_v = "#1baf7a", "#E24B4A"
    graus = pct_av * 3.6
    pct_av_txt = f"{pct_av:.2f}%".replace(".", ",")
    def linha(nome, cor, pct, valor, qtd):
        pct_txt = f"{pct:.2f}%".replace(".", ",")
        return (
            f'<div style="display:flex;align-items:center;gap:8px;margin:5px 0;font-size:13px">'
            f'<span style="width:10px;height:10px;border-radius:2px;background:{cor};flex-shrink:0"></span>'
            f'<span style="flex:1">{nome} <span style="opacity:.7;font-size:12px">· {qtd} tít.</span></span>'
            f'<span style="color:{cor};font-weight:600">{pct_txt}</span>'
            f'<span style="min-width:92px;text-align:right">{_formatar_numero(valor)}</span></div>'
        )
    corpo = (
        '<div style="display:flex;align-items:center;gap:16px;padding:6px 0 4px">'
        '<div style="position:relative;width:104px;height:104px;flex-shrink:0">'
        f'<div class="an-rosca" style="width:104px;height:104px;border-radius:50%;'
        f'background:conic-gradient({cor_av} 0deg {graus:.2f}deg,{cor_v} {graus:.2f}deg 360deg);'
        '-webkit-mask:radial-gradient(farthest-side,transparent 60%,black 60%);'
        'mask:radial-gradient(farthest-side,transparent 60%,black 60%)"></div>'
        '<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">'
        f'<span style="font-size:14px;font-weight:600">{pct_av_txt}</span>'
        '<span style="font-size:10px;opacity:.7">a vencer</span></div></div>'
        '<div style="flex:1;min-width:0">'
        + linha("A vencer", cor_av, pct_av, a_vencer, qtd_a_vencer)
        + linha("Vencido", cor_v, pct_v, vencido, qtd_vencidos)
        + '</div></div>'
    )
    return _bloco("Situação dos títulos", "R$", _COR_MI, "", corpo, total, ocultar=False).replace("Total em reais", "Total em aberto")


def _painel_situacao_titulos_imagem(a_vencer, vencido, qtd_a_vencer, qtd_vencidos) -> dict:
    a_vencer, vencido = max(float(a_vencer or 0), 0.0), max(float(vencido or 0), 0.0)
    pct_av = a_vencer / ((a_vencer + vencido) or 1) * 100
    return {
        "tipo": "rosca", "titulo": "Situação dos títulos",
        "centro_texto": f"{pct_av:.2f}%".replace(".", ","),
        "fatias": [
            {"label": f"A vencer ({qtd_a_vencer} tít.)", "valor": a_vencer, "cor": (27, 175, 122),
             "texto": _formatar_numero(a_vencer)},
            {"label": f"Vencido ({qtd_vencidos} tít.)", "valor": vencido, "cor": (226, 75, 74),
             "texto": _formatar_numero(vencido)},
        ],
        "total_rotulo": "Total em aberto", "total_texto": _formatar_moeda(a_vencer + vencido),
    }


def _dados_aging(df_cliente: pd.DataFrame) -> dict:
    """Aging do cliente no mesmo padrão da Visão Geral do Contas a Receber:
    faixas de vencimento, empilhadas por moeda (vencido em vermelho).
    Devolve {"faixas": [(rótulo, [(valor, cor_hex)], total)], "legenda": [(nome, cor_hex)], "total"}."""
    d = df_cliente.copy()
    d["DIAS"] = pd.to_numeric(d["DIAS"], errors="coerce")
    d["SALDO_EM_ABERTO"] = pd.to_numeric(d["SALDO_EM_ABERTO"], errors="coerce").fillna(0)
    d = d[d["DIAS"].notna()]
    moedas = sorted(m for m in d["MOEDA"].dropna().unique() if m != "R$") if "MOEDA" in d.columns else []
    cor_moeda = {m: _COR_MOEDA.get(m, "#D4537E") for m in moedas}
    cor_moeda["R$"] = _COR_COMPL if moedas else _COR_MI   # em reais: NF complementar (se houver moeda) ou azul

    faixas = []
    for i, (rotulo, ini, fim) in enumerate(_faixas(date.today())):
        sub = d[_na_faixa(d["DIAS"], ini, fim)]
        if i < 2:
            segmentos = [(float(sub["SALDO_EM_ABERTO"].sum()), _COR_VENCIDO)]
        elif "MOEDA" in sub.columns:
            segmentos = [
                (float(sub.loc[sub["MOEDA"] == m, "SALDO_EM_ABERTO"].sum()), cor_moeda[m])
                for m in moedas + ["R$"]
            ]
        else:
            segmentos = [(float(sub["SALDO_EM_ABERTO"].sum()), _COR_MI)]
        faixas.append((rotulo, segmentos, sum(v for v, _ in segmentos)))

    legenda = [("Vencido", _COR_VENCIDO)] + [(_SIMBOLOS_MOEDA.get(m, m), cor_moeda[m]) for m in moedas]
    if not moedas:
        legenda.append(("R$", _COR_MI))
    elif (d["MOEDA"] == "R$").any():
        legenda.append(("NF Compl.", _COR_COMPL))
    return {"faixas": faixas, "legenda": legenda, "total": sum(t for _, _, t in faixas)}


def _html_aging(dados: dict) -> str:
    maximo = max((t for _, _, t in dados["faixas"]), default=0)
    corpo = ""
    for i, (rotulo, segmentos, total) in enumerate(dados["faixas"]):
        if i in (2, 6):
            corpo += _espaco()
        corpo += _linha(rotulo, segmentos, total, maximo, ocultar=False)
    return _bloco("Aging de vencimento", "R$", _COR_MI, _legenda(dados["legenda"]), corpo,
                  dados["total"], ocultar=False).replace("Total em reais", "Saldo em aberto")


def _aging_para_imagem(dados: dict) -> dict:
    """Mesmo aging no formato que a imagem para e-mail espera."""
    def rgb(cor):
        h = cor.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return {
        "titulo": "Aging de vencimento",
        "legenda": [(nome, rgb(cor)) for nome, cor in dados["legenda"]],
        "total_texto": _formatar_moeda(dados["total"]),
        "linhas": [
            {"label": rotulo, "segmentos": [(v, rgb(c)) for v, c in segmentos],
             "texto": _completo(total, False), "separador": i in (2, 6)}
            for i, (rotulo, segmentos, total) in enumerate(dados["faixas"])
        ],
    }


def _formatar_regra(tipo, perc) -> str:
    """"FINANCEIRO - 12,30%": tipo e percentual na mesma linha, percentual com 2 casas."""
    try:
        v = float(str(perc).replace("%", "").replace(",", ".").strip())
        perc_txt = f"{v:.2f}%".replace(".", ",")
    except ValueError:
        perc_txt = str(perc)
    return f"{str(tipo).strip()} - {perc_txt}"


def _regra_desconto(df_cr_sel: pd.DataFrame) -> str:
    if df_cr_sel.empty or not {"TIPO_REGRA", "PERC_REGRA"}.issubset(df_cr_sel.columns):
        return "Sem desconto"
    regras = (
        df_cr_sel.dropna(subset=["TIPO_REGRA", "PERC_REGRA"])
        .drop_duplicates(subset=["COD_CLIENTE"])
    ) if "COD_CLIENTE" in df_cr_sel.columns else df_cr_sel.dropna(subset=["TIPO_REGRA", "PERC_REGRA"])
    combinacoes = set(zip(regras["TIPO_REGRA"], regras["PERC_REGRA"]))
    if not combinacoes:
        return "Sem desconto"
    if len(combinacoes) > 1:
        return "Vários"
    tipo, perc = combinacoes.pop()
    return _formatar_regra(tipo, perc)


def _regra_do_cliente(df_cliente: pd.DataFrame, codigo_agente) -> str:
    """Regra do card: a dos títulos em aberto; sem títulos (ou sem regra neles), a do cadastro do cliente."""
    regra = _regra_desconto(df_cliente)
    if regra != "Sem desconto":
        return regra
    try:
        cadastro = carregar_regra_desconto_cliente(int(codigo_agente))
    except (TypeError, ValueError):
        return regra
    return _formatar_regra(*cadastro) if cadastro else regra


def render(
    df_contas_receber: pd.DataFrame,
    df_grupo_agentes: pd.DataFrame,
    df_grupo_geral: pd.DataFrame = None,
    df_faturado: pd.DataFrame = None,
    carregar_adiantamento=None,
) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Situação Cliente")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="sc_atualizar", use_container_width=True):
            if "sc_cliente_cod" in st.session_state:
                st.session_state["_sc_cliente_cod_bkp"] = st.session_state["sc_cliente_cod"]
            st.cache_data.clear()
            st.rerun()

    if "_sc_cliente_cod_bkp" in st.session_state:
        st.session_state["sc_cliente_cod"] = st.session_state.pop("_sc_cliente_cod_bkp")

    if df_contas_receber.empty:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return

    df_base = df_contas_receber.copy()

    # ── Busca de cliente ──────────────────────────────────────────────────────
    # Clientes com título em aberto + todos os que existem no Grupo de Crédito e no
    # faturamento, para também dar para consultar quem não tem nada em aberto.
    nomes = {}  # código (texto) -> nome; o nome do Contas a Receber tem prioridade.
    if not df_grupo_agentes.empty and {"COD_AGENTE", "NOME_AGENTE"}.issubset(df_grupo_agentes.columns):
        for cod, nome in zip(df_grupo_agentes["COD_AGENTE"], df_grupo_agentes["NOME_AGENTE"]):
            nomes[str(cod)] = str(nome).strip()
    if df_faturado is not None and not df_faturado.empty and {"COD_CLIENTE", "CLIENTE"}.issubset(df_faturado.columns):
        for cod, nome in zip(df_faturado["COD_CLIENTE"], df_faturado["CLIENTE"]):
            nomes[str(cod)] = str(nome).strip()
    if {"COD_CLIENTE", "CLIENTE"}.issubset(df_base.columns):
        for cod, nome in zip(df_base["COD_CLIENTE"], df_base["CLIENTE"]):
            if pd.notna(cod) and pd.notna(nome):
                nomes[str(cod)] = str(nome).strip()

    codigos = sorted(nomes, key=lambda c: nomes[c].upper())
    codigo_agente = st.selectbox(
        "Cliente:",
        codigos,
        index=None,
        format_func=lambda cod: f"{nomes[cod]} - {cod}",
        placeholder="Buscar cliente por código ou nome...",
        key="sc_cliente_cod",
    )

    if codigo_agente is None:
        st.info("Selecione um cliente para visualizar.")
        return

    cliente_sel = nomes[codigo_agente]
    df_cliente = df_base[df_base["COD_CLIENTE"].astype(str) == codigo_agente].copy()         if "COD_CLIENTE" in df_base.columns else df_base.iloc[0:0].copy()

    # Busca a situação (bloqueado/ativo/etc.) do grupo ao qual esse cliente pertence,
    # cruzando o código numérico com a base de Saldo por Agente do Grupo de Crédito.
    situacao_cliente = "-"
    cor_situacao = "#6366f1"
    if df_grupo_geral is not None and not df_grupo_geral.empty and codigo_agente != "-" \
       and not df_grupo_agentes.empty and "COD_AGENTE" in df_grupo_agentes.columns:
        match_agente = df_grupo_agentes[
            df_grupo_agentes["COD_AGENTE"].astype(str) == codigo_agente
        ]
        if not match_agente.empty and "COD_GRUPO" in match_agente.columns:
            cod_grupo_agente = match_agente.iloc[0]["COD_GRUPO"]
            match_grupo = df_grupo_geral[df_grupo_geral["GRUPO_CODIGO"] == cod_grupo_agente]
            if not match_grupo.empty and "SITUACAO_CLIENTE" in match_grupo.columns:
                situacao_cliente = str(match_grupo.iloc[0]["SITUACAO_CLIENTE"] or "-").strip()
                _situacao_upper = situacao_cliente.upper()
                if any(t in _situacao_upper for t in ("BLOQ", "INADIMPL", "SUSPENS")):
                    cor_situacao = "#E24B4A"
                elif any(t in _situacao_upper for t in ("ATIVO", "OK", "LIBERADO", "NORMAL")):
                    cor_situacao = "#22c55e"

    # ── Métricas de resumo ───────────────────────────────────────────────────
    total_vencido = df_cliente.loc[df_cliente["SITUACAO"] == "VENCIDO", "SALDO_EM_ABERTO"].sum() \
        if "SITUACAO" in df_cliente.columns else 0
    total_a_vencer = df_cliente.loc[df_cliente["SITUACAO"] == "A VENCER", "SALDO_EM_ABERTO"].sum() \
        if "SITUACAO" in df_cliente.columns else 0
    saldo_total = df_cliente["SALDO_EM_ABERTO"].sum() if "SALDO_EM_ABERTO" in df_cliente.columns else 0

    qtd_titulos_abertos = len(df_cliente)
    qtd_titulos_vencidos = len(df_cliente[df_cliente["SITUACAO"] == "VENCIDO"]) \
        if "SITUACAO" in df_cliente.columns else 0

    # % Inadimplência: do que está em aberto HOJE (não do faturado histórico),
    # quanto já está vencido.
    pct_inadimplencia = (total_vencido / saldo_total * 100) if saldo_total else 0.0
    cor_inadimplencia = "#22c55e" if pct_inadimplencia < 5 else "#EF9F27" if pct_inadimplencia < 15 else "#E24B4A"

    if df_cliente.empty:
        st.info("Sem títulos em aberto para este cliente. "
                 "Use \"Adiantamento recebido em aberto\" abaixo se quiser conferir adiantamentos.")

    # Moedas estrangeiras dos títulos em aberto do cliente (mercado externo).
    moedas_cliente = []
    if "MOEDA" in df_cliente.columns and "SALDO_MOEDA" in df_cliente.columns:
        moedas_cliente = sorted(
            m for m in df_cliente["MOEDA"].dropna().unique() if m != "R$"
        )

    st.subheader(f"CLIENTE - {cliente_sel}{sufixo_mercado(df_cliente)}")

    # ── Cards de resumo ─────────────────────────────────────────────────────
    # Títulos em reais do cliente (notas de complemento): não têm valor na moeda estrangeira.
    saldo_em_reais = 0.0
    if moedas_cliente:
        em_reais = df_cliente[~df_cliente["MOEDA"].isin(moedas_cliente)]
        saldo_em_reais = float(em_reais["SALDO_EM_ABERTO"].sum())

    _card_base = partial(card_html, largura="100%", altura="112px", padding="14px 12px", topo=True)

    def _card_sc(label, valor, **kw):
        """Valor com fonte que encolhe até caber na largura do card (tela pequena), sem cortar o texto. Se o valor tem
        quebra de linha (<br>), conta só a linha mais longa."""
        if not kw.get("subtitulo"):
            kw["subtitulo"] = "&nbsp;"   # reserva a linha: o valor fica na mesma altura em todos os cards
        if "tamanho_valor" not in kw:
            linhas = re.sub(r"<[^>]+>", "", str(valor).replace("<br>", "|")).split("|")
            kw["tamanho_valor"] = tamanho_auto(max(linhas, key=len), max_px=26, min_px=13, fator=0.53, reserva=30)
        return _card_base(label, valor, **kw)

    # Placeholder no topo para o spinner de adiantamento (preenchido quando o botão é clicado).
    _adto_top = st.empty()

    # Adiantamento: consulta Oracle às vezes lenta (função por linha), então só roda
    # quando o usuário pede — não trava o carregamento normal da tela.
    chave_adto = f"_sc_adto_{codigo_agente}"
    valor_adto = _formatar_moeda(st.session_state[chave_adto]) if chave_adto in st.session_state else "—"
    chave_btn_adto = f"sc_carregar_adto_{codigo_agente}"

    # Grade de 4 cards por linha, em qualquer tamanho de tela: saldo (um card por moeda estrangeira e o total em R$, este
    # com a quantidade de títulos em aberto), a vencer, vencido (cada um com a sua quantidade), inadimplência, adiantamento
    # (botão preso ao próprio card), situação documental, status e, só no Mercado Interno, a regra de desconto.
    _qtd_a_vencer = int((df_cliente["SITUACAO"] == "A VENCER").sum()) if "SITUACAO" in df_cliente.columns else 0
    _so_externo = sufixo_mercado(df_cliente) == " - Mercado Externo"
    _sit_fat_val, _sit_fat_sub, _sit_fat_cor = situacao_faturamento(df_cliente)

    # Status ("Faturamento Bloqueado"): numa linha só quando o card tem largura; em duas linhas, na fonte normal, só quando
    # o card fica estreito (janela pequena). A quebra e a linha em branco do subtítulo dependem da largura do card (CSS).
    _status_1_linha = re.sub(r"<[^>]+>", "", _sit_fat_val.replace("<br>", " "))
    st.markdown(
        "<style>@container (min-width: 275px){.sc-br{display:none}}"
        "@container (max-width: 274px){.sc-subv{display:none}}</style>",
        unsafe_allow_html=True,
    )
    _card_status = _card_sc(
        "Status", _sit_fat_val.replace("<br>", " <br class='sc-br'>"),
        subtitulo=_sit_fat_sub or "<span class='sc-subv'>&nbsp;</span>", cor_borda=_sit_fat_cor,
        tamanho_valor=tamanho_auto(_status_1_linha, max_px=26, min_px=22, fator=0.53, reserva=30),
    )

    _slots = []
    for m in moedas_cliente:
        d = df_cliente[df_cliente["MOEDA"] == m]
        _slots.append(_card_sc(
            f"Total em Aberto {_SIMBOLOS_MOEDA.get(m, m)}",
            f"{_SIMBOLOS_MOEDA.get(m, m)} {_formatar_numero(d['SALDO_MOEDA'].sum())}",
            subtitulo=f"{len(d)} título(s)", cor_borda="#4A7FB5",
        ))
    _slots += [
        _card_sc("Total em Aberto R$", _formatar_moeda(saldo_total), subtitulo=f"{qtd_titulos_abertos} título(s)", cor_borda="#6366f1"),
        _card_sc("Total a Vencer", _formatar_moeda(total_a_vencer), subtitulo=f"{_qtd_a_vencer} título(s)", cor_borda="#22c55e"),
        _card_sc("Total Vencido", _formatar_moeda(total_vencido), subtitulo=f"{qtd_titulos_vencidos} título(s)", cor_borda="#E24B4A"),
        _card_sc("% Inadimplência", f"{pct_inadimplencia:.2f}%".replace(".", ","), cor_borda=cor_inadimplencia),
        "ADIANTAMENTO",
        _card_sc("Situação Documental", situacao_cliente.capitalize(), cor_borda=cor_situacao),
        _card_status,
    ]
    if not _so_externo:   # a regra de desconto e as notas pendentes de validação só existem no Mercado Interno
        _slots.append(card_pendencias([codigo_agente], _card_sc))
        _regra_desc = _regra_do_cliente(df_cliente, codigo_agente)
        _slots.append(_card_sc("Regra de Desconto", _regra_desc, cor_borda="#8B5CF6"))   # numa linha só: a fonte se ajusta

    def _card_adiantamento():
        with st.container(key="sc_adto_wrap"):
            st.markdown(_card_sc(
                "<span style='display:inline-block;padding-right:24px;box-sizing:border-box;'>"
                "Adiantamento em Aberto</span>",
                valor_adto, cor_borda="#2ECC71",
            ), unsafe_allow_html=True)
            st.markdown(
                f"<style>div[class*='st-key-sc_adto_wrap'] {{ position:relative !important; }}"
                f"div[class*='st-key-{chave_btn_adto}'] {{"
                f" position:absolute !important; top:10px !important; right:10px !important;"
                f" margin:0 !important; width:28px !important; max-width:28px !important; z-index:10; }}"
                f"div[class*='st-key-{chave_btn_adto}'] button {{"
                f" width:28px; height:28px; padding:0; min-height:0; border-radius:6px;"
                f" background-color:#1E88E5; border-color:#1E88E5; color:#ffffff; }}"
                f"div[class*='st-key-{chave_btn_adto}'] button:hover {{"
                f" background-color:#1669B3; border-color:#1669B3; color:#ffffff; }}</style>",
                unsafe_allow_html=True,
            )
            if st.button("", icon=":material/refresh:", key=chave_btn_adto,
                         help="Carregar adiantamento", disabled=carregar_adiantamento is None):
                _adto_top.info("⏳ Consultando adiantamento...")
                df_adiantamento = carregar_adiantamento()
                _adto_top.empty()
                st.session_state[chave_adto] = float(
                    _adiantamento_recebido_por_agente(df_adiantamento).get(str(codigo_agente), 0.0)
                )
                st.rerun()

    for _ini in range(0, len(_slots), 4):
        if _ini:
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        for _col, _slot in zip(st.columns(4), _slots[_ini:_ini + 4]):
            with _col:
                if _slot == "ADIANTAMENTO":
                    _card_adiantamento()
                else:
                    st.markdown(_slot, unsafe_allow_html=True)
    adiantamento_recebido = st.session_state.get(chave_adto)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    st.divider()

    # ── Aging de vencimento (barras) ─────────────────────────────────────────
    st.subheader("Aging de Vencimento")
    # Cliente do Mercado Interno com nota pendente de validação: o gráfico das notas entra numa terceira coluna, ao lado do aging
    _html_pend = None if _so_externo else html_notas_pendentes(codigo_agente)
    if _html_pend:
        col_aging, col_sit, col_pend = st.columns([1, 0.9, 0.9])
    else:
        col_aging, col_sit = st.columns([1, 0.9])
    _sit_col = df_cliente["SITUACAO"] if "SITUACAO" in df_cliente.columns else pd.Series(dtype=object)
    qtd_titulos_a_vencer = int((_sit_col == "A VENCER").sum())

    with col_aging:
        if df_cliente.empty:
            st.info("Sem títulos em aberto para montar o aging.")
        else:
            st.html(_html_aging(_dados_aging(df_cliente)))
    with col_sit:
        if not df_cliente.empty:
            st.html(_html_situacao_titulos(total_a_vencer, total_vencido, qtd_titulos_a_vencer, qtd_titulos_vencidos))
    if _html_pend:
        with col_pend:
            st.html(_html_pend)

    st.divider()

    # ── Tabela de títulos do cliente (sempre "Em Aberto" — base rápida) ──────
    st.subheader(f"Títulos do Cliente — {codigo_agente} — {cliente_sel}")

    if "SALDO_EM_ABERTO" in df_cliente.columns:
        df_titulos = df_cliente[df_cliente["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    else:
        df_titulos = df_cliente.copy()

    # Imagem: os mesmos cards da tela, na mesma ordem e em 4 por linha.
    cards_para_imagem = []
    for m in moedas_cliente:
        d = df_cliente[df_cliente["MOEDA"] == m]
        cards_para_imagem.append({
            "label": f"Total em Aberto {_SIMBOLOS_MOEDA.get(m, m)}",
            "valor": f"{_SIMBOLOS_MOEDA.get(m, m)} {_formatar_numero(d['SALDO_MOEDA'].sum())}",
            "cor": (55, 138, 221),
        })
    cards_para_imagem += [
        {"label": "Total em Aberto R$", "valor": _formatar_moeda(saldo_total), "sub": f"{qtd_titulos_abertos} título(s)", "cor": (99, 102, 241)},
        {"label": "Total a Vencer", "valor": _formatar_moeda(total_a_vencer), "sub": f"{_qtd_a_vencer} título(s)", "cor": (34, 197, 94)},
        {"label": "Total Vencido", "valor": _formatar_moeda(total_vencido), "sub": f"{qtd_titulos_vencidos} título(s)", "cor": (226, 75, 74)},
        {"label": "% Inadimplência", "valor": f"{pct_inadimplencia:.2f}%".replace(".", ","), "cor": (226, 75, 74)},
        {"label": "Adiantamento em Aberto", "valor": valor_adto, "cor": (46, 204, 113)},
        {"label": "Situação Documental", "valor": situacao_cliente.capitalize(), "cor": (99, 102, 241)},
        {"label": "Status", "valor": _sit_fat_val.replace("<br>", chr(10)), "cor": (226, 75, 74) if "Bloqueado" in _sit_fat_val else (34, 197, 94)},
    ]
    if not _so_externo:
        cards_para_imagem.append({"label": "Regra de Desconto", "valor": _regra_desc, "cor": (139, 92, 246)})

    if df_titulos.empty:
        st.success("Nenhum título em aberto para este cliente.")
        # Sem títulos: a imagem leva os cards e o faturamento por ano (sem aging nem tabela).
        imagem_vazia = _gerar_imagem_situacao_cached(
            codigo_agente, cliente_sel, cards_para_imagem, pd.DataFrame(),
            mensagem_vazia="Nenhum título em aberto para este cliente.",
            cards_por_linha=4,
        )
        botoes_acao_row(
            imagem={"data": imagem_vazia, "file_name": f"Situacao_{cliente_sel}.png", "key": "sc_export_imagem_vazio"},
            copiar={"data": imagem_vazia, "key": "sc_copiar_vazio"},
        )
    else:
        colunas_exibir = {            
            "CLIENTE":          "Cliente",
            "NF":               "NF",
            "PARCELA":          "Parcela",
            "LIQUIDO_FIN":      "Valor Total",
            "SALDO_EM_ABERTO":  "Saldo em Aberto",
            "MOEDA":            "Moeda",
            "COTACAO":          "Cotação",
            "SALDO_MOEDA":      "Saldo em Aberto (Moeda)",
            "ENTRADA":           "Entrada",
            "VENCIMENTO":       "Vencimento",
            "PRORROGADO":       "Prorrogado",
            "PRAZO":            "Prazo",
            "DIAS_VENCIDO":      "Dias Vencto.",
            "SITUACAO":         "Situação Vencto.",
            "CLASSIFICACAO":    "Classificação",
            "COMPLEMENTO":      "Complemento",    # sempre a última coluna (tela, planilha e imagem)

        }
        # Colunas de moeda só aparecem para clientes com moeda estrangeira.
        if not moedas_cliente:
            for c in ("MOEDA", "COTACAO", "SALDO_MOEDA"):
                colunas_exibir.pop(c, None)
        # Prazo = vencimento - entrada, em dias.
        if {"ENTRADA", "VENCIMENTO"}.issubset(df_titulos.columns):
            df_titulos["PRAZO"] = (
                pd.to_datetime(df_titulos["VENCIMENTO"], errors="coerce")
                - pd.to_datetime(df_titulos["ENTRADA"], errors="coerce")
            ).dt.days
        # Títulos em reais (sem conversão): cotação 1,0000 e valor na moeda 0,00, só na tabela.
        if {"MOEDA", "COTACAO", "SALDO_MOEDA"}.issubset(df_titulos.columns):
            em_reais_tab = df_titulos["MOEDA"] == "R$"
            df_titulos.loc[em_reais_tab, "COTACAO"] = df_titulos.loc[em_reais_tab, "COTACAO"].fillna(1.0)
            df_titulos.loc[em_reais_tab, "SALDO_MOEDA"] = df_titulos.loc[em_reais_tab, "SALDO_MOEDA"].fillna(0.0)
        df_titulos = calcular_dias_prazo(df_titulos)
        colunas_existentes = [c for c in colunas_exibir if c in df_titulos.columns]
        df_exib = df_titulos[colunas_existentes].copy()
        if "CLASSIFICACAO" in df_exib.columns:
            df_exib["CLASSIFICACAO"] = df_exib["CLASSIFICACAO"].fillna("")
        if "COMPLEMENTO" in df_exib.columns:
            # em uma linha só; vazio vira "-"
            df_exib["COMPLEMENTO"] = (df_exib["COMPLEMENTO"].fillna("").astype(str)
                                      .str.replace(r"\s+", " ", regex=True).str.strip().replace("", "-"))

        # Base para o Excel: datas e valores reais (não texto), cotação com 4 casas.
        df_excel = df_exib.copy()
        for col in ["ENTRADA", "VENCIMENTO", "PRORROGADO"]:
            if col in df_excel.columns:
                df_excel[col] = pd.to_datetime(df_excel[col], errors="coerce")
        for col in ["LIQUIDO_FIN", "SALDO_EM_ABERTO", "COTACAO", "SALDO_MOEDA"]:
            if col in df_excel.columns:
                df_excel[col] = pd.to_numeric(df_excel[col], errors="coerce")
        df_excel = df_excel.rename(columns=colunas_exibir)

        for col in ["ENTRADA", "VENCIMENTO", "PRORROGADO"]:
            if col in df_exib.columns:
                df_exib[col] = pd.to_datetime(df_exib[col], errors="coerce").dt.strftime("%d/%m/%Y")

        if "DIAS_VENCIDO" in df_exib.columns and "SITUACAO" in df_exib.columns:
            df_exib["DIAS_VENCIDO"] = df_exib.apply(formatar_dias_unificado_html, axis=1)
        if "PRAZO" in df_exib.columns:
            df_exib["PRAZO"] = df_exib["PRAZO"].apply(
                lambda v: f"{int(v)} dias" if pd.notna(v) else ""
            )
        for col in ["LIQUIDO_FIN", "SALDO_EM_ABERTO"]:
            if col in df_exib.columns:
                df_exib[col] = df_exib[col].apply(_formatar_moeda)
        if "COTACAO" in df_exib.columns:
            df_exib["COTACAO"] = df_exib["COTACAO"].apply(_formatar_cotacao)
        if "SALDO_MOEDA" in df_exib.columns:
            df_exib["SALDO_MOEDA"] = df_exib["SALDO_MOEDA"].apply(_formatar_numero)

        df_exib = df_exib.rename(columns=colunas_exibir)

        render_tabela_html(df_exib, coluna_situacao="Situação Vencto.", coluna_complemento="Complemento")

        st.markdown("---")

        arquivo_excel = exportar_excel(df_excel, "SITUACAO_CLIENTE",
                                      colunas_situacao=("Situação Vencto.",),
                                      colunas_centralizar=("Dias Vencto.",),
                                      colunas_verde_vermelho=("Dias Vencto.",),
                                      titulo_planilha=f"Títulos do Cliente — {codigo_agente} — {cliente_sel}")
        _codigos_nota = (
            df_grupo_agentes.loc[df_grupo_agentes["COD_GRUPO"] == df_grupo_agentes.loc[
                df_grupo_agentes["COD_AGENTE"].astype(str) == str(codigo_agente), "COD_GRUPO"
            ].values[0], "COD_AGENTE"].astype(str).tolist()
            if df_grupo_agentes is not None and not df_grupo_agentes.empty
            and "COD_AGENTE" in df_grupo_agentes.columns and "COD_GRUPO" in df_grupo_agentes.columns
            and (df_grupo_agentes["COD_AGENTE"].astype(str) == str(codigo_agente)).any()
            else [str(codigo_agente)]
        )
        imagem_png = _gerar_imagem_situacao_cached(
            codigo_agente, cliente_sel, cards_para_imagem,
            texto_dias_para_imagem(df_exib, df_titulos, {"Dias Vencto.": "DIAS_VENCIDO"}),
            paineis=[
                (lambda ag: {"titulo": ag["titulo"], "legenda": ag["legenda"], "linhas": ag["linhas"],
                             "total_rotulo": "Saldo em aberto", "total_texto": ag["total_texto"]})(
                    _aging_para_imagem(_dados_aging(df_cliente))),
                _painel_situacao_titulos_imagem(total_a_vencer, total_vencido, qtd_titulos_a_vencer, qtd_titulos_vencidos),
            ],
            max_linhas_tabela=_MAX_LINHAS_IMAGEM,
            cards_por_linha=4,
            nota_rodape=_texto_representatividade(df_contas_receber, _codigos_nota),
        )
        botoes_acao_row(
            excel={"data": arquivo_excel, "file_name": f"Situacao_{cliente_sel}.xlsx", "key": "sc_export"},
            imagem={"data": imagem_png, "file_name": f"Situacao_{cliente_sel}.png", "key": "sc_export_imagem"},
            copiar={"data": imagem_png, "key": "sc_copiar"},
        )
