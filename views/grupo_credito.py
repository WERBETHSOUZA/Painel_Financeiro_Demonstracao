import streamlit as st
import pandas as pd
from components.buttons import botao_exportar_excel, botoes_acao_row
from components.cards import card_html, render_cards_row, render_tabela_html, situacao_faturamento
from utils.exporters import exportar_excel
from utils.imagem_email import gerar_imagem_resumo_titulos
from views.contas_receber_painel import _COR_MI, _bloco

# A imagem para e-mail (Pillow, pixel a pixel) é cara de gerar — sem cache ela era
# refeita em TODO rerun da página (qualquer clique em qualquer lugar do app), o que
# deixava a tela lenta mesmo sem o usuário pedir a imagem. Com cache, só é gerada de
# novo quando os dados do grupo mudam.
_gerar_imagem_grupo_cached = st.cache_data(show_spinner=False, max_entries=50)(gerar_imagem_resumo_titulos)


# ── Formatação ────────────────────────────────────────────────────────────────

def _formatar_moeda(valor) -> str:
    try:
        v = float(valor)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def _formatar_numero(valor) -> str:
    try:
        v = float(valor)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "0,00"


def html_situacao_limite(limite_total, disponivel, nf, pv, titulo="Situação do limite") -> str:
    if not limite_total:
        return _bloco(titulo, "R$", _COR_MI, "",
                      '<div style="padding:30px 0">Sem limite cadastrado.</div>', 0.0,
                      ocultar=False).replace("Total em reais", "Limite total")
    fatias = [("Disponível", disponivel, "#22c55e"), ("Consumido em NF", nf, "#E24B4A"),
              ("Consumido em PV", pv, "#4A7FB5")]
    fatias = [(n, max(v, 0.0), c) for n, v, c in fatias]
    soma = sum(v for _, v, _ in fatias) or 1.0
    ini, partes, legenda = 0.0, [], ""
    for nome, valor, cor in fatias:
        fim = ini + valor / soma * 360
        partes.append(f"{cor} {ini:.2f}deg {fim:.2f}deg")
        ini = fim
        legenda += (
            f'<div style="display:flex;align-items:center;gap:8px;margin:5px 0;font-size:13px">'
            f'<span style="width:10px;height:10px;border-radius:2px;background:{cor};flex-shrink:0"></span>'
            f'<span style="flex:1">{nome}</span>'
            f'<span style="color:{cor};font-weight:600">{f"{valor / soma * 100:.2f}".replace(".", ",")}%</span>'
            f'<span style="min-width:92px;text-align:right">{_formatar_numero(valor)}</span></div>'
        )
    pct_util = (nf + pv) / limite_total * 100
    corpo = (
        '<div style="display:flex;align-items:center;gap:16px;padding:6px 0 4px">'
        '<div style="position:relative;width:96px;height:96px;flex-shrink:0">'
        f'<div class="an-rosca" style="width:96px;height:96px;border-radius:50%;background:conic-gradient({",".join(partes)});'
        '-webkit-mask:radial-gradient(farthest-side,transparent 60%,black 60%);'
        'mask:radial-gradient(farthest-side,transparent 60%,black 60%)"></div>'
        '<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">'
        f'<span style="font-size:13px;font-weight:600">{f"{pct_util:.2f}".replace(".", ",")}%</span>'
        '<span style="font-size:10px;opacity:.7">utilizado</span></div></div>'
        f'<div style="flex:1;min-width:0">{legenda}</div></div>'
    )
    return _bloco(titulo, "R$", _COR_MI, "", corpo, limite_total,
                  ocultar=False, abreviar=False).replace("Total em reais", "Limite total")


