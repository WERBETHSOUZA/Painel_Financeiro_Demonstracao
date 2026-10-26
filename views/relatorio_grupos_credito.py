import streamlit as st
import pandas as pd
from datetime import datetime
from components.buttons import botoes_acao_row
from components.cards import card_html, render_cards_row, render_tabela_html, situacao_faturamento
from utils.exporters import exportar_excel_grupos_credito


def _fmt_moeda(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


_COR_VERDE    = "#22c55e"
_COR_VERMELHO = "#E24B4A"
_COR_AZUL     = "#4A7FB5"
_COR_LARANJA  = "#E8724A"
_COR_ROXO     = "#7B68B5"
_COR_CINZA    = "#6B7280"


def _badge(label: str, cor: str) -> str:
    return (
        f'<span style="background:{cor};color:#fff;border-radius:10px;'
        f'padding:2px 10px;font-size:12px;font-weight:600">{label}</span>'
    )


def _badge_doc(sit_doc: str) -> str:
    cor = _COR_VERMELHO if "BLOQ" in sit_doc.upper() else _COR_VERDE
    return _badge(sit_doc, cor)


def _badge_tipo(tipo: str) -> str:
    _mapa = {
        "Mercado Interno": (_COR_AZUL, "Mercado Interno"),
        "Mercado Externo": (_COR_ROXO, "Mercado Externo"),
        "MI":              (_COR_AZUL, "MI"),
        "ME":              (_COR_ROXO, "ME"),
    }
    partes = [t.strip() for t in tipo.split("/")]
    spans = []
    for p in partes:
        cor, label = _mapa.get(p, (_COR_CINZA, p))
        spans.append(f'<span style="color:{cor};font-weight:600">{label}</span>')
    return ' <span style="color:var(--text-muted)">/</span> '.join(spans)


def _mercado_grupo(df_cr: pd.DataFrame, codigos: list) -> str:
    if df_cr.empty or "MERCADO" not in df_cr.columns or "COD_CLIENTE" not in df_cr.columns:
        return "-"
    df_g = df_cr[df_cr["COD_CLIENTE"].astype(str).isin(codigos)]
    mercados = set(df_g["MERCADO"].dropna().str.strip().str.upper().unique())
    if "MI" in mercados and "ME" in mercados:
        return "MI/ME"
    if "ME" in mercados:
        return "ME"
    if "MI" in mercados:
        return "MI"
    return "-"


def _tipo_agente(tipo_pessoa: str, pais: str) -> str:
    _pais = str(pais or "BRA").strip().upper()
    if _pais not in ("BRA", ""):
        return "ME"
    return "MI"


def _tipo_grupo(df_gc_agentes: pd.DataFrame, cod: str) -> str:
    if df_gc_agentes.empty or "COD_GRUPO" not in df_gc_agentes.columns:
        return "-"
    df_g = df_gc_agentes[df_gc_agentes["COD_GRUPO"].astype(str) == cod]
    _pais_col = "PAIS" if "PAIS" in df_g.columns else None
    tipos = set()
    for _, r in df_g.iterrows():
        pais = str(r[_pais_col] or "BRA") if _pais_col else "BRA"
        tipos.add(_tipo_agente(r.get("TIPO_PESSOA", ""), pais))
    tipos.discard("-")
    if not tipos:
        return "-"
    tem_mi = "MI" in tipos
    tem_me = "ME" in tipos
    if tem_mi and tem_me:
        return "MI / ME"
    if tem_mi:
        return "Mercado Interno"
    if tem_me:
        return "Mercado Externo"
    return "-"


def _montar_df(df_gc_geral: pd.DataFrame, df_gc_agentes: pd.DataFrame, df_cr: pd.DataFrame):
    """Retorna (df_exib_html, df_export) onde df_exib_html tem badges HTML e
    df_export tem texto puro (para Excel/PNG)."""
    linhas_html = []
    linhas_exp  = []

    _tem_agentes = (
        not df_gc_agentes.empty
        and "COD_GRUPO"  in df_gc_agentes.columns
        and "COD_AGENTE" in df_gc_agentes.columns
    )

    for _, row in df_gc_geral.iterrows():
        cod    = str(row.get("GRUPO_CODIGO", "") or "").strip()
        nome   = str(row.get("NOME_GRUPO",   "") or "").strip()
        limite = float(row.get("VALOR_LIMITE",          0) or 0)
        nf     = float(row.get("VALOR_RECEBER_ABERTO",  0) or 0)
        pv     = float(row.get("VALOR_PEDIDO_ABERTO",   0) or 0)
        disp   = float(row.get("VALOR_DISPONIVEL",      0) or 0)
        pct    = (nf + pv) / limite * 100 if limite > 0 else 0.0
        sit_doc = str(row.get("SITUACAO_CLIENTE") or "-").strip().capitalize()

        if _tem_agentes:
            codigos = df_gc_agentes[df_gc_agentes["COD_GRUPO"].astype(str) == cod]["COD_AGENTE"].astype(str).tolist()
            df_grupo_cr = (
                df_cr[df_cr["COD_CLIENTE"].astype(str).isin(codigos)]
                if (not df_cr.empty and "COD_CLIENTE" in df_cr.columns)
                else pd.DataFrame()
            )
        else:
            codigos     = []
            df_grupo_cr = pd.DataFrame()

        _fat_val, _, _fat_cor = situacao_faturamento(df_grupo_cr)
        _fat_label = "Liberado" if "Liberado" in _fat_val else "Bloqueado"
        _doc_bloq  = "BLOQ" in sit_doc.upper()
        mercado    = _mercado_grupo(df_cr, codigos)
        tipo       = _tipo_grupo(df_gc_agentes, cod)

        if pct <= 0:
            _pct_html      = "—"
            _classif_label = "Livre"
            _cor_pct       = "#22c55e"
        else:
            _cor_pct = "#22c55e" if pct < 50 else "#EF9F27" if pct < 80 else "#E24B4A"
            _classif_label = "Livre" if pct < 50 else "Atenção" if pct < 80 else "Em Risco"
            _bar_w   = min(pct, 100)
            _pct_html = (
                f'<div style="display:flex;flex-direction:column;align-items:center;gap:3px">'
                f'<span style="color:{_cor_pct};font-weight:600">{pct:.2f}%</span>'
                f'<div style="width:72px;height:5px;border-radius:3px;background:#3a3a4a">'
                f'<div style="width:{_bar_w:.0f}%;height:5px;border-radius:3px;background:{_cor_pct}"></div>'
                f'</div></div>'
            )
        _classif_html = f'<span style="color:{_cor_pct};font-weight:600">{_classif_label}</span>'

        linhas_html.append({
            "Cód.":          cod,
            "Grupo":         nome,
            "Tipo":          _badge_tipo(tipo) if tipo != "-" else "—",
            "Limite":        _fmt_moeda(limite),
            "Consumido NF":  _fmt_moeda(nf),
            "Consumido PV":  _fmt_moeda(pv),
            "% Util.":        _pct_html,
            "Classificação":  _classif_html,
            "Disponível":     _fmt_moeda(disp),
            "Documentação":   _badge_doc(sit_doc),
            "Faturamento":    _badge(_fat_label, _fat_cor),
            "_fat_label":     _fat_label,
            "_doc_bloq":      _doc_bloq,
            "_mercado":       mercado,
            "_tipo":          tipo,
            "_pct":           pct,
        })
        linhas_exp.append({
            "Cód.":           cod,
            "Grupo":          nome,
            "Tipo":           tipo if tipo != "-" else "",
            "Limite":         limite,
            "Consumido NF":   nf,
            "Consumido PV":   pv,
            "% Util.":        round(pct, 4) / 100,
            "Classificação":  _classif_label,
            "Disponível":     disp,
            "Documentação":   sit_doc,
            "Faturamento":    _fat_label,
        })

    df_h = pd.DataFrame(linhas_html).sort_values("Grupo", ignore_index=True)
    df_e = pd.DataFrame(linhas_exp).sort_values("Grupo", ignore_index=True)
    return df_h, df_e


def render(df_gc_geral: pd.DataFrame, df_gc_agentes: pd.DataFrame, df_cr: pd.DataFrame):
    _col_tit, _col_btn = st.columns([8, 1], vertical_alignment="center")
    with _col_tit:
        st.title("Grupos de Crédito")
    with _col_btn:
        if st.button("🔄 Atualizar", key="rgc_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if df_gc_geral is None or df_gc_geral.empty:
        st.info("Sem dados disponíveis.")
        return

    df_html, df_exp = _montar_df(df_gc_geral, df_gc_agentes, df_cr)

    # ── Cards de resumo ──────────────────────────────────────────────────────
    total    = len(df_html)
    fat_lib  = int((df_html["_fat_label"] == "Liberado").sum())
    fat_blo  = int((df_html["_fat_label"] == "Bloqueado").sum())
    doc_blo  = int(df_html["_doc_bloq"].sum())
    em_risco = int((df_html["_pct"] > 80).sum())

    render_cards_row([
        card_html("Total de Grupos",    str(total),    cor_borda="#4A7FB5", largura="200px"),
        card_html("Fat. Liberado",      str(fat_lib),  cor_borda="#22c55e", largura="200px"),
        card_html("Fat. Bloqueado",     str(fat_blo),  cor_borda="#E24B4A", largura="200px"),
        card_html("Doc. Bloqueada",     str(doc_blo),  cor_borda="#BA7517", largura="200px"),
        card_html("Grupos em Risco >80%", str(em_risco), cor_borda="#E24B4A", largura="200px"),
    ])

    st.divider()

    # ── Filtros ───────────────────────────────────────────────────────────────
    col_titulo, col_busca, col_f1, col_f2, col_f3, col_f4, col_qtd = st.columns([2, 3, 2, 2, 2, 2, 1], vertical_alignment="center")
    with col_titulo:
        st.subheader("Grupos de Crédito")
    with col_busca:
        filtro_busca_sel = st.selectbox(
            "Grupo",
            sorted(df_html["Grupo"].dropna().unique().tolist()),
            index=None,
            placeholder="Todos",
            key="rgc_busca",
        )
    with col_f1:
        filtro_fat = st.selectbox(
            "Faturamento",
            ["Todos", "Liberado", "Bloqueado"],
            key="rgc_filtro_fat",
        )
    with col_f2:
        filtro_doc = st.selectbox(
            "Documentação",
            ["Todos", "Bloqueado", "Liberado"],
            key="rgc_filtro_doc",
        )
    with col_f3:
        filtro_util = st.selectbox(
            "% Utilização",
            ["Todos", "Em Risco (>80%)", "Atenção (50–80%)", "Livre (<50%)"],
            key="rgc_filtro_util",
        )
    with col_f4:
        filtro_tipo = st.selectbox(
            "Tipo",
            ["Todos", "Mercado Interno", "Mercado Externo", "MI / ME"],
            key="rgc_filtro_tipo",
        )

    filtro_mer = "Todos"

    # ── Aplicar filtros ───────────────────────────────────────────────────────
    mask = pd.Series([True] * len(df_html), index=df_html.index)
    if filtro_busca_sel is not None:
        mask &= df_html["Grupo"] == filtro_busca_sel
    if filtro_fat != "Todos":
        mask &= df_html["_fat_label"] == filtro_fat
    if filtro_doc != "Todos":
        if filtro_doc == "Bloqueado":
            mask &= df_html["_doc_bloq"]
        else:
            mask &= ~df_html["_doc_bloq"]
    if filtro_util != "Todos":
        if filtro_util == "Em Risco (>80%)":
            mask &= df_html["_pct"] > 80
        elif filtro_util == "Atenção (50–80%)":
            mask &= (df_html["_pct"] >= 50) & (df_html["_pct"] <= 80)
        elif filtro_util == "Livre (<50%)":
            mask &= df_html["_pct"] < 50
    if filtro_mer != "Todos":
        mask &= df_html["_mercado"] == filtro_mer
    if filtro_tipo != "Todos":
        mask &= df_html["_tipo"] == filtro_tipo

    df_html_exib = df_html[mask].copy()
    df_exp_exib  = df_exp[mask].copy()
    df_html_exib = df_html_exib.drop(columns=["_fat_label", "_doc_bloq", "_mercado", "_tipo", "_pct"], errors="ignore")
    df_exp_exib  = df_exp_exib.drop(columns=["Mercado"], errors="ignore")

    with col_qtd:
        st.caption(f"{len(df_html_exib)} grupo(s)")


    render_tabela_html(
        df_html_exib,
        colunas_centralizar=["Cód.", "Tipo", "% Util.", "Classificação", "Documentação", "Faturamento"],
    )

    # ── Exportações ──────────────────────────────────────────────────────────
    arquivo_excel = exportar_excel_grupos_credito(df_exp_exib)

    botoes_acao_row(
        excel={"data": arquivo_excel, "file_name": f"Grupos_Credito_{datetime.now().strftime('%d-%m-%Y_%Hh%Mmin')}.xlsx", "key": "rgc_excel"},
    )
