"""
views/faturamento_cliente_grupo.py
====================================
Relatório "Faturamento - Cliente/Grupo": análise completa de um cliente ou
de um grupo econômico — limite de crédito, faturamento histórico, aging,
regra de desconto, e (só no modo Grupo) comparativo entre os clientes do
grupo e faturamento por estado (mapa). Exportação em Excel (gráficos nativos,
editáveis) e também em imagem/PNG (mesmo padrão de Situação Cliente e Grupo
de Crédito, pra colar em e-mail).
"""

from functools import partial

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel, botoes_acao_row
from components.cards import tamanho_auto, card_html, render_cards_row, render_tabela_html, situacao_faturamento
from utils.exporters import exportar_excel_faturamento_cliente_grupo
from utils.prazos import calcular_dias_prazo, formatar_dias_html, formatar_dias_unificado_html, nullar_zeros_dias, texto_dias_para_imagem, VERDE_DIAS, VERMELHO_DIAS
from utils.imagem_email import gerar_imagem_resumo_titulos
from views.contas_receber_painel import _COR_MI, _abrev, _bloco
from views.faturamento_ano import (_MESES, dados_faturamento_ano, dados_faturamento_mes, dados_variacao_anual,
                                   html_grafico_faturamento, html_grafico_faturamento_mes,
                                   html_variacao_anual, nota_faturamento, pontos_faturamento)
from views.grupo_credito import _adiantamento_recebido_por_agente, _texto_representatividade, html_situacao_limite
from views.situacao_cliente import _aging_para_imagem, _dados_aging, _formatar_regra, _html_aging, _SIMBOLOS_MOEDA

# Mesmo motivo do Grupo de Crédito/Situação Cliente: sem cache, a imagem (Pillow)
# era refeita em todo rerun da página, mesmo sem o usuário pedir.
_gerar_imagem_fcg_cached = st.cache_data(show_spinner=False, max_entries=50)(gerar_imagem_resumo_titulos)


def _formatar_moeda(valor) -> str:
    try:
        v = float(valor)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def _formatar_numero(valor, casas: int = 2) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _cor_alerta(pct_disponivel: float) -> str:
    if pct_disponivel >= 40:
        return "#22c55e"
    if pct_disponivel >= 20:
        return "#EF9F27"
    return "#E24B4A"


def _cor_situacao(situacao: str) -> str:
    s = (situacao or "").upper()
    if any(t in s for t in ("BLOQ", "INADIMPL", "SUSPENS")):
        return "#E24B4A"
    if any(t in s for t in ("ATIVO", "OK", "LIBERADO", "NORMAL")):
        return "#22c55e"
    return "#6366f1"


def _regra_desconto(df_cr_sel: pd.DataFrame) -> str:
    """Regra de desconto (Faturamento/Financeiro + %) do cliente, vinda do
    cadastro de regras do cliente — só existe nos títulos em aberto do
    cliente. Se houver mais de uma regra distinta na seleção (grupo com
    clientes diferentes), mostra "Vários". Sem título/regra = "Sem desconto"."""
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


def _limite_credito(codigo_grupo, df_geral: pd.DataFrame) -> dict:
    """Limite/disponível/situação do grupo (o limite é sempre do GRUPO econômico,
    nunca do cliente individual — um cliente sozinho usa o limite do grupo dele)."""
    vazio = {"limite_total": 0.0, "limite_disponivel": 0.0, "situacao": "-",
             "consumido_nf": 0.0, "consumido_pv": 0.0}
    if codigo_grupo is None or df_geral is None or df_geral.empty:
        return vazio
    match = df_geral[df_geral["GRUPO_CODIGO"] == codigo_grupo]
    if match.empty:
        return vazio
    row = match.iloc[0]
    return {
        "limite_total": float(row.get("VALOR_LIMITE") or 0),
        "limite_disponivel": float(row.get("VALOR_DISPONIVEL") or 0),
        "situacao": str(row.get("SITUACAO_CLIENTE") or "-").strip(),
        "consumido_nf": float(row.get("VALOR_RECEBER_ABERTO") or 0),
        "consumido_pv": float(row.get("VALOR_PEDIDO_ABERTO") or 0),
    }


_PALETA_UF = ["#E24B4A", "#BA7517", "#5b8bd9", "#1baf7a", "#8B5CF6", "#E8724A", "#378ADD", "#888780"]