def _dados_consumo_por_cliente(df_clientes: pd.DataFrame, top: int = 5):
    """([(nome, nf, pv)] dos maiores consumidores + 'Outros', total consumido) ou None."""
    if df_clientes is None or df_clientes.empty or not {"NOME_AGENTE", "CONSUMIDO_EM_NF", "CONSUMIDO_EM_PV"}.issubset(df_clientes.columns):
        return None
    d = df_clientes[["NOME_AGENTE", "CONSUMIDO_EM_NF", "CONSUMIDO_EM_PV"]].copy()
    d["NF"] = pd.to_numeric(d["CONSUMIDO_EM_NF"], errors="coerce").fillna(0.0)
    d["PV"] = pd.to_numeric(d["CONSUMIDO_EM_PV"], errors="coerce").fillna(0.0)
    d["TOT"] = d["NF"] + d["PV"]
    d = d[d["TOT"] > 0].sort_values("TOT", ascending=False)
    if d.empty:
        return None
    linhas = [(str(r.NOME_AGENTE), float(r.NF), float(r.PV)) for r in d.head(top).itertuples()]
    resto = d.iloc[top:]
    if not resto.empty:
        linhas.append((f"Outros ({len(resto)} clientes)", float(resto["NF"].sum()), float(resto["PV"].sum())))
    return linhas, float(d["TOT"].sum())


def _html_consumo_por_cliente(df_clientes: pd.DataFrame, limite_total: float, top: int = 5) -> str:
    """Barra por cliente do grupo, empilhada em NF e PV, com o % do limite do grupo."""
    tit = "Consumo do limite por cliente"
    dados = _dados_consumo_por_cliente(df_clientes, top)
    if dados is None:
        return _bloco(tit, "R$ · NF + PV", _COR_MI, "",
                      '<div style="padding:30px 0">Sem consumo de limite no grupo.</div>', 0.0,
                      ocultar=False).replace("Total em reais", "Total consumido")
    linhas, total = dados
    maximo = max(nf + pv for _, nf, pv in linhas) or 1.0
    legenda = (
        '<div style="display:flex;gap:12px;font-size:12px;opacity:.75;margin:0 0 6px">'
        '<span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#E24B4A;margin-right:4px"></span>NF</span>'
        '<span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:#4A7FB5;margin-right:4px"></span>PV</span>'
        '<span style="margin-left:auto">% do limite do grupo</span></div>'
    )
    corpo = ""
    for nome, nf, pv in linhas:
        tot = nf + pv
        largura = tot / maximo * 100
        pct_nf = nf / tot * 100 if tot else 0
        pct_lim = f"{tot / limite_total * 100:.2f}%".replace(".", ",") if limite_total else "—"
        corpo += (
            '<div style="display:grid;grid-template-columns:minmax(110px,1.2fr) minmax(0,2.4fr) 44px 92px;'
            'gap:8px;align-items:center;padding:3px 0;font-size:13px">'
            f'<span title="{nome}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{nome}</span>'
            '<div style="height:14px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div class="an-wipe" style="width:{largura:.1f}%;height:100%;display:flex">'
            f'<i style="display:block;width:{pct_nf:.1f}%;background:#E24B4A"></i>'
            f'<i style="display:block;width:{100 - pct_nf:.1f}%;background:#4A7FB5"></i></div></div>'
            f'<span style="text-align:right;opacity:.75;font-size:12px">{pct_lim}</span>'
            f'<span style="text-align:right">{_formatar_numero(tot)}</span></div>'
        )
    return _bloco(tit, "R$ · NF + PV", _COR_MI, legenda, corpo, total, ocultar=False).replace("Total em reais", "Total consumido")


def _paineis_para_imagem(limite_total, disponivel, nf, pv, df_clientes_num, pct_utilizado) -> list:
    paineis = [{
        "tipo": "rosca", "titulo": "Gráfico do limite de crédito",
        "centro_texto": f"{pct_utilizado:.2f}%".replace(".", ","),
        "fatias": [
            {"label": "Disponível", "valor": disponivel, "cor": (34, 197, 94), "texto": _formatar_numero(disponivel)},
            {"label": "Consumido em NF", "valor": nf, "cor": (226, 75, 74), "texto": _formatar_numero(nf)},
            {"label": "Consumido em PV", "valor": pv, "cor": (74, 127, 181), "texto": _formatar_numero(pv)},
        ],
        "total_rotulo": "Limite total", "total_texto": _formatar_moeda(limite_total),
    }]
    dados = _dados_consumo_por_cliente(df_clientes_num)
    if dados:
        linhas, total = dados
        paineis.append({
            "titulo": "Consumo do limite por cliente",
            "legenda": [("NF", (226, 75, 74)), ("PV", (74, 127, 181))],
            "larg_rotulo": 170,
            "linhas": [
                {"label": nome, "segmentos": [(n, (226, 75, 74)), (v, (74, 127, 181))],
                 "texto": f"{(n + v) / limite_total * 100:.2f}%  {_formatar_numero(n + v)}".replace(".", ",", 1)
                 if limite_total else _formatar_numero(n + v)}
                for nome, n, v in linhas
            ],
            "total_rotulo": "Total consumido", "total_texto": _formatar_moeda(total),
        })
    return paineis


# ── Entry point ───────────────────────────────────────────────────────────────

def _adiantamento_recebido_por_agente(df_adiantamento) -> dict:
    """Saldo em aberto de adiantamentos RECEBIDOS, somado por código de agente."""
    if df_adiantamento is None or df_adiantamento.empty:
        return {}
    if not {"NATUREZA", "COD_CLIENTE", "SALDO"}.issubset(df_adiantamento.columns):
        return {}
    recebidos = df_adiantamento[df_adiantamento["NATUREZA"].astype(str).str.upper() == "RECEBIDO"]
    saldo = pd.to_numeric(recebidos["SALDO"], errors="coerce").fillna(0)
    return saldo.groupby(recebidos["COD_CLIENTE"].astype(str)).sum().to_dict()


def _texto_representatividade(df_cr, codigos_clientes: list) -> str | None:
    """Texto plano de representatividade do grupo (para imagem/Excel — sem HTML)."""
    if df_cr is None or df_cr.empty or "SALDO_EM_ABERTO" not in df_cr.columns or "COD_CLIENTE" not in df_cr.columns:
        return None
    df_grupo = df_cr[df_cr["COD_CLIENTE"].astype(str).isin(codigos_clientes)]
    if df_grupo.empty:
        return None
    partes = []
    if "MERCADO" in df_cr.columns:
        for cod, rotulo in (("MI", "mercado interno"), ("ME", "mercado externo")):
            grupo_saldo = float(df_grupo[df_grupo["MERCADO"] == cod]["SALDO_EM_ABERTO"].sum())
            if grupo_saldo <= 0:
                continue
            total_m = float(df_cr[df_cr["MERCADO"] == cod]["SALDO_EM_ABERTO"].sum())
            if not total_m:
                continue
            partes.append(f"{grupo_saldo / total_m * 100:.2f}% do {rotulo}")
    else:
        total = float(df_cr["SALDO_EM_ABERTO"].sum())
        grupo_saldo = float(df_grupo["SALDO_EM_ABERTO"].sum())
        if total and grupo_saldo > 0:
            partes.append(f"{grupo_saldo / total * 100:.2f}%")
    if not partes:
        return None
    return "O saldo do grupo representa " + " e ".join(partes) + " do valor em aberto."