def _dados_distribuicao_estado(df_cr_sel: pd.DataFrame, uf_map: dict, top=None):
    """([(uf, saldo, qtd)] ordenado, total) ou None quando não há saldo em aberto."""
    if df_cr_sel is None or df_cr_sel.empty or not {"COD_CLIENTE", "SALDO_EM_ABERTO"}.issubset(df_cr_sel.columns):
        return None
    d = df_cr_sel[df_cr_sel["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    if d.empty:
        return None
    d["_UF"] = d["COD_CLIENTE"].astype(str).map(uf_map).fillna("-")
    por_uf = (d.groupby("_UF").agg(SALDO=("SALDO_EM_ABERTO", "sum"), QTD=("SALDO_EM_ABERTO", "size"))
              .sort_values("SALDO", ascending=False))
    if top is None:   # tela: todos os estados (a lista rola); imagem: só os maiores
        top = len(por_uf)
    linhas = [(uf, float(r["SALDO"]), int(r["QTD"])) for uf, r in por_uf.head(top).iterrows()]
    resto = por_uf.iloc[top:]
    if len(resto) > 1:   # os menores viram uma linha só, para a imagem não crescer demais
        linhas.append((f"Outros ({len(resto)} estados)", float(resto["SALDO"].sum()), int(resto["QTD"].sum())))
    elif len(resto) == 1:
        linhas.append((resto.index[0], float(resto["SALDO"].iloc[0]), int(resto["QTD"].iloc[0])))
    return linhas, float(por_uf["SALDO"].sum())


def _cor_uf(i: int, rotulo: str) -> str:
    return "#888780" if str(rotulo).startswith("Outros") else _PALETA_UF[i % (len(_PALETA_UF) - 1)]


def _html_distribuicao_estado(df_cr_sel: pd.DataFrame, uf_map: dict) -> str:
    dados = _dados_distribuicao_estado(df_cr_sel, uf_map)
    if dados is None:
        return _bloco("Distribuição por Estado", "R$ · em aberto", _COR_MI, "",
                      '<div style="padding:30px 0">Sem títulos em aberto.</div>', 0.0,
                      ocultar=False).replace("Total em reais", "Saldo em aberto")
    linhas, total = dados
    total = total or 1.0
    barra, corpo_linhas = "", ""
    for i, (uf, saldo, qtd) in enumerate(linhas):
        cor = _cor_uf(i, uf)
        pct = saldo / total * 100
        barra += f'<div style="width:{pct:.2f}%;height:100%;background:{cor}"></div>'
        corpo_linhas += (
            f'<div style="display:flex;align-items:center;gap:8px;height:27px;box-sizing:border-box;font-size:13px">'
            f'<span style="width:10px;height:10px;border-radius:2px;background:{cor};flex-shrink:0"></span>'
            f'<span style="flex:1">{uf}</span>'
            f'<span style="opacity:.7;font-size:12px">{qtd} tít.</span>'
            f'<span style="color:{cor};font-weight:600;min-width:42px;text-align:right">{_pct1(pct)}</span>'
            f'<span style="min-width:72px;text-align:right">{_abrev(saldo, False)}</span></div>'
        )
    corpo = (f'<div style="height:8px;border-radius:4px;overflow:hidden;display:flex;margin:6px 0 8px">'
             f'<div class="an-wipe" style="display:flex;width:100%;height:100%">{barra}</div></div>'
             f'<div style="max-height:108px;overflow-y:auto;scrollbar-width:thin;padding-right:6px">{corpo_linhas}</div>')
    return _bloco("Distribuição por Estado", "R$ · em aberto", _COR_MI, "", corpo, total,
                  ocultar=False, abreviar=True).replace("Total em reais", "Saldo em aberto")


_card_topo = partial(card_html, topo=True, padding="14px 12px")


def _pct1(valor: float) -> str:
    return f"{valor:.2f}%".replace(".", ",")


def _rgb(hex_cor: str) -> tuple:
    h = hex_cor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _html_resumo_titulos(a_vencer, vencido, qtd_a_vencer, qtd_vencidos, regra_desconto=None) -> str:
    def linha(nome, cor, qtd, valor):
        return (
            f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">'
            f'<span style="width:10px;height:10px;border-radius:2px;background:{cor};flex-shrink:0"></span>'
            f'<span style="flex:1">{nome}</span>'
            f'<span style="opacity:.7;font-size:12px">{qtd} tít.</span>'
            f'<span style="min-width:72px;text-align:right">{_abrev(valor, False)}</span></div>'
        )
    corpo = linha("Total a Vencer", "#22c55e", qtd_a_vencer, a_vencer) + linha("Total Vencido", "#E24B4A", qtd_vencidos, vencido)
    if regra_desconto:
        corpo += (
            '<div style="display:flex;justify-content:space-between;gap:8px;padding:4px 0;font-size:13px">'
            f'<span>Regra de Desconto</span><span style="text-align:right">{regra_desconto}</span></div>'
        )
    return _bloco("Resumo de títulos", "R$", _COR_MI, "", corpo, a_vencer + vencido,
                  ocultar=False, abreviar=True).replace("Total em reais", "Total em aberto")


def render(
    df_cr: pd.DataFrame,
    df_fat: pd.DataFrame,
    df_geral: pd.DataFrame,
    df_agentes: pd.DataFrame,
    carregar_adiantamento=None,
    df_fat_mensal: pd.DataFrame = None,
) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Faturamento - Cliente/Grupo")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="fat_cg_atualizar", use_container_width=True):
            for k in ("fcg_modo", "fcg_grupo", "fcg_cliente"):
                if k in st.session_state:
                    st.session_state[f"_fcg_bkp_{k}"] = st.session_state[k]
            st.cache_data.clear()
            st.rerun()

    for k in ("fcg_modo", "fcg_grupo", "fcg_cliente"):
        bk = f"_fcg_bkp_{k}"
        if bk in st.session_state:
            st.session_state[k] = st.session_state.pop(bk)

    if df_agentes is None or df_agentes.empty:
        st.warning("Nenhum dado disponível.")
        return

    # ── Seletor de modo + busca (tela principal, igual ao Grupo de Crédito) ──
    nomes_agente = {}
    if {"COD_AGENTE", "NOME_AGENTE"}.issubset(df_agentes.columns):
        for cod, nome in zip(df_agentes["COD_AGENTE"], df_agentes["NOME_AGENTE"]):
            nomes_agente[str(cod)] = str(nome).strip()

    codigos_selecionados = []
    codigo_grupo = None
    titulo_escolhido = None

    col_modo, col_busca, _ = st.columns([1, 2, 5])
    with col_modo:
        modo = st.radio("Consultar por", ["Grupo", "Cliente"], horizontal=True, key="fcg_modo")

    if modo == "Cliente":
        codigos_disponiveis = sorted(nomes_agente, key=lambda c: nomes_agente[c].upper())
        with col_busca:
            codigo_cliente = st.selectbox(
                "Cliente:", codigos_disponiveis, index=None,
                format_func=lambda cod: f"{cod} - {nomes_agente[cod]}",
                placeholder="Buscar cliente por código ou nome...", key="fcg_cliente",
            )
        if codigo_cliente is not None:
            codigos_selecionados = [codigo_cliente]
            titulo_escolhido = f"CLIENTE - {nomes_agente[codigo_cliente]}"
            if "COD_GRUPO" in df_agentes.columns:
                match = df_agentes[df_agentes["COD_AGENTE"].astype(str) == codigo_cliente]
                if not match.empty:
                    codigo_grupo = match.iloc[0]["COD_GRUPO"]
    else:
        grupos_disponiveis = (
            sorted(df_geral[df_geral["GRUPO_CODIGO"].isin(df_agentes["COD_GRUPO"].dropna().unique())]["NOME_GRUPO"].dropna().unique())
            if df_geral is not None and not df_geral.empty and "COD_GRUPO" in df_agentes.columns
            else []
        )
        with col_busca:
            grupo_sel = st.selectbox(
                "Grupo:", grupos_disponiveis, index=None,
                placeholder="Selecione um grupo...", key="fcg_grupo",
            )
        if grupo_sel is not None:
            match_grupo = df_geral[df_geral["NOME_GRUPO"] == grupo_sel]
            if not match_grupo.empty:
                codigo_grupo = match_grupo.iloc[0]["GRUPO_CODIGO"]
                codigos_selecionados = (
                    df_agentes.loc[df_agentes["COD_GRUPO"] == codigo_grupo, "COD_AGENTE"]
                    .astype(str).tolist()
                )
                titulo_escolhido = f"GRUPO - {grupo_sel}"

    if not codigos_selecionados:
        st.info("Selecione um cliente ou um grupo acima para visualizar.")
        return

    eh_grupo = modo == "Grupo"
    codigos_str = [str(c) for c in codigos_selecionados]

    # ── Faturamento (histórico completo) ─────────────────────────────────────
    df_fat_sel = pd.DataFrame()
    if df_fat is not None and not df_fat.empty and "COD_CLIENTE" in df_fat.columns:
        df_fat_sel = df_fat[df_fat["COD_CLIENTE"].astype(str).isin(codigos_str)].copy()

    total_faturado = float(df_fat_sel["VALOR_TOTAL_FATURADO"].sum()) if not df_fat_sel.empty else 0.0

    # ── Títulos em aberto (Contas a Receber) ─────────────────────────────────
    df_cr_sel = pd.DataFrame()
    if df_cr is not None and not df_cr.empty and "COD_CLIENTE" in df_cr.columns:
        df_cr_sel = df_cr[df_cr["COD_CLIENTE"].astype(str).isin(codigos_str)].copy()

    # Mercado Externo tem particularidade própria (moeda estrangeira) — os cards
    # de saldo em moeda só aparecem quando existe título ME na seleção.
    tem_me = "MERCADO" in df_cr_sel.columns and (df_cr_sel["MERCADO"] == "ME").any()
    moedas_estrangeiras = (
        sorted(m for m in df_cr_sel["MOEDA"].dropna().unique() if m != "R$")
        if tem_me and "MOEDA" in df_cr_sel.columns else []
    )

    total_vencido = float(df_cr_sel.loc[df_cr_sel["SITUACAO"] == "VENCIDO", "SALDO_EM_ABERTO"].sum()) \
        if "SITUACAO" in df_cr_sel.columns else 0.0
    total_a_vencer = float(df_cr_sel.loc[df_cr_sel["SITUACAO"] == "A VENCER", "SALDO_EM_ABERTO"].sum()) \
        if "SITUACAO" in df_cr_sel.columns else 0.0
    total_em_aberto = total_vencido + total_a_vencer

    qtd_titulos_vencidos = int((df_cr_sel["SITUACAO"] == "VENCIDO").sum()) \
        if "SITUACAO" in df_cr_sel.columns else 0
    qtd_titulos_a_vencer = int((df_cr_sel["SITUACAO"] == "A VENCER").sum()) \
        if "SITUACAO" in df_cr_sel.columns else 0

    # % Inadimplência: do que está em aberto HOJE (não do faturado histórico),
    # quanto já está vencido.
    pct_inadimplencia = (total_vencido / total_em_aberto * 100) if total_em_aberto else 0.0
    cor_inadimplencia = "#22c55e" if pct_inadimplencia < 5 else "#EF9F27" if pct_inadimplencia < 15 else "#E24B4A"

    # ── Limite de crédito (sempre do grupo econômico) ────────────────────────
    limite = _limite_credito(codigo_grupo, df_geral)
    limite_total = limite["limite_total"]
    limite_disponivel = limite["limite_disponivel"]
    consumido_nf = limite["consumido_nf"]
    consumido_pv = limite["consumido_pv"]
    situacao_cliente = limite["situacao"]
    pct_disponivel = (limite_disponivel / limite_total * 100) if limite_total else 0.0
    pct_utilizado = 100 - pct_disponivel
    cor_disp = _cor_alerta(pct_disponivel)
    cor_fundo_disp = {"#22c55e": "#16261c", "#EF9F27": "#2b2313"}.get(cor_disp, "#2b1818")
    cor_sit = _cor_situacao(situacao_cliente)

    # Adiantamento recebido em aberto: consulta às vezes lenta/instável (função
    # por linha) — só roda quando o usuário pede (mesmo padrão da
    # Situação Cliente e do Grupo de Crédito), pra não travar a abertura da tela.
    chave_sel_adto = codigo_grupo if eh_grupo else codigos_str[0]
    chave_adto = f"_fcg_adto_{chave_sel_adto}"
    chave_btn_adto = f"fcg_carregar_adto_{chave_sel_adto}"
    adiantamento = st.session_state.get(chave_adto)

    # Regra de desconto é do CADASTRO DO CLIENTE (tabela de regras) — não
    # faz sentido resumir num grupo com vários clientes, então só aparece no
    # modo Cliente.
    regra_desconto = _regra_desconto(df_cr_sel) if not eh_grupo else None

    _aviso_adto = st.empty()

    st.subheader(titulo_escolhido)

    valor_adto_card = _formatar_numero(adiantamento) if adiantamento is not None else "—"
    valor_regra_card = None
    if regra_desconto is not None:
        # No card, "TIPO — 12.30%" vira duas linhas (tipo em cima, % embaixo, maior
        # que o padrão de subtítulo pra não ficar pequeno demais de ler);
        # "Vários"/"Sem desconto" não tem o que separar, fica como está.
        if " — " in regra_desconto:
            _tipo_regra, _perc_regra = regra_desconto.split(" — ", 1)
            valor_regra_card = (
                f"{_tipo_regra}<br>"
                f"<span style='font-size:22px;font-weight:400;'>{_perc_regra}</span>"
            )
        else:
            valor_regra_card = regra_desconto

    # ── Cards ─────────────────────────────────────────────────────────────────
    # Linha 1: limite de crédito e situação. Linha 2: financeiro e adiantamento.
    # Seis colunas nas duas linhas, para os cards terem sempre a mesma largura.
    _sit_fat_val, _sit_fat_sub, _sit_fat_cor = situacao_faturamento(df_cr_sel)
    _H = "112px"
    por_ano = dados_faturamento_ano(df_fat, codigos_selecionados)
    _n = 6   # sempre 6 colunas: o layout é o mesmo para todo cliente, com ou sem moeda estrangeira
    # Fonte única dos valores numéricos, ajustada ao maior texto (7 colunas ficam estreitas):
    # cresce até 26px e encolhe só quando o valor não cabe, sem cortar.
    _valores = [_formatar_moeda(v) for v in (limite_total, consumido_nf + consumido_pv, limite_disponivel,
                                             total_faturado, total_em_aberto, total_a_vencer, total_vencido)]
    _valores += [f"{_SIMBOLOS_MOEDA.get(m, m)} {_formatar_numero(df_cr_sel.loc[df_cr_sel['MOEDA'] == m, 'SALDO_MOEDA'].sum())}"
                 for m in moedas_estrangeiras]
    _card_num = partial(_card_topo, tamanho_valor=tamanho_auto(max(_valores, key=len), 26, fator=0.5))
    _l1 = st.columns(_n)
    with _l1[0]:
        st.markdown(_card_num("Limite Total", _formatar_moeda(limite_total),
                              cor_borda="#6366f1", largura="100%", altura=_H), unsafe_allow_html=True)
    with _l1[1]:
        st.markdown(_card_num("Limite Consumido NF + PV", _formatar_moeda(consumido_nf + consumido_pv),
                              cor_borda="#E24B4A", largura="100%", altura=_H),
                    unsafe_allow_html=True)
    with _l1[2]:
        st.markdown(_card_num("Limite Disponível", _formatar_moeda(limite_disponivel),
                              cor_borda=cor_disp, cor_fundo=cor_fundo_disp, largura="100%", altura=_H),
                    unsafe_allow_html=True)
    with _l1[3]:
        st.markdown(_card_num("% Limite Utilizado", f"{pct_utilizado:.2f}%".replace(".", ","),
                              cor_borda=cor_disp, cor_fundo=cor_fundo_disp, largura="100%", altura=_H),
                    unsafe_allow_html=True)
    with _l1[4]:
        st.markdown(_card_topo("Situação Documental", situacao_cliente.capitalize(),
                              cor_borda=cor_sit, largura="100%", altura=_H), unsafe_allow_html=True)
    with _l1[5]:
        st.markdown(_card_topo("Situação Faturamento", _sit_fat_val, subtitulo=_sit_fat_sub,
                              cor_borda=_sit_fat_cor, largura="100%", altura=_H),
                    unsafe_allow_html=True)

    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
    # Linha 2: saldo em aberto (na moeda estrangeira + em R$ quando for Mercado Externo),
    # a vencer, vencido, inadimplência e adiantamento. Linha 3: Total Faturado (e, se o
    # cliente tiver mais de uma moeda estrangeira, os saldos das demais moedas).
    _l2 = st.columns(_n)
    _moeda_principal = moedas_estrangeiras[0] if moedas_estrangeiras else None
    _outras_moedas = moedas_estrangeiras[1:]
    _o = 1 if _moeda_principal else 0

    def _saldo_moeda_card(_m):
        _simbolo = _SIMBOLOS_MOEDA.get(_m, _m)
        _saldo = df_cr_sel.loc[df_cr_sel["MOEDA"] == _m, "SALDO_MOEDA"].sum()
        return _card_num(f"Total em Aberto {_simbolo}", f"{_simbolo} {_formatar_numero(_saldo)}",
                         cor_borda="#4A7FB5", largura="100%", altura=_H)

    if _moeda_principal:
        with _l2[0]:
            st.markdown(_saldo_moeda_card(_moeda_principal), unsafe_allow_html=True)
    with _l2[_o]:
        st.markdown(_card_num("Total em Aberto R$" if _moeda_principal else "Total em Aberto",
                              _formatar_moeda(total_em_aberto),
                              cor_borda="#6366f1", largura="100%", altura=_H), unsafe_allow_html=True)
    with _l2[1 + _o]:
        st.markdown(_card_num("Total a Vencer", _formatar_moeda(total_a_vencer),
                              cor_borda="#22c55e", largura="100%", altura=_H), unsafe_allow_html=True)
    with _l2[2 + _o]:
        st.markdown(_card_num("Total Vencido", _formatar_moeda(total_vencido),
                              cor_borda="#E24B4A", largura="100%", altura=_H), unsafe_allow_html=True)
    with _l2[3 + _o]:
        st.markdown(_card_num("% Inadimplência", f"{pct_inadimplencia:.2f}%".replace(".", ","),
                              cor_borda=cor_inadimplencia, largura="100%", altura=_H), unsafe_allow_html=True)
    with _l2[4 + _o]:
        with st.container(key="fcg_adto_wrap"):
            st.markdown(_card_num(
                "<span style='display:inline-block;padding-right:24px;box-sizing:border-box;'>"
                "Adiantamento em Aberto</span>",
                valor_adto_card, cor_borda="#2ECC71", largura="100%", altura=_H), unsafe_allow_html=True)
            st.markdown(
                f"<style>div[class*='st-key-fcg_adto_wrap'] {{ position:relative !important; }}"
                f"div[class*='st-key-{chave_btn_adto}'] {{"
                f" position:absolute !important; top:10px !important; right:10px !important;"
                f" margin:0 !important; width:28px !important; max-width:28px !important; z-index:10; }}"
                f"div[class*='st-key-{chave_btn_adto}'] button {{"
                f" width:28px; height:28px; padding:0; min-height:0; border-radius:6px;"
                f" background-color:#1E88E5; border-color:#1E88E5; color:#ffffff; }}"
                f"div[class*='st-key-{chave_btn_adto}'] button:hover {{"
                f" background-color:#1669B3; border-color:#1669B3; color:#ffffff; }}"
                "div[class*='st-key-fcg_fat_wrap'] { position:relative !important; }"
                "div[class*='st-key-fcg_fat_modo'] { position:absolute !important; top:8px !important;"
                " right:14px !important; z-index:10; margin:0 !important; gap:6px !important; }"
                "div[class*='st-key-fcg_fat_modo'] { width:96px !important; }"
                "div[class*='st-key-fcg_fat_modo'] button { min-height:28px !important; padding:2px 8px !important; }"
                "div[class*='st-key-fcg_fat_modo'] button p { font-size:12px !important; }</style>",
                unsafe_allow_html=True,
            )
            if st.button("", icon=":material/refresh:", key=chave_btn_adto,
                         help="Carregar adiantamento", disabled=carregar_adiantamento is None):
                _aviso_adto.info("⏳ Consultando adiantamento...")
                df_adto = carregar_adiantamento()
                _aviso_adto.empty()
                mapa_adto = _adiantamento_recebido_por_agente(df_adto)
                st.session_state[chave_adto] = float(sum(mapa_adto.get(c, 0.0) for c in codigos_str))
                st.rerun()

    # Linha 3: demais moedas estrangeiras (se houver), depois o Total Faturado em faixa de
    # largura total (gráfico por ano, altura de um card).
    if _outras_moedas:
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        for _col, _m in zip(st.columns(max(_n, len(_outras_moedas))), _outras_moedas):
            with _col:
                st.markdown(_saldo_moeda_card(_m), unsafe_allow_html=True)
    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
    meses = dados_faturamento_mes(df_fat_mensal, codigos_selecionados)
    if por_ano:
        # O botão Por ano | Por mês fica dentro da faixa (canto superior direito): o contêiner é
        # relativo e o controle é posicionado por cima, sem ocupar espaço entre os cards.
        with st.container(key="fcg_fat_wrap"):
            _modo_fat = "Por ano"
            _faixa = st.empty()
            if meses:
                _modo_fat = st.session_state.get("fcg_fat_modo_sel", "Por ano")
                with st.container(key="fcg_fat_modo"):
                    for _rotulo, _chave in (("Por ano", "fcg_fat_btn_ano"), ("Por mês", "fcg_fat_btn_mes")):
                        if st.button(_rotulo, key=_chave, use_container_width=True,
                                     type="primary" if _modo_fat == _rotulo else "secondary"):
                            st.session_state["fcg_fat_modo_sel"] = _rotulo
                            st.rerun()
            if _modo_fat == "Por mês" and meses:
                _faixa.html(html_grafico_faturamento_mes(meses, com_botao=True))
            else:
                _faixa.html(html_grafico_faturamento(por_ano, total_faturado, com_botao=bool(meses)))
    else:
        st.markdown(_card_num("Total Faturado", _formatar_moeda(total_faturado),
                              cor_borda="#2E86AB", largura="100%", altura=_H), unsafe_allow_html=True)

    # Aviso de representatividade (apenas modo Grupo) — após todos os cards.
    if eh_grupo and df_cr is not None and not df_cr.empty and "SALDO_EM_ABERTO" in df_cr.columns and "COD_CLIENTE" in df_cr.columns:
        df_grupo_cr = df_cr[df_cr["COD_CLIENTE"].astype(str).isin(codigos_str)]
        if not df_grupo_cr.empty:
            partes_rep = []
            if "MERCADO" in df_cr.columns:
                for _cod, _rotulo in (("MI", "mercado interno"), ("ME", "mercado externo")):
                    _grupo_saldo = float(df_grupo_cr[df_grupo_cr["MERCADO"] == _cod]["SALDO_EM_ABERTO"].sum())
                    if _grupo_saldo <= 0:
                        continue
                    _total_m = float(df_cr[df_cr["MERCADO"] == _cod]["SALDO_EM_ABERTO"].sum())
                    if not _total_m:
                        continue
                    partes_rep.append(f"<b>{_grupo_saldo / _total_m * 100:.2f}%</b> do {_rotulo}")
            else:
                _total = float(df_cr["SALDO_EM_ABERTO"].sum())
                _gs = float(df_grupo_cr["SALDO_EM_ABERTO"].sum())
                if _total and _gs > 0:
                    partes_rep.append(f"<b>{_gs / _total * 100:.2f}%</b>")
            if partes_rep:
                _texto_rep = "O saldo do grupo representa " + " e ".join(partes_rep) + " do valor em aberto."
                st.markdown(
                    f"<div style='background:rgba(239,159,39,0.12);border-left:3px solid #EF9F27;border-radius:6px;"
                    f"padding:7px 12px;font-size:13px;color:#EF9F27;display:inline-block;margin-bottom:4px'>"
                    f"{_texto_rep}</div>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Gráficos ──────────────────────────────────────────────────────────────
    por_ano = dados_faturamento_ano(df_fat, codigos_selecionados)

    aging_dados = _dados_aging(df_cr_sel) if not df_cr_sel.empty else None

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    # Painéis numa grade só (e não em colunas separadas), para as bordas alinharem:
    # o aging ocupa as duas linhas; situação do limite e resumo ficam empilhados no meio
    # (a base do resumo coincide com a do aging) e a distribuição por estado fica ao lado
    # da situação do limite, com o mesmo topo e a mesma altura.
    _uf_map = {}
    if not df_agentes.empty and {"COD_AGENTE", "UF"}.issubset(df_agentes.columns):
        _uf_map = dict(zip(df_agentes["COD_AGENTE"].astype(str), df_agentes["UF"]))

    def _celula(html, coluna, linha):
        return f'<div style="display:grid;grid-column:{coluna};grid-row:{linha}">{html}</div>'

    def _centralizado(html):
        """Conteúdo do painel centralizado na vertical (o aging estica até a base do resumo)."""
        return html.replace('border-radius:12px;padding:12px 14px"',
                            'border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;justify-content:center"', 1)

    _aging_html = (_centralizado(_html_aging(aging_dados)) if aging_dados else
                   '<div style="padding:16px;border:1px solid rgba(128,128,128,0.3);border-radius:12px">'
                   'Sem títulos em aberto.</div>')
    st.html(
        '<div style="display:grid;grid-template-columns:1.3fr 0.9fr 1.1fr;gap:16px;align-items:stretch">'
        + _celula(_aging_html, 1, "1 / span 2")
        + _celula(html_situacao_limite(limite_total, limite_disponivel, consumido_nf, consumido_pv), 2, 1)
        + _celula(_html_resumo_titulos(total_a_vencer, total_vencido, qtd_titulos_a_vencer,
                                       qtd_titulos_vencidos, regra_desconto), 2, 2)
        + _celula(_html_distribuicao_estado(df_cr_sel, _uf_map), 3, 1)
        + _celula(html_variacao_anual(por_ano), 3, 2)
        + "</div>"
    )

    # ── Clientes do grupo (PV/NF/Total — consumo do limite de crédito) ───────
    # Mesmo dado do antigo relatório de Grupo de Crédito: um cliente por
    # linha, PV + NF = Total consumido do limite. Só existe (e só faz sentido) no
    # modo Grupo, exportado no Excel — não muda o que a tela já mostra.
    clientes_pv_nf = []
    df_pv_nf_tela = pd.DataFrame()
    if eh_grupo and not df_agentes.empty and {"COD_AGENTE", "NOME_AGENTE"}.issubset(df_agentes.columns):
        df_g = df_agentes[df_agentes["COD_AGENTE"].astype(str).isin(codigos_str)].copy()
        if not df_g.empty:
            df_g["CONSUMIDO_EM_PV"] = pd.to_numeric(df_g.get("CONSUMIDO_EM_PV"), errors="coerce").fillna(0.0)
            df_g["CONSUMIDO_EM_NF"] = pd.to_numeric(df_g.get("CONSUMIDO_EM_NF"), errors="coerce").fillna(0.0)
            df_g["TOTAL_CONSUMIDO"] = df_g["CONSUMIDO_EM_PV"] + df_g["CONSUMIDO_EM_NF"]
            df_g = df_g.sort_values("TOTAL_CONSUMIDO", ascending=False)
            clientes_pv_nf = list(zip(
                df_g["NOME_AGENTE"], df_g["COD_AGENTE"],
                df_g["CONSUMIDO_EM_PV"], df_g["CONSUMIDO_EM_NF"], df_g["TOTAL_CONSUMIDO"],
            ))
            df_pv_nf_tela = pd.DataFrame({
                "Cód. Agente": df_g["COD_AGENTE"].astype(str),
                "ESTADO": df_g["UF"] if "UF" in df_g.columns else "-",
                "Cliente": df_g["NOME_AGENTE"],
                "PV": df_g["CONSUMIDO_EM_PV"].apply(_formatar_numero),
                "NF": df_g["CONSUMIDO_EM_NF"].apply(_formatar_numero),
                "Total": df_g["TOTAL_CONSUMIDO"].apply(_formatar_numero),
            })

    # ── Gráficos exclusivos de Grupo ─────────────────────────────────────────
    clientes_grupo, por_estado = [], []
    if eh_grupo:
        if not df_fat_sel.empty and "COD_CLIENTE" in df_fat_sel.columns:
            por_cliente = df_fat_sel.groupby("COD_CLIENTE")["VALOR_TOTAL_FATURADO"].sum().sort_values(ascending=False)
            clientes_grupo = [
                (cod, nomes_agente.get(str(cod), str(cod)), float(valor)) for cod, valor in por_cliente.items()
            ]
        if clientes_grupo or (not df_agentes.empty and "UF" in df_agentes.columns):
            uf_por_agente = {}
            if {"COD_AGENTE", "UF"}.issubset(df_agentes.columns):
                uf_por_agente = dict(zip(df_agentes["COD_AGENTE"].astype(str), df_agentes["UF"]))
            if not df_fat_sel.empty and "COD_CLIENTE" in df_fat_sel.columns:
                f = df_fat_sel.copy()
                f["UF"] = f["COD_CLIENTE"].astype(str).map(uf_por_agente).fillna("-")
                por_uf = f.groupby("UF")["VALOR_TOTAL_FATURADO"].sum().sort_values(ascending=False)
                por_estado = [(uf, float(valor)) for uf, valor in por_uf.items()]

        if clientes_grupo or por_estado:
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            col_d, col_e = st.columns(2)
            with col_d:
                st.markdown("**Clientes do grupo (faturamento)**")
                if clientes_grupo:
                    maximo = max(v for _, _, v in clientes_grupo)
                    for _cod, nome, valor in clientes_grupo[:10]:
                        st.markdown(
                            f'<div style="display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(0,2.5fr) 72px;gap:10px;'
                            f'align-items:center;font-size:13px;padding:3px 0">'
                            f'<div title="{nome}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{nome}</div>'
                            f'<div style="height:16px;border-radius:3px;overflow:hidden;background:rgba(128,128,128,0.15)">'
                            f'<div class="an-wipe" style="width:{valor / maximo * 100 if maximo else 0:.1f}%;height:100%;background:#E8724A"></div></div>'
                            f'<div style="text-align:right;">{_abrev(valor, False)}</div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("Sem faturamento por cliente no período.")
            with col_e:
                st.markdown("**Faturamento por estado**")
                if por_estado:
                    maximo = max(v for _, v in por_estado)
                    for uf, valor in por_estado:
                        st.markdown(
                            f'<div style="display:grid;grid-template-columns:36px minmax(0,1fr) 72px;gap:10px;'
                            f'align-items:center;font-size:13px;padding:3px 0">'
                            f'<div>{uf}</div>'
                            f'<div style="height:16px;border-radius:3px;overflow:hidden;background:rgba(128,128,128,0.15)">'
                            f'<div class="an-wipe" style="width:{valor / maximo * 100 if maximo else 0:.1f}%;height:100%;background:{_COR_MI}"></div></div>'
                            f'<div style="text-align:right;">{_abrev(valor, False)}</div></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("Sem faturamento por estado no período.")

    # Consumo do limite de crédito por cliente do grupo (PV, NF e Total) — mesma
    # tabela do Grupo de Crédito, só no modo Grupo.
    if eh_grupo and not df_pv_nf_tela.empty:
        st.markdown("<div style='margin-top:-0.5rem'></div>", unsafe_allow_html=True)
        with st.expander(f"Clientes do grupo — consumo do limite de crédito", expanded=True):
            st.caption("PV, NF e Total = consumido do limite de crédito (R$)")
            render_tabela_html(df_pv_nf_tela)

    st.divider()

    # ── Tabela de títulos em aberto + Excel ──────────────────────────────────
    st.subheader("Títulos em Aberto")
    if not df_cr_sel.empty:
        df_cr_sel = calcular_dias_prazo(df_cr_sel)
    colunas_tabela = {
        "COD_CLIENTE": "Cód. Cliente", "CLIENTE": "Cliente", "NF": "NF", "SALDO_EM_ABERTO": "Saldo em Aberto",
        "MOEDA": "Moeda", "COTACAO": "Cotação", "SALDO_MOEDA": "Saldo (Moeda)",
        "VENCIMENTO": "Vencimento", "PRORROGADO": "Prorrogado", "DIAS_VENCIDO": "Dias Vencto.", "SITUACAO": "Situação Vencto.", "CLASSIFICACAO": "Classificação",
        "COMPLEMENTO": "Complemento",
    }

    # Moeda/Cotação/Saldo (Moeda) só fazem sentido quando existe título de Mercado
    # Externo na seleção — em Mercado Interno puro elas vêm sempre vazias (a
    # consulta zera esses campos quando Cotação = 1), então nem aparecem.
    colunas_moeda_estrangeira = ("MOEDA", "COTACAO", "SALDO_MOEDA")
    colunas_tabela_tela = colunas_tabela if tem_me else {
        k: v for k, v in colunas_tabela.items() if k not in colunas_moeda_estrangeira
    }

    if df_cr_sel.empty:
        st.success("Nenhum título em aberto.")
        df_tela = pd.DataFrame()
    else:
        colunas_existentes = [c for c in colunas_tabela_tela if c in df_cr_sel.columns]
        df_tela = df_cr_sel[colunas_existentes].copy()
        for _col_data in ("VENCIMENTO", "PRORROGADO"):
            if _col_data in df_tela.columns:
                df_tela[_col_data] = pd.to_datetime(df_tela[_col_data], errors="coerce").dt.strftime("%d/%m/%Y")
        if "DIAS_VENCIDO" in df_tela.columns and "SITUACAO" in df_tela.columns:
            df_tela["DIAS_VENCIDO"] = df_tela.apply(formatar_dias_unificado_html, axis=1)
        if "SALDO_EM_ABERTO" in df_tela.columns:
            df_tela["SALDO_EM_ABERTO"] = df_tela["SALDO_EM_ABERTO"].apply(_formatar_moeda)
        if "COTACAO" in df_tela.columns:
            df_tela["COTACAO"] = df_tela["COTACAO"].apply(lambda v: _formatar_numero(v, 4))
        df_tela = df_tela.rename(columns=colunas_tabela_tela)
        render_tabela_html(
            df_tela,
            coluna_situacao="Situação Vencto.",
            colunas_moeda=["Saldo em Aberto"],
        )

    kpis = [
        ("Limite Total", limite_total, "moeda"),
        ("Limite Disponível", limite_disponivel, "moeda"),
        ("% Limite Utilizado", pct_utilizado / 100, "percentual"),
        ("Situação Documental", situacao_cliente, "situacao"),
        ("Situação Faturamento", _sit_fat_val.split("<br>")[-1], "situacao"),
        ("Total Faturado", total_faturado, "moeda"),
        ("Total em Aberto", total_em_aberto, "moeda"),
        ("Total a Vencer", total_a_vencer, "moeda"),
        ("Total Vencido", total_vencido, "moeda"),
        ("% Inadimplência", pct_inadimplencia / 100, "percentual_alerta"),
    ]
    if adiantamento is not None:
        kpis.append(("Adiantamento em Aberto", adiantamento, "moeda"))
    if regra_desconto is not None:
        kpis.append(("Regra de Desconto", regra_desconto, "texto"))

    # Excel: colunas "cruas" da consulta (mesmos nomes/ordem confirmados pelo
    # usuário), sem renomear pra rótulo bonito — Mercado Externo entra com as
    # colunas de moeda estrangeira logo depois do Saldo em Aberto.
    _COLUNAS_TITULOS_RAW = ["NF", "COD_CLIENTE", "CLIENTE", "PARCELA", "TIPO_DOC", "VENCIMENTO", "PRORROGADO",
                            "DIAS_VENCIDO", "SITUACAO", "LIQUIDO_FIN", "SALDO_EM_ABERTO"]
    if tem_me:
        _COLUNAS_TITULOS_RAW += ["MOEDA", "VLR_PARCELA_MOEDA", "COTACAO", "SALDO_MOEDA"]
    _COLUNAS_TITULOS_RAW += ["CLASSIFICACAO", "SITUACAO_BOLETO", "COMPLEMENTO"]
    _RENOMEIA_TITULOS_RAW = {"DIAS_VENCIDO": "Dias Vencto."}

    if df_cr_sel.empty:
        df_titulos_excel = pd.DataFrame(columns=[_RENOMEIA_TITULOS_RAW.get(c, c) for c in _COLUNAS_TITULOS_RAW])
    else:
        colunas_existentes_raw = [c for c in _COLUNAS_TITULOS_RAW if c in df_cr_sel.columns]
        df_titulos_excel = df_cr_sel[colunas_existentes_raw].rename(columns=_RENOMEIA_TITULOS_RAW)

    _nota_repr = _texto_representatividade(df_cr, codigos_selecionados) if eh_grupo else None

    arquivo_excel = exportar_excel_faturamento_cliente_grupo(
        titulo=titulo_escolhido,
        kpis=kpis,
        faturamento_por_ano=por_ano,
        clientes_grupo=clientes_grupo if eh_grupo else None,
        por_estado=por_estado if eh_grupo else None,
        df_titulos=df_titulos_excel,
        clientes_pv_nf=clientes_pv_nf if eh_grupo else None,
        nota_rodape=_nota_repr,
    )

    # Imagem: os MESMOS cards e gráficos da tela (12 cards em 2 linhas de 6 + painéis).
    _cor_disp_rgb = _rgb(cor_disp)
    _fundo_disp_rgb = {"#22c55e": (224, 244, 231), "#EF9F27": (250, 235, 210)}.get(cor_disp, (250, 224, 222))
    cards_para_imagem = [
        {"label": "Limite Total", "valor": _formatar_moeda(limite_total), "cor": (99, 102, 241)},
        {"label": "Limite Consumido NF + PV", "valor": _formatar_moeda(consumido_nf + consumido_pv), "cor": (226, 75, 74)},
        {"label": "Limite Disponível", "valor": _formatar_moeda(limite_disponivel),
         "cor": _cor_disp_rgb, "fundo": _fundo_disp_rgb},
        {"label": "% Limite Utilizado", "valor": f"{pct_utilizado:.2f}%".replace(".", ","),
         "cor": _cor_disp_rgb, "fundo": _fundo_disp_rgb},
        {"label": "Situação Documental", "valor": situacao_cliente.capitalize(), "cor": _rgb(cor_sit)},
        {"label": "Situação Faturamento", "valor": _sit_fat_val.replace("<br>", chr(10)), "cor": _rgb(_sit_fat_cor)},
        *[{"label": f"Total em Aberto {_SIMBOLOS_MOEDA.get(m, m)}",
           "valor": f"{_SIMBOLOS_MOEDA.get(m, m)} {_formatar_numero(df_cr_sel.loc[df_cr_sel['MOEDA'] == m, 'SALDO_MOEDA'].sum())}",
           "cor": (55, 138, 221)} for m in moedas_estrangeiras[:1]],
        {"label": "Total em Aberto R$" if moedas_estrangeiras else "Total em Aberto",
         "valor": _formatar_moeda(total_em_aberto), "cor": (99, 102, 241)},
        {"label": "Total a Vencer", "valor": _formatar_moeda(total_a_vencer), "cor": (34, 197, 94)},
        {"label": "Total Vencido", "valor": _formatar_moeda(total_vencido), "cor": (226, 75, 74)},
        {"label": "% Inadimplência", "valor": f"{pct_inadimplencia:.2f}%".replace(".", ","), "cor": _rgb(cor_inadimplencia)},
        {"label": "Adiantamento em Aberto", "valor": valor_adto_card, "cor": (46, 204, 113)},
    ]
    while len(cards_para_imagem) % _n:
        cards_para_imagem.append(None)
    cards_para_imagem += [
        {"label": f"Total em Aberto {_SIMBOLOS_MOEDA.get(m, m)}",
         "valor": f"{_SIMBOLOS_MOEDA.get(m, m)} {_formatar_numero(df_cr_sel.loc[df_cr_sel['MOEDA'] == m, 'SALDO_MOEDA'].sum())}",
         "cor": (55, 138, 221)}
        for m in moedas_estrangeiras[1:]
    ]

    _verde, _verm = (34, 197, 94), (226, 75, 74)
    paineis_img = []
    if aging_dados:
        _ag = _aging_para_imagem(aging_dados)
        paineis_img.append({"titulo": _ag["titulo"], "legenda": _ag["legenda"], "linhas": _ag["linhas"],
                            "total_rotulo": "Saldo em aberto", "total_texto": _ag["total_texto"]})
    paineis_img.append({
        "tipo": "rosca", "titulo": "Situação do limite",
        "centro_texto": f"{pct_utilizado:.2f}%".replace(".", ","),
        "fatias": [
            {"label": "Disponível", "valor": limite_disponivel, "cor": _verde, "texto": _formatar_numero(limite_disponivel)},
            {"label": "Consumido em NF", "valor": consumido_nf, "cor": _verm, "texto": _formatar_numero(consumido_nf)},
            {"label": "Consumido em PV", "valor": consumido_pv, "cor": (74, 127, 181), "texto": _formatar_numero(consumido_pv)},
        ],
        "total_rotulo": "Limite total", "total_texto": _formatar_moeda(limite_total),
    })
    paineis_img.append({
        "titulo": "Resumo de títulos", "larg_rotulo": 120,
        "linhas": [
            {"label": "Total a Vencer", "segmentos": [(total_a_vencer, _verde)],
             "texto": f"{qtd_titulos_a_vencer} tít.  {_formatar_numero(total_a_vencer)}"},
            {"label": "Total Vencido", "segmentos": [(total_vencido, _verm)],
             "texto": f"{qtd_titulos_vencidos} tít.  {_formatar_numero(total_vencido)}"},
        ],
        "total_rotulo": "Total em aberto", "total_texto": _formatar_moeda(total_em_aberto),
        "nota": f"Regra de Desconto: {regra_desconto}" if regra_desconto else None,
    })
    _uf_map_img = {}
    if not df_agentes.empty and {"COD_AGENTE", "UF"}.issubset(df_agentes.columns):
        _uf_map_img = dict(zip(df_agentes["COD_AGENTE"].astype(str), df_agentes["UF"]))
    _dados_uf = _dados_distribuicao_estado(df_cr_sel, _uf_map_img, top=6)
    if _dados_uf:
        _linhas_uf, _total_uf = _dados_uf
        paineis_img.append({
            "titulo": "Distribuição por Estado", "larg_rotulo": 60,
            "linhas": [
                {"label": uf, "segmentos": [(saldo, _rgb(_cor_uf(i, uf)))],
                 "texto": f"{qtd} tít.  {_pct1(saldo / (_total_uf or 1) * 100)}  {_formatar_numero(saldo)}"}
                for i, (uf, saldo, qtd) in enumerate(_linhas_uf)
            ],
            "total_rotulo": "Saldo em aberto", "total_texto": _formatar_moeda(_total_uf),
        })
    if por_ano:
        _ano_atual = pd.Timestamp.today().year
        _pts = pontos_faturamento(por_ano)
        paineis_img.insert(0, {
            "tipo": "linha", "largura_total": True, "titulo": "Total Faturado",
            "total_texto": _formatar_moeda(total_faturado),
            "nota": f"por ano desde {_pts[0][0]}" + (f" · {_ano_atual} parcial" if _pts[-1][0] == _ano_atual else ""),
            "parcial": _pts[-1][0] == _ano_atual,
            "pontos": [(f"{ano}*" if ano == _ano_atual else str(ano), valor, _abrev(valor, False)) for ano, valor in _pts],
        })
    else:
        cards_para_imagem.append({"label": "Total Faturado", "valor": _formatar_moeda(total_faturado), "cor": (46, 134, 171)})
    _var = dados_variacao_anual(por_ano)
    if _var:
        _linhas_var, (_ano_melhor, _valor_melhor), _ = _var
        paineis_img.append({
            "titulo": "Variação anual", "larg_rotulo": 60,
            "linhas": [
                {"label": f"{ano}*" if parcial else str(ano),
                 "segmentos": [(valor, (127, 184, 209) if parcial else (46, 134, 171))],
                 "texto": (f"parcial  {_abrev(valor, False)}" if parcial else
                           (f"{var:+.2f}%".replace(".", ",") + f"  {_abrev(valor, False)}") if var is not None
                           else _abrev(valor, False))}
                for ano, valor, var, parcial in _linhas_var[:6]
            ],
            "total_rotulo": "Melhor ano", "total_texto": f"{_ano_melhor} · {_abrev(_valor_melhor, False)}",
        })
    if meses:
        _vermelho, _verde_v = (226, 75, 74), (34, 197, 94)
        _pontos = []
        for ano, mes, valor, var, parcial in meses:
            if not valor:
                _vt, _vc = "sem fat.", (140, 140, 140)
            elif var is None:
                _vt, _vc = ("parcial" if parcial else "-"), (140, 140, 140)
            else:
                _vt, _vc = f"{var:+.2f}%".replace(".", ","), (_verde_v if var >= 0 else _vermelho)
            _pontos.append((_MESES[mes - 1] + ("*" if parcial else ""), valor,
                            _abrev(valor, False) if valor else "", (_vt, _vc)))
        paineis_img.insert(1 if por_ano else 0, {
            "tipo": "linha", "largura_total": True, "titulo": "Faturado nos últimos 12 meses",
            "total_texto": _formatar_moeda(sum(m[2] for m in meses)),
            "nota": "% = vs. mesmo mês do ano anterior",
            "parcial": meses[-1][4],
            "pontos": _pontos,
        })
    if eh_grupo and clientes_grupo:
        paineis_img.append({
            "titulo": "Clientes do grupo (faturamento)", "larg_rotulo": 200,
            "linhas": [{"label": nome, "segmentos": [(valor, (232, 114, 74))], "texto": _formatar_moeda(valor)}
                       for _cod, nome, valor in clientes_grupo[:10]],
            "total_rotulo": "Total faturado", "total_texto": _formatar_moeda(sum(v for _, _, v in clientes_grupo)),
        })
    if eh_grupo and por_estado:
        paineis_img.append({
            "titulo": "Faturamento por estado", "larg_rotulo": 60,
            "linhas": [{"label": uf, "segmentos": [(valor, (29, 158, 117))], "texto": _formatar_moeda(valor)}
                       for uf, valor in por_estado],
            "total_rotulo": "Total faturado", "total_texto": _formatar_moeda(sum(v for _, v in por_estado)),
        })

    imagem_png = _gerar_imagem_fcg_cached(
        titulo_principal=titulo_escolhido,
        cards_resumo=cards_para_imagem,
        df_titulos=texto_dias_para_imagem(df_tela, df_cr_sel, {"Dias Vencto.": "DIAS_VENCIDO"}),
        titulo_tabela="Títulos em Aberto",
        ordem_colunas=list(colunas_tabela_tela.values()),
        mensagem_vazia="Nenhum título em aberto." if df_tela.empty else None,
        paineis=paineis_img,
        cards_por_linha=_n,
        nota_rodape=_nota_repr,
    )

    botoes_acao_row(
        excel={"data": arquivo_excel, "file_name": f"Faturamento_{titulo_escolhido}.xlsx".replace(" ", "_").replace("/", "-"), "key": "fcg_export"},
        imagem={"data": imagem_png, "file_name": f"Faturamento_{titulo_escolhido}.png".replace(" ", "_").replace("/", "-"), "key": "fcg_export_imagem"},
        copiar={"data": imagem_png, "key": "fcg_copiar"},
    )