def _aviso_representatividade(df_cr, codigos_clientes: list) -> str | None:
    """Texto HTML de representatividade do grupo por mercado (MI e/ou ME). Retorna None se sem dados."""
    if df_cr is None or df_cr.empty or "SALDO_EM_ABERTO" not in df_cr.columns or "COD_CLIENTE" not in df_cr.columns:
        return None
    df_grupo = df_cr[df_cr["COD_CLIENTE"].astype(str).isin(codigos_clientes)]
    if df_grupo.empty:
        return None
    partes = []
    if "MERCADO" in df_cr.columns:
        for cod, rotulo in (("MI", "mercado interno"), ("ME", "mercado externo")):
            grupo_saldo = float(df_grupo[df_grupo["MERCADO"] == cod]["SALDO_EM_ABERTO"].sum())
            if grupo_saldo <= 0:
                continue
            total_m = float(df_cr[df_cr["MERCADO"] == cod]["SALDO_EM_ABERTO"].sum())
            if not total_m:
                continue
            partes.append(f"<b>{grupo_saldo / total_m * 100:.2f}%</b> do {rotulo}")
    else:
        total = float(df_cr["SALDO_EM_ABERTO"].sum())
        grupo_saldo = float(df_grupo["SALDO_EM_ABERTO"].sum())
        if total and grupo_saldo > 0:
            partes.append(f"<b>{grupo_saldo / total * 100:.2f}%</b>")
    if not partes:
        return None
    return "O saldo do grupo representa " + " e ".join(partes) + " do valor em aberto."


def render_conteudo(df_geral: pd.DataFrame, df_agentes: pd.DataFrame, carregar_adiantamento=None,
                    df_contas_receber=None) -> None:
    """Renderiza só o conteúdo (seletor + cards + gráfico + tabela), sem título.
    Use isto para embutir a tela como uma aba dentro de outra view."""
    if "_gc_grupo_sel_bkp" in st.session_state:
        st.session_state["gc_grupo_sel"] = st.session_state.pop("_gc_grupo_sel_bkp")

    if df_geral.empty:
        st.warning("Nenhum dado encontrado para Grupo de Crédito.")
        return

    # ── Seletor de grupo ─────────────────────────────────────────────────────
    if not df_agentes.empty and "COD_GRUPO" in df_agentes.columns:
        codigos_bra = set(df_agentes["COD_GRUPO"].dropna().unique())
        df_geral_bra = df_geral[df_geral["GRUPO_CODIGO"].isin(codigos_bra)]
    else:
        df_geral_bra = df_geral

    grupos = sorted(df_geral_bra["NOME_GRUPO"].dropna().unique())
    grupo_sel = st.selectbox(
        "Grupo:",
        grupos,
        index=None,
        placeholder="Selecione um grupo...",
        help="Selecione um grupo de crédito para ver o detalhamento.",
        key="gc_grupo_sel",
    )

    if grupo_sel is None:
        st.warning("Selecione o grupo para visualizar")
        return

    row = df_geral_bra[df_geral_bra["NOME_GRUPO"] == grupo_sel].iloc[0]
    codigo_grupo = row["GRUPO_CODIGO"]

    limite_total     = float(row["VALOR_LIMITE"] or 0)
    limite_disponivel = float(row["VALOR_DISPONIVEL"] or 0)
    consumido_nf      = float(row["VALOR_RECEBER_ABERTO"] or 0)
    consumido_pv      = float(row["VALOR_PEDIDO_ABERTO"] or 0)
    situacao_cliente  = str(row.get("SITUACAO_CLIENTE") or "-").strip()

    _situacao_upper = situacao_cliente.upper()
    if any(t in _situacao_upper for t in ("BLOQ", "INADIMPL", "SUSPENS")):
        cor_situacao = "#E24B4A"
    elif any(t in _situacao_upper for t in ("ATIVO", "OK", "LIBERADO", "NORMAL")):
        cor_situacao = "#22c55e"
    else:
        cor_situacao = "#6366f1"

    # Clientes (agentes) do grupo. Adiantamento Recebido não carrega automaticamente: a
    # consulta calcula o saldo com uma função de saldo por linha, que às
    # vezes demora muito ou falha — deixava a tela inteira travada por causa
    # de uma informação que não afeta limite/disponível/consumido/faturado. Agora só roda
    # quando o usuário clica em "Carregar adiantamento" (mesmo padrão da Situação Cliente).
    df_clientes = df_agentes[df_agentes["COD_GRUPO"] == codigo_grupo].copy()         if not df_agentes.empty and "COD_GRUPO" in df_agentes.columns else pd.DataFrame()

    # % do limite disponível/utilizado — mesma conta usada pelo gráfico de rosca.
    pct_disponivel = (limite_disponivel / limite_total * 100) if limite_total else 0.0
    pct_utilizado = 100 - pct_disponivel
    if pct_disponivel >= 40:
        cor_disponivel = "#22c55e"
        cor_fundo_disponivel = "#16261c"  # verde suave
    elif pct_disponivel >= 20:
        cor_disponivel = "#EF9F27"
        cor_fundo_disponivel = "#2b2313"  # âmbar suave
    else:
        cor_disponivel = "#E24B4A"
        cor_fundo_disponivel = "#2b1818"  # vermelho suave

    _aviso_adto = st.empty()

    # ── Cards ─────────────────────────────────────────────────────────────────
    # Só informação atual (o que precisamos analisar antes de faturar) — Adiantamento
    # e Faturado (histórico) saíram desta tela; o histórico foi para o relatório
    # "Faturamento por Cliente/Grupo".
    render_cards_row([
        card_html("Limite de crédito total", _formatar_moeda(limite_total), cor_borda="#6366f1"),
        card_html("Limite de crédito disponível", _formatar_moeda(limite_disponivel),
                  cor_borda=cor_disponivel, cor_fundo=cor_fundo_disponivel),
        card_html("Consumido em Nota Fiscal", _formatar_moeda(consumido_nf), cor_borda="#E24B4A"),
        card_html("Consumido em Pedido de Venda", _formatar_moeda(consumido_pv), cor_borda="#4A7FB5"),
        card_html("% do limite utilizado", f"{pct_utilizado:.2f}%".replace(".", ","),
                  cor_borda=cor_disponivel, cor_fundo=cor_fundo_disponivel),
    ])

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # Adiantamento recebido em aberto do grupo: soma o adiantamento de todos os
    # clientes (agentes) do grupo, só quando o usuário pede (ver comentário acima).
    chave_adto = f"_gc_adto_{codigo_grupo}"
    chave_btn_adto = f"gc_carregar_adto_{codigo_grupo}"
    valor_adto = _formatar_numero(st.session_state[chave_adto]) if chave_adto in st.session_state else "—"

    # Mesmo mecanismo (render_cards_row/card_html, largura fixa 240px + gap 12px) da
    # linha de cima, pra alinhar exatamente sob as mesmas colunas — st.columns usa
    # largura proporcional ao container e não bate com a grade de largura fixa.
    _cods_sit_fat = df_clientes["COD_AGENTE"].astype(str).tolist() if not df_clientes.empty else []
    _titulos_sit_fat = (df_contas_receber[df_contas_receber["COD_CLIENTE"].astype(str).isin(_cods_sit_fat)]
                        if df_contas_receber is not None and not df_contas_receber.empty
                        and "COD_CLIENTE" in df_contas_receber.columns else None)
    _sit_fat_val, _sit_fat_sub, _sit_fat_cor = situacao_faturamento(_titulos_sit_fat)
    render_cards_row([
        card_html("Situação Documental", situacao_cliente.capitalize(), cor_borda=cor_situacao, topo=True, padding="14px 20px"),
        card_html("Status", _sit_fat_val, subtitulo=_sit_fat_sub, cor_borda=_sit_fat_cor, topo=True, padding="14px 20px"),
        card_html(
            "<span style='display:inline-block;padding-right:32px;box-sizing:border-box;'>"
            "Adiantamento Recebido em Aberto</span>",
            valor_adto, cor_borda="#2ECC71", topo=True, padding="14px 20px",
        ),
    ])
    # Botão fica sobreposto no canto superior direito do card (não embaixo), em azul.
    st.markdown(
        f"<style>div[class*='st-key-{chave_btn_adto}'] {{"
        f" margin-left: 710px; margin-top: -110px; width: 28px; max-width: 28px; }}"
        f"div[class*='st-key-{chave_btn_adto}'] button {{"
        f" width: 28px; height: 28px; padding: 0; min-height: 0; border-radius: 6px;"
        f" background-color: #1E88E5; border-color: #1E88E5; color: #ffffff; }}"
        f"div[class*='st-key-{chave_btn_adto}'] button:hover {{"
        f" background-color: #1669B3; border-color: #1669B3; color: #ffffff; }}</style>",
        unsafe_allow_html=True,
    )
    if st.button("", icon=":material/refresh:", key=chave_btn_adto,
                 help="Carregar adiantamento", disabled=carregar_adiantamento is None):
        _aviso_adto.info("⏳ Consultando adiantamento...")
        df_adto = carregar_adiantamento()
        _aviso_adto.empty()
        mapa_adto = _adiantamento_recebido_por_agente(df_adto)
        codigos_grupo = df_clientes["COD_AGENTE"].astype(str).tolist() if not df_clientes.empty else []
        st.session_state[chave_adto] = float(sum(mapa_adto.get(cod, 0.0) for cod in codigos_grupo))
        st.rerun()

    # Compensa o margin-top negativo do botão (senão o divisor sobe junto e fica
    # sobreposto nos cards).
    st.markdown("<div style='height:110px;'></div>", unsafe_allow_html=True)

    # Aviso de representatividade do grupo por mercado.
    codigos_grupo = df_clientes["COD_AGENTE"].astype(str).tolist() if not df_clientes.empty else []
    aviso_rep = _aviso_representatividade(df_contas_receber, codigos_grupo)
    if aviso_rep is not None:
        st.markdown(
            f"<div style='background:rgba(239,159,39,0.12);border-left:3px solid #EF9F27;border-radius:6px;"
            f"padding:7px 12px;font-size:13px;color:#EF9F27;display:inline-block'>"
            f"{aviso_rep}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Gráfico do limite de crédito (painel compacto com rosca) ────────────
    _col_graf, _col_cons = st.columns([2, 3])
    with _col_graf:
        st.html(html_situacao_limite(limite_total, limite_disponivel, consumido_nf, consumido_pv,
                                     titulo="Gráfico do limite de crédito"))
    with _col_cons:
        st.html(_html_consumo_por_cliente(df_clientes, limite_total))

    st.divider()

    # ── Tabela de clientes do grupo (expansível) ────────────────────────────
    df_exib = pd.DataFrame()
    if not df_clientes.empty:
        df_clientes["TOTAL_CONSUMIDO"] = (
            df_clientes["CONSUMIDO_EM_PV"].fillna(0)
            + df_clientes["CONSUMIDO_EM_NF"].fillna(0)
        )
        # Quem mais consome o limite do grupo aparece primeiro.
        df_clientes = df_clientes.sort_values("TOTAL_CONSUMIDO", ascending=False)
        colunas_valor = ["CONSUMIDO_EM_PV", "CONSUMIDO_EM_NF", "TOTAL_CONSUMIDO"]
        df_clientes_num = df_clientes.copy()   # valores reais, para o Excel (número, não texto)
        for col in colunas_valor:
            if col in df_clientes_num.columns:
                df_clientes_num[col] = pd.to_numeric(df_clientes_num[col], errors="coerce").fillna(0.0)
        for col in colunas_valor:
            if col in df_clientes.columns:
                df_clientes[col] = df_clientes[col].apply(_formatar_numero)

        colunas_exibir = {
            "COD_AGENTE":       "Cód. Agente",
            "UF":               "ESTADO",
            "NOME_AGENTE":      "Cliente",
            "CONSUMIDO_EM_PV":  "PV",
            "CONSUMIDO_EM_NF":  "NF",
            "TOTAL_CONSUMIDO":  "Total",
        }
        colunas_existentes = [c for c in colunas_exibir if c in df_clientes.columns]
        df_exib = df_clientes[colunas_existentes].rename(columns=colunas_exibir)
        df_excel = df_clientes_num[colunas_existentes].rename(columns=colunas_exibir)

    with st.expander(f"Clientes do grupo {grupo_sel}", expanded=True):
        if df_exib.empty:
            st.info("Nenhum cliente encontrado para este grupo.")
        else:
            st.caption("PV, NF e Total = consumido do limite de crédito (R$)")
            render_tabela_html(df_exib)

            st.markdown("---")

            # Mesma cor de alerta do card na tela (verde/âmbar/vermelho conforme % disponível).
            cor_disponivel_rgb = (
                (34, 197, 94) if pct_disponivel >= 40
                else (239, 159, 39) if pct_disponivel >= 20
                else (226, 75, 74)
            )
            fundo_disponivel_rgb = (
                (224, 244, 231) if pct_disponivel >= 40
                else (250, 235, 210) if pct_disponivel >= 20
                else (250, 224, 222)
            )
            cards_para_imagem = [
                {"label": "Limite de crédito total", "valor": _formatar_moeda(limite_total), "cor": (99, 102, 241)},
                {"label": "Limite de crédito disponível", "valor": _formatar_moeda(limite_disponivel),
                 "cor": cor_disponivel_rgb, "fundo": fundo_disponivel_rgb},
                {"label": "Consumido em Nota Fiscal", "valor": _formatar_moeda(consumido_nf), "cor": (226, 75, 74)},
                {"label": "Consumido em Pedido de Venda", "valor": _formatar_moeda(consumido_pv), "cor": (74, 127, 181)},
                {"label": "% do limite utilizado", "valor": f"{pct_utilizado:.2f}%".replace(".", ","),
                 "cor": cor_disponivel_rgb, "fundo": fundo_disponivel_rgb},
                {"label": "Situação Documental", "valor": situacao_cliente.capitalize(), "cor": (99, 102, 241)},
                {"label": "Status", "valor": _sit_fat_val.replace("<br>", chr(10)), "cor": (226, 75, 74) if "Bloqueado" in _sit_fat_val else (34, 197, 94)},
            ]
            cards_para_imagem.append({
                "label": "Adiantamento Recebido em Aberto",
                "valor": valor_adto,
                "cor": (46, 204, 113),
            })

            arquivo_excel = exportar_excel(df_excel, "CLIENTES_GRUPO_CREDITO",
                                          colunas_moeda=("PV", "NF", "Total"))
            imagem_png = _gerar_imagem_grupo_cached(
                titulo_principal=f"Limite de Crédito — {grupo_sel}",
                cards_resumo=cards_para_imagem,
                df_titulos=df_exib,
                titulo_tabela=f"Clientes do grupo {grupo_sel}",
                destacar_vencidos=False,
                ordem_colunas=["Cliente", "Cód. Agente", "ESTADO", "PV", "NF", "Total"],
                paineis=_paineis_para_imagem(limite_total, limite_disponivel, consumido_nf, consumido_pv,
                                             df_clientes_num, pct_utilizado),
                nota_rodape=_texto_representatividade(df_contas_receber, codigos_grupo),
            )
            botoes_acao_row(
                excel={"data": arquivo_excel, "file_name": f"Clientes_{grupo_sel}.xlsx", "key": "gc_export_clientes"},
                imagem={"data": imagem_png, "file_name": f"Limite_Credito_{grupo_sel}.png", "key": "gc_export_imagem"},
                copiar={"data": imagem_png, "key": "gc_copiar"},
            )


def render(df_geral: pd.DataFrame, df_agentes: pd.DataFrame, carregar_adiantamento=None,
           df_contas_receber=None) -> None:
    """Renderiza a tela completa, com título — use isto se for uma página própria no menu."""
    if df_geral.empty:
        st.warning("Nenhum dado encontrado para Grupo de Crédito.")
        return

    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Grupo de Crédito")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="gc_atualizar", use_container_width=True):
            if "gc_grupo_sel" in st.session_state:
                st.session_state["_gc_grupo_sel_bkp"] = st.session_state["gc_grupo_sel"]
            st.cache_data.clear()
            st.rerun()

    render_conteudo(df_geral, df_agentes, carregar_adiantamento, df_contas_receber=df_contas_receber)
