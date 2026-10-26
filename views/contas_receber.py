import streamlit as st
import pandas as pd
from utils.prazos import calcular_dias_prazo, formatar_dias_html, formatar_dias_unificado_html, nullar_zeros_dias, VERDE_DIAS, VERMELHO_DIAS
from components.buttons import botao_exportar_excel, botao_salvar_imagem, botoes_acao_row
from components.cards import card_html, render_cards_row, render_ranking_barras, render_tabela_html
from utils.exporters import exportar_excel
from utils.imagem_email import gerar_imagem_resumo_titulos


# ── Formatação ────────────────────────────────────────────────────────────────

def formatar_moeda(valor: float) -> str:
    try:
        return f"R$ {valor:_.2f}".replace(".", ",").replace("_", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_options(df: pd.DataFrame, coluna: str) -> list:
    if coluna not in df.columns:
        return []
    return sorted(df[coluna].dropna().unique().tolist())


# ── (Filtros de Cliente/Vendedor removidos — agora ficam na tela Situação Cliente)


# ── Cards por banco ───────────────────────────────────────────────────────────

BANCO_CONFIG = {
    "SANTANDER":       {"cor_barra": "#E24B4A"},
    "CAIXA ECONÔMICA": {"cor_barra": "#5c8fd6"},
    "OUTROS":          {"cor_barra": "#BA7517"},
}

def _normalizar_banco(nome) -> str:
    if pd.isna(nome) or str(nome).strip().upper() in ("NONE", "", "NAN"):
        return "OUTROS"
    s = str(nome).upper().strip()
    if "SANTANDER" in s:
        return "SANTANDER"
    if "CAIXA" in s:
        return "CAIXA ECONÔMICA"
    return s

# ── Aging (só "A Vencer") ──────────────────────────────────────────────────────

_ORDEM_FAIXA_A_VENCER = {
    "A vencer até 30 dias":   1,
    "A vencer 31 a 60 dias":  2,
    "A vencer 61 a 90 dias":  3,
    "A vencer 90+ dias":      4,
}

_PALETA_AGING = ["#22c55e", "#BA7517", "#E8724A", "#791F1F"]


def _cards_aging_a_vencer(df: pd.DataFrame, ocultar: bool = False):
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    if "FAIXA_DIAS" not in df_ab.columns:
        return

    df_av = df_ab[df_ab["FAIXA_DIAS"].isin(_ORDEM_FAIXA_A_VENCER.keys())].copy()
    if df_av.empty:
        return

    resumo = (
        df_av.groupby("FAIXA_DIAS", as_index=False)
        .agg(SALDO=("SALDO_EM_ABERTO", "sum"))
    )
    resumo["_ORDEM"] = resumo["FAIXA_DIAS"].map(_ORDEM_FAIXA_A_VENCER)
    resumo = resumo.sort_values("_ORDEM")

    vencido = 0
    if "SITUACAO" in df_ab.columns:
        vencido = df_ab[df_ab["SITUACAO"] == "VENCIDO"]["SALDO_EM_ABERTO"].sum()

    st.markdown("#### Aging — A Vencer")

    total_av = resumo["SALDO"].sum()
    maximo = max(resumo["SALDO"].max() or 1, vencido)
    linhas = ""

    if vencido > 0:
        vp = vencido / maximo * 100
        vv = "••••••" if ocultar else formatar_moeda(vencido)
        linhas += (
            '<div style="display:grid;grid-template-columns:160px minmax(0,1fr) 150px;gap:12px;'
            'align-items:center;font-size:13px;padding:5px 0">'
            f'<span style="color:#E24B4A;font-weight:600">Vencidos</span>'
            f'<div style="height:14px;border-radius:4px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div class="an-wipe" style="width:{vp:.1f}%;height:100%;background:#E24B4A"></div></div>'
            f'<span style="color:#E24B4A;text-align:right;font-weight:600">{vv}</span></div>'
            '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'
        )

    for i, row in enumerate(resumo.itertuples()):
        valor = "••••••" if ocultar else formatar_moeda(row.SALDO)
        pct = row.SALDO / maximo * 100 if maximo else 0
        cor = _PALETA_AGING[i % len(_PALETA_AGING)]
        linhas += (
            '<div style="display:grid;grid-template-columns:160px minmax(0,1fr) 150px;gap:12px;'
            'align-items:center;font-size:13px;padding:5px 0">'
            f'<span style="color:#e0e0e0;">{row.FAIXA_DIAS}</span>'
            f'<div style="height:14px;border-radius:4px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div class="an-wipe" style="width:{pct:.1f}%;height:100%;background:{cor}"></div></div>'
            f'<span style="color:#8892A4;text-align:right;">{valor}</span></div>'
        )

    total_fmt = "••••••" if ocultar else formatar_moeda(total_av + vencido)
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px;width:100%;min-height:200px">'
        + linhas
        + '<div style="height:1px;background:#2a2a3a;margin:10px 0"></div>'
        + '<div style="display:flex;justify-content:space-between">'
        + '<span style="color:#e0e0e0;font-size:13px;font-weight:600">Saldo em aberto</span>'
        + f'<span style="color:#e0e0e0;font-size:13px;font-weight:600">{total_fmt}</span></div></div>',
        unsafe_allow_html=True,
    )


def _card_situacao_rosca(df: pd.DataFrame, ocultar: bool = False):
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    if "SITUACAO" not in df_ab.columns:
        return
    total = df_ab["SALDO_EM_ABERTO"].sum() or 1
    vencido  = df_ab[df_ab["SITUACAO"] == "VENCIDO"]["SALDO_EM_ABERTO"].sum()
    a_vencer = df_ab[df_ab["SITUACAO"] == "A VENCER"]["SALDO_EM_ABERTO"].sum()
    pct_av = a_vencer / total * 100
    av_deg = pct_av * 3.6

    val_av   = "••••••" if ocultar else formatar_moeda(a_vencer)
    val_v    = "••••••" if ocultar else formatar_moeda(vencido)
    val_tot  = "••••••" if ocultar else formatar_moeda(total)
    pct_venc = 100 - pct_av
    pct_av_t  = "••••%" if ocultar else f"{pct_av:.2f}%"
    pct_venc_t = "••••%" if ocultar else f"{pct_venc:.2f}%"

    st.markdown("#### Situação")
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:12px;padding:20px 20px;width:100%;'
        'min-height:200px;display:flex;align-items:center;justify-content:center">'
        '<div style="display:flex;align-items:center;justify-content:center;gap:24px">'
        # donut CSS conic-gradient
        '<div style="position:relative;width:100px;height:100px;flex-shrink:0">'
        f'<div class="an-rosca" style="width:100px;height:100px;border-radius:50%;'
        f'background:conic-gradient(#1baf7a 0deg {av_deg:.2f}deg,#E24B4A {av_deg:.2f}deg 360deg);'
        '-webkit-mask:radial-gradient(farthest-side,transparent 60%,black 60%);'
        'mask:radial-gradient(farthest-side,transparent 60%,black 60%)"></div>'
        '<div style="position:absolute;inset:0;display:flex;flex-direction:column;'
        'align-items:center;justify-content:center;pointer-events:none">'
        f'<span style="font-size:13px;font-weight:700;color:#e0e0e0">{pct_av_t}</span>'
        '<span style="font-size:9px;color:#8892A4">a vencer</span>'
        '</div></div>'
        # legenda apenas %
        '<div>'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">'
        '<span style="width:10px;height:10px;border-radius:2px;background:#1baf7a;'
        'display:inline-block;flex-shrink:0"></span>'
        f'<span style="font-size:13px;color:#e0e0e0">A Vencer &nbsp;<strong style="color:#1baf7a">{pct_av_t}</strong></span>'
        '</div>'
        '<div style="display:flex;align-items:center;gap:8px">'
        '<span style="width:10px;height:10px;border-radius:2px;background:#E24B4A;'
        'display:inline-block;flex-shrink:0"></span>'
        f'<span style="font-size:13px;color:#e0e0e0">Vencido &nbsp;<strong style="color:#E24B4A">{pct_venc_t}</strong></span>'
        '</div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )


def _cards_banco(df: pd.DataFrame, ocultar: bool = False):
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    if "BANCO_NOME" not in df_ab.columns:
        return
    df_ab["_B"] = df_ab["BANCO_NOME"].apply(_normalizar_banco)
    bancos = (df_ab.groupby("_B")["SALDO_EM_ABERTO"].sum()
              .reset_index().query("SALDO_EM_ABERTO > 0")
              .sort_values("SALDO_EM_ABERTO", ascending=False))
    if bancos.empty:
        return

    st.markdown("#### Distribuição por Banco")

    total = bancos["SALDO_EM_ABERTO"].sum() or 1

    # barra empilhada proporcional
    segmentos = ""
    for _, row in bancos.iterrows():
        b   = row["_B"]
        cor = BANCO_CONFIG.get(b, {"cor_barra": "#6366f1"})["cor_barra"]
        pct = row["SALDO_EM_ABERTO"] / total * 100
        segmentos += (
            f'<div style="width:{pct:.1f}%;height:100%;background:{cor};flex-shrink:0;'
            f'transition:width .3s"></div>'
        )
    barra_empilhada = (
        '<div class="an-wipe" style="height:8px;border-radius:4px;overflow:hidden;display:flex;'
        f'margin-bottom:14px">{segmentos}</div>'
    )

    linhas = ""
    for _, row in bancos.iterrows():
        b    = row["_B"]
        cor  = BANCO_CONFIG.get(b, {"cor_barra": "#6366f1"})["cor_barra"]
        qtd  = len(df_ab[df_ab["_B"] == b])
        pct  = row["SALDO_EM_ABERTO"] / total * 100
        valor   = "••••••" if ocultar else formatar_moeda(row["SALDO_EM_ABERTO"])
        pct_txt = "••%" if ocultar else f"{pct:.2f}%"
        qtd_txt = "••" if ocultar else f"{qtd} tít."
        linhas += (
            '<div style="display:flex;align-items:center;gap:10px;padding:5px 0">'
            f'<span style="width:10px;height:10px;border-radius:2px;background:{cor};'
            f'flex-shrink:0;display:inline-block"></span>'
            f'<span style="flex:1;color:#e0e0e0;font-size:12px;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis">{b}</span>'
            f'<span style="color:#8892A4;font-size:11px;white-space:nowrap">{qtd_txt}</span>'
            f'<span style="color:{cor};font-size:11px;font-weight:600;white-space:nowrap;'
            f'min-width:38px;text-align:right">{pct_txt}</span>'
            f'<span style="color:#ffffff;font-size:12px;white-space:nowrap;'
            f'min-width:100px;text-align:right">{valor}</span>'
            '</div>'
        )

    total_fmt = "••••••" if ocultar else formatar_moeda(total)
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px;width:100%;min-height:200px">'
        + barra_empilhada + linhas
        + '<div style="height:1px;background:#2a2a3a;margin:10px 0"></div>'
        + '<div style="display:flex;justify-content:space-between">'
        + '<span style="color:#e0e0e0;font-size:13px;font-weight:600">Total em aberto</span>'
        + f'<span style="color:#e0e0e0;font-size:13px;font-weight:600">{total_fmt}</span></div></div>',
        unsafe_allow_html=True,
    )


_DOW_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

def _credito_d1(vencimento: pd.Timestamp) -> pd.Timestamp:
    """Retorna a data de crédito: próximo dia útil após o vencimento.
    Sexta, sábado e domingo → segunda-feira."""
    d = vencimento + pd.Timedelta(days=1)
    while d.weekday() >= 5:  # 5=Sáb, 6=Dom
        d += pd.Timedelta(days=1)
    return d


def _tabela_recebimentos_dia(df: pd.DataFrame, ocultar: bool = False):
    """Recebimentos a vencer agrupados pela data de crédito (D+1 útil), ordem cronológica."""
    if "PRORROGADO" not in df.columns:
        return

    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    df_ab["PRORROGADO"] = pd.to_datetime(df_ab["PRORROGADO"], errors="coerce")
    hoje = pd.Timestamp.today().normalize()

    df_ab = df_ab[df_ab["PRORROGADO"] >= hoje].dropna(subset=["PRORROGADO"]).copy()
    col_data = "PRORROGADO"
    df_ab["_CREDITO"] = df_ab[col_data].apply(_credito_d1)

    df_dia = (
        df_ab.groupby("_CREDITO")["SALDO_EM_ABERTO"]
        .sum()
        .reset_index()
        .rename(columns={"_CREDITO": "Data", "SALDO_EM_ABERTO": "Total"})
        .sort_values("Data")
    )

    if df_dia.empty:
        st.info("Nenhum recebimento a vencer.")
        return

    total_geral = df_dia["Total"].sum() or 1
    maximo = df_dia["Total"].max() or 1
    opacidades = ["1","1","1","0.70","0.55","0.45","0.38","0.32","0.28","0.24",
                  "0.21","0.18","0.16","0.14","0.12"]

    linhas = ""
    for i, (_, row) in enumerate(df_dia.iterrows()):
        opac  = opacidades[i] if i < len(opacidades) else "0.12"
        pct   = row["Total"] / total_geral * 100
        barw  = row["Total"] / maximo * 100
        ts    = pd.Timestamp(row["Data"])
        dow   = _DOW_PT[ts.weekday()]
        _meses = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
        data_fmt = f"{ts.day:02d}/{_meses[ts.month-1]}"
        pct_txt  = "••" if ocultar else f"{pct:.2f}%"
        val_txt  = "••••••" if ocultar else (
            f"{row['Total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        linhas += (
            '<div style="display:grid;grid-template-columns:36px 52px 38px minmax(0,1fr) 115px;'
            'gap:6px;align-items:center;font-size:13px;padding:1px 0">'
            f'<span style="background:rgba(79,163,224,0.15);color:#4fa3e0;font-size:10px;'
            f'font-weight:700;border-radius:4px;padding:1px 4px;text-align:center;white-space:nowrap">{dow}</span>'
            f'<span style="color:#e0e0e0;white-space:nowrap">{data_fmt}</span>'
            f'<span style="color:#4fa3e0;font-size:11px;font-weight:600;text-align:right;white-space:nowrap">{pct_txt}</span>'
            f'<div style="height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div style="width:{barw:.1f}%;height:100%;background:rgba(79,163,224,{opac})"></div></div>'
            f'<span style="color:#ffffff;font-size:12px;text-align:right;white-space:nowrap">{val_txt}</span>'
            '</div>'
        )
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px;min-height:400px">'
        + f'<div style="max-height:375px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
        + linhas
        + '</div>'
        + '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'
        + '<span style="color:#8892A4;font-size:11px">Data de crédito = vencimento + 1 dia útil</span>'
        + '</div>',
        unsafe_allow_html=True,
    )


_OPACIDADES_RANKING = ["1","1","1","0.70","0.55","0.45","0.38","0.32","0.28","0.24",
                        "0.21","0.18","0.16","0.14","0.12"]


def _ranking_clientes(df: pd.DataFrame, ocultar: bool = False, df_grupo_agentes=None, df_grupo_geral=None):
    """Ranking dos top clientes/grupos com maior valor a vencer."""
    tem_grupos = (
        df_grupo_agentes is not None and not df_grupo_agentes.empty
        and {"COD_AGENTE", "COD_GRUPO"}.issubset(df_grupo_agentes.columns)
        and df_grupo_geral is not None and not df_grupo_geral.empty
        and {"GRUPO_CODIGO", "NOME_GRUPO"}.issubset(df_grupo_geral.columns)
    )

    if tem_grupos:
        col_t, col_m = st.columns([1.4, 1])
        with col_t:
            st.markdown("#### Top Clientes a Receber")
        with col_m:
            modo = st.radio(
                "", ["Por Grupo", "Por Cliente"],
                horizontal=True,
                key="cr_rank_modo",
                label_visibility="collapsed",
            )
    else:
        st.markdown("#### Top Clientes a Receber")
        modo = "Por Cliente"

    df_av = df[
        (df["SALDO_EM_ABERTO"].fillna(0) > 0) &
        (df["SITUACAO"] == "A VENCER")
    ].copy()

    if df_av.empty or "CLIENTE" not in df_av.columns:
        st.info("Sem dados a vencer.")
        return

    total_geral = df[df["SALDO_EM_ABERTO"].fillna(0) > 0]["SALDO_EM_ABERTO"].sum() or 1

    if modo == "Por Grupo" and tem_grupos:
        # Mesmo mapeamento de relatorio_contas_receber._com_grupo:
        # str(COD_AGENTE) → COD_GRUPO → NOME_GRUPO
        grupo_por_codigo = (df_grupo_geral.drop_duplicates("GRUPO_CODIGO")
                            .set_index("GRUPO_CODIGO")["NOME_GRUPO"])
        agente_para_grupo = (
            df_grupo_agentes.drop_duplicates("COD_AGENTE")
            .set_index(df_grupo_agentes["COD_AGENTE"].astype(str))["COD_GRUPO"]
            .map(grupo_por_codigo)
        )
        if "COD_CLIENTE" in df_av.columns:
            df_av["_NOME"] = df_av["COD_CLIENTE"].astype(str).map(agente_para_grupo)
        else:
            df_av["_NOME"] = pd.NA
        df_av["_NOME"] = df_av["_NOME"].fillna("Sem grupo")
        df_rank = (
            df_av.groupby("_NOME")["SALDO_EM_ABERTO"]
            .sum().reset_index()
            .rename(columns={"_NOME": "NOME"})
            .sort_values("SALDO_EM_ABERTO", ascending=False)
            .head(15)
        )
    else:
        df_rank = (
            df_av.groupby("CLIENTE")["SALDO_EM_ABERTO"]
            .sum().reset_index()
            .rename(columns={"CLIENTE": "NOME"})
            .sort_values("SALDO_EM_ABERTO", ascending=False)
            .head(15)
        )

    maximo = df_rank["SALDO_EM_ABERTO"].max() or 1
    linhas = ""
    for i, (_, row) in enumerate(df_rank.iterrows()):
        opac = _OPACIDADES_RANKING[i] if i < len(_OPACIDADES_RANKING) else "0.12"
        pct  = row["SALDO_EM_ABERTO"] / total_geral * 100
        barw = row["SALDO_EM_ABERTO"] / maximo * 100
        nome = row["NOME"]
        if len(nome) > 35:
            nome = nome[:34] + "…"
        pct_txt = "••" if ocultar else f"{pct:.2f}%"
        val_txt = "••••••" if ocultar else (
            f"{row['SALDO_EM_ABERTO']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        linhas += (
            '<div style="display:grid;grid-template-columns:20px minmax(0,1fr) 42px minmax(0,1fr) 115px;'
            'gap:8px;align-items:center;font-size:13px;padding:5px 0">'
            f'<span style="color:#8892A4;font-size:11px;font-weight:600;text-align:center">{i+1}</span>'
            f'<span style="color:#e0e0e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{nome}</span>'
            f'<span style="color:#22a35a;font-size:11px;font-weight:600;text-align:right;white-space:nowrap">{pct_txt}</span>'
            f'<div style="height:14px;border-radius:4px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div style="width:{barw:.1f}%;height:100%;background:rgba(46,204,113,{opac})"></div></div>'
            f'<span style="color:#ffffff;font-size:12px;text-align:right;white-space:nowrap">{val_txt}</span>'
            '</div>'
        )
    nota_rodape = (
        "agrupado por grupo econômico (Grupo de Crédito)"
        if modo == "Por Grupo"
        else "% sobre saldo total em aberto"
    )
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px;width:100%;min-height:400px">'
        + '<div style="color:#8892A4;font-size:11px;margin-bottom:8px">% sobre saldo total em aberto</div>'
        + '<div style="max-height:375px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
        + linhas
        + '</div>'
        + '<div style="height:1px;background:#2a2a3a;margin:10px 0"></div>'
        + f'<span style="color:#8892A4;font-size:11px">{nota_rodape}</span>'
        + '</div>',
        unsafe_allow_html=True,
    )


# ── Cards totais ──────────────────────────────────────────────────────────────

def _botao_salvar_imagem(df: pd.DataFrame, ocultar: bool = False):
    """Gera e disponibiliza o download da imagem (fundo branco) e do Excel
    com os cards de totais + a tabela de Títulos Vencidos, pronta para e-mail."""
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0]
    tv    = df_ab[df_ab["SITUACAO"] == "VENCIDO"]["SALDO_EM_ABERTO"].sum()
    tav   = df_ab[df_ab["SITUACAO"] == "A VENCER"]["SALDO_EM_ABERTO"].sum()
    tg    = df_ab["SALDO_EM_ABERTO"].sum()
    qv    = len(df_ab[df_ab["SITUACAO"] == "VENCIDO"])
    qav   = len(df_ab[df_ab["SITUACAO"] == "A VENCER"])
    qt    = len(df_ab)
    perc  = (tv / tg * 100) if tg > 0 else 0
    cor_p = (239, 68, 68) if perc > 20 else (245, 158, 11) if perc > 10 else (34, 197, 94)

    if ocultar:
        _v, _av, _tg, _p = "••••••", "••••••", "••••••", "••••"
    else:
        _v, _av, _tg, _p = formatar_moeda(tv), formatar_moeda(tav), formatar_moeda(tg), f"{perc:.2f}%"

    cards_para_imagem = [
        {"label": "Inadimplência", "valor": _p, "cor": cor_p},
        {"label": "Total Vencido", "valor": _v, "cor": (239, 68, 68)},
        {"label": "Total a Vencer", "valor": _av, "cor": (34, 197, 94)},
        {"label": "Saldo Total em Aberto", "valor": _tg, "cor": (99, 102, 241)},
    ]

    # ── Bloco Aging (barras) ─────────────────────────────────────────────────
    aging_dict = None
    df_av_aging = df_ab[df_ab["SITUACAO"] == "A VENCER"].copy()
    if "FAIXA_DIAS" in df_av_aging.columns:
        resumo_aging = (
            df_av_aging[df_av_aging["FAIXA_DIAS"].isin(_ORDEM_FAIXA_A_VENCER.keys())]
            .groupby("FAIXA_DIAS", as_index=False)
            .agg(SALDO=("SALDO_EM_ABERTO", "sum"))
        )
        resumo_aging["_ORDEM"] = resumo_aging["FAIXA_DIAS"].map(_ORDEM_FAIXA_A_VENCER)
        resumo_aging = resumo_aging.sort_values("_ORDEM")
        cores_aging_rgb = [(34, 197, 94), (186, 117, 23), (232, 114, 74), (121, 31, 31)]
        linhas_aging = []
        for i, row in enumerate(resumo_aging.itertuples()):
            cor = cores_aging_rgb[i % len(cores_aging_rgb)]
            texto = "••••••" if ocultar else formatar_moeda(row.SALDO)
            linhas_aging.append({"label": row.FAIXA_DIAS, "segmentos": [(row.SALDO, cor)], "texto": texto})
        if linhas_aging:
            total_aging = resumo_aging["SALDO"].sum()
            aging_dict = {
                "titulo": "Aging — A Vencer",
                "legenda": [],
                "total_texto": "••••••" if ocultar else formatar_moeda(total_aging),
                "linhas": linhas_aging,
            }

    # ── Bloco Banco (barras) ─────────────────────────────────────────────────
    banco_dict = None
    if "BANCO_NOME" in df_ab.columns:
        df_banco = df_ab.copy()
        df_banco["_B"] = df_banco["BANCO_NOME"].apply(_normalizar_banco)
        bancos_img = (
            df_banco.groupby("_B")["SALDO_EM_ABERTO"].sum()
            .reset_index().query("SALDO_EM_ABERTO > 0")
            .sort_values("SALDO_EM_ABERTO", ascending=False)
        )
        _cores_banco_rgb = {
            "SANTANDER":       (226, 75,  74),
            "CAIXA ECONÔMICA": (92,  143, 214),
            "OUTROS":          (186, 117, 23),
        }
        linhas_banco = []
        for _, row in bancos_img.iterrows():
            b    = row["_B"]
            cor  = _cores_banco_rgb.get(b, (99, 102, 241))
            texto = "••••••" if ocultar else formatar_moeda(row["SALDO_EM_ABERTO"])
            linhas_banco.append({"label": b, "segmentos": [(row["SALDO_EM_ABERTO"], cor)], "texto": texto})
        if linhas_banco:
            total_banco = bancos_img["SALDO_EM_ABERTO"].sum()
            banco_dict = {
                "titulo": "Distribuição por Banco",
                "legenda": [],
                "total_texto": "••••••" if ocultar else formatar_moeda(total_banco),
                "linhas": linhas_banco,
            }

    df_venc = df[
        (df["SITUACAO"] == "VENCIDO") &
        (df["SALDO_EM_ABERTO"].fillna(0) > 0)
    ].copy()

    colunas_origem = {
        "CLIENTE": "Cliente",
        "NF": "NF",
        "ENTRADA": "Entrada",
        "LIQUIDO_FIN": "Saldo Total",
        "SALDO_EM_ABERTO": "Saldo em Aberto",
        "DIAS": "Atraso",
        "COMPLEMENTO": "Complemento",
    }
    colunas_existentes = [c for c in colunas_origem if c in df_venc.columns]

    # df_excel: valores numéricos crus (moeda como número real) — vai para o Excel.
    df_excel = df_venc[colunas_existentes].copy()
    if "DIAS" in df_excel.columns:
        df_excel["DIAS"] = df_excel["DIAS"].apply(lambda x: abs(int(x)) if pd.notna(x) else None)
    if "COMPLEMENTO" in df_excel.columns:
        df_excel["COMPLEMENTO"] = df_excel["COMPLEMENTO"].fillna("-").replace("", "-")
    df_excel = df_excel.rename(columns=colunas_origem)

    # df_img: valores formatados como texto (R$, "X dias", "-") — vai para a imagem PNG.
    df_img = df_venc[colunas_existentes].copy()
    if "LIQUIDO_FIN" in df_img.columns:
        df_img["LIQUIDO_FIN"] = df_img["LIQUIDO_FIN"].apply(formatar_moeda)
    if "SALDO_EM_ABERTO" in df_img.columns:
        df_img["SALDO_EM_ABERTO"] = df_img["SALDO_EM_ABERTO"].apply(formatar_moeda)
    if "DIAS" in df_img.columns:
        df_img["DIAS"] = df_img["DIAS"].apply(
            lambda x: f"{abs(int(x))} dias" if pd.notna(x) else "-"
        )
    if "ENTRADA" in df_img.columns:
        df_img["ENTRADA"] = pd.to_datetime(df_img["ENTRADA"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
    if "COMPLEMENTO" in df_img.columns:
        df_img["COMPLEMENTO"] = df_img["COMPLEMENTO"].fillna("-").replace("", "-")
    df_img = df_img.rename(columns=colunas_origem)

    arquivo_excel = exportar_excel(df_excel, "TITULOS_VENCIDOS")

    # ── Rankings para a imagem ───────────────────────────────────────────────
    def _rank_img(df_base, situacao, cor, top=10):
        df_s = df_base[(df_base["SALDO_EM_ABERTO"].fillna(0) > 0) & (df_base["SITUACAO"] == situacao)]
        if df_s.empty or "CLIENTE" not in df_s.columns:
            return None
        agg = (df_s.groupby("CLIENTE")["SALDO_EM_ABERTO"].sum()
               .reset_index().sort_values("SALDO_EM_ABERTO", ascending=False).head(top))
        linhas = [
            (row["CLIENTE"], row["SALDO_EM_ABERTO"],
             "••••••" if ocultar else formatar_moeda(row["SALDO_EM_ABERTO"]))
            for _, row in agg.iterrows()
        ]
        return {"titulo": ("Top Clientes a Receber" if situacao == "A VENCER" else "Vencido por Cliente"),
                "linhas": linhas, "cor": cor}

    _r_av   = _rank_img(df, "A VENCER",  (34, 197, 94))
    _r_venc = _rank_img(df, "VENCIDO",   (226, 75,  74))
    rankings_img = [r for r in [_r_av, _r_venc] if r]

    imagem_png = gerar_imagem_resumo_titulos(
        titulo_principal="Contas a Receber - Mercado Interno — Títulos Vencidos",
        cards_resumo=cards_para_imagem,
        df_titulos=df_img,
        titulo_tabela="Títulos Vencidos",
        destacar_vencidos=False,
        ordem_colunas=list(colunas_origem.values()),
        aging=aging_dict,
        bloco_direita=banco_dict,
        rankings=rankings_img if rankings_img else None,
    )
    botoes_acao_row(
        excel={"data": arquivo_excel, "file_name": "Contas_a_Receber_Vencidos.xlsx", "key": "cr_export_excel"},
        imagem={"data": imagem_png, "file_name": "Contas_a_Receber_Vencidos.png", "key": "cr_export_imagem"},
        copiar={"data": imagem_png, "key": "cr_copiar"},
    )


def _cards_totais(df: pd.DataFrame, ocultar: bool = False):
    df_ab  = df[df["SALDO_EM_ABERTO"].fillna(0) > 0]
    tv     = df_ab[df_ab["SITUACAO"] == "VENCIDO"]["SALDO_EM_ABERTO"].sum()
    tav    = df_ab[df_ab["SITUACAO"] == "A VENCER"]["SALDO_EM_ABERTO"].sum()
    tg     = df_ab["SALDO_EM_ABERTO"].sum()
    qv     = len(df_ab[df_ab["SITUACAO"] == "VENCIDO"])
    qav    = len(df_ab[df_ab["SITUACAO"] == "A VENCER"])
    qt     = len(df_ab)
    perc   = (tv / tg * 100) if tg > 0 else 0
    cor_p  = "#ef4444" if perc > 20 else "#f59e0b" if perc > 10 else "#22c55e"

    _v  = "••••••" if ocultar else formatar_moeda(tv)
    _av = "••••••" if ocultar else formatar_moeda(tav)
    _tg = "••••••" if ocultar else formatar_moeda(tg)
    _p  = "••••" if ocultar else f"{perc:.2f}%"

    render_cards_row([
        card_html("Saldo Total em Aberto", _tg, f"{qt} título(s)", cor_borda="#6366f1"),
        card_html("Total a Vencer", _av, f"{qav} título(s)", cor_borda="#22c55e"),
        card_html("Total Vencido", _v, f"{qv} título(s)", cor_borda="#ef4444"),
        card_html("Inadimplência", _p, f"Vencido: {_v}", cor_borda=cor_p),
    ])


# ── Aba Resumo: tabela + gráfico ──────────────────────────────────────────────

def _aba_resumo(df: pd.DataFrame, ocultar: bool = False):
    df_venc = df[
        (df["SITUACAO"] == "VENCIDO") &
        (df["SALDO_EM_ABERTO"].fillna(0) > 0)
    ].copy()

    col_tab, col_chart = st.columns(2)

    with col_tab:
        st.markdown("#### Títulos Vencidos")
        if df_venc.empty:
            st.success("Nenhum título vencido.")
        else:
            df_venc = calcular_dias_prazo(df_venc)
            colunas = [c for c in ["CLIENTE", "NF", "ENTRADA", "LIQUIDO_FIN", "SALDO_EM_ABERTO", "DIAS_VENCIDO", "COMPLEMENTO"]
                       if c in df_venc.columns]
            df_exib = df_venc[colunas].copy()
            if "ENTRADA" in df_exib.columns:
                df_exib["ENTRADA"] = pd.to_datetime(df_exib["ENTRADA"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
            if "DIAS_VENCIDO" in df_exib.columns:
                df_exib["DIAS_VENCIDO"] = df_exib["DIAS_VENCIDO"].apply(
                    lambda x: formatar_dias_html(x, VERMELHO_DIAS, negrito=True) if pd.notna(x) else "-"
                )
            if "LIQUIDO_FIN" in df_exib.columns:
                df_exib["LIQUIDO_FIN"] = df_exib["LIQUIDO_FIN"].apply(formatar_moeda)
            if "SALDO_EM_ABERTO" in df_exib.columns:
                df_exib["SALDO_EM_ABERTO"] = df_exib["SALDO_EM_ABERTO"].apply(formatar_moeda)
            if "COMPLEMENTO" in df_exib.columns:
                df_exib["COMPLEMENTO"] = df_exib["COMPLEMENTO"].fillna("-").replace("", "-")
            render_tabela_html(
                df_exib,
                colunas_renomear={
                    "CLIENTE": "Cliente", "NF": "NF", "ENTRADA": "Entrada",
                    "LIQUIDO_FIN": "Saldo Total", "SALDO_EM_ABERTO": "Saldo em Aberto",
                    "DIAS_VENCIDO": "Dias Vencto.", "COMPLEMENTO": "Complemento",
                },
                colunas_moeda=["LIQUIDO_FIN", "SALDO_EM_ABERTO"],
                coluna_complemento="COMPLEMENTO",
            )

            st.markdown("---")
            _botao_salvar_imagem(df, ocultar=ocultar)

    with col_chart:
        st.markdown("#### Vencido por Cliente")
        if df_venc.empty:
            st.info("Sem dados para o gráfico.")
        elif "CLIENTE" in df_venc.columns:
            df_chart = (
                df_venc.groupby("CLIENTE")["SALDO_EM_ABERTO"]
                .sum().reset_index()
                .sort_values("SALDO_EM_ABERTO", ascending=False)
            )
            total_geral = df[df["SALDO_EM_ABERTO"].fillna(0) > 0]["SALDO_EM_ABERTO"].sum() or 1
            maximo = df_chart["SALDO_EM_ABERTO"].max() or 1
            linhas_v = ""
            for i, (_, row) in enumerate(df_chart.iterrows()):
                opac = _OPACIDADES_RANKING[i] if i < len(_OPACIDADES_RANKING) else "0.12"
                pct  = row["SALDO_EM_ABERTO"] / total_geral * 100
                barw = row["SALDO_EM_ABERTO"] / maximo * 100
                nome = row["CLIENTE"]
                if len(nome) > 35:
                    nome = nome[:34] + "…"
                val_txt = formatar_moeda(row["SALDO_EM_ABERTO"])
                linhas_v += (
                    '<div style="display:grid;grid-template-columns:20px minmax(0,1fr) 42px minmax(0,1fr) 130px;'
                    'gap:8px;align-items:center;font-size:13px;padding:4px 0">'
                    f'<span style="color:#8892A4;font-size:11px;font-weight:600;text-align:center">{i+1}</span>'
                    f'<span style="color:#e0e0e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{nome}</span>'
                    f'<span style="color:#E24B4A;font-size:11px;font-weight:600;text-align:right;white-space:nowrap">{pct:.2f}%</span>'
                    f'<div style="height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
                    f'<div style="width:{barw:.1f}%;height:100%;background:rgba(226,75,74,{opac})"></div></div>'
                    f'<span style="color:#8892A4;font-size:12px;text-align:right;white-space:nowrap">{val_txt}</span>'
                    '</div>'
                )
            st.markdown(
                '<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px">'
                + '<div style="max-height:375px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
                + linhas_v
                + '</div>'
                + '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'
                + '<span style="color:#8892A4;font-size:11px">% sobre saldo total em aberto</span>'
                + '</div>',
                unsafe_allow_html=True,
            )


# ── Aba Títulos em Aberto ─────────────────────────────────────────────────────

COLUNAS_EXIBIR = [
    "COD_CLIENTE", "CLIENTE", "VENDEDOR",
    "PARCELA", "TIPO_DOC", "NF", "FATURAMENTO",
    "ENTRADA", "VENCIMENTO", "PRORROGADO",
    "DIAS_VENCIDO", "SITUACAO",
    "LIQUIDO_FIN", "SALDO_EM_ABERTO",
    "BANCO_NOME", "SITUACAO_BOLETO", "CENTRO_CUSTO",
]
COLUNAS_MOEDA = ["LIQUIDO_FIN", "SALDO_EM_ABERTO"]
COLUNAS_DATA  = ["ENTRADA", "VENCIMENTO", "PRORROGADO", "FATURAMENTO"]
COR_SITUACAO  = {"VENCIDO": "#3d1a1a", "A VENCER": "#1a3d1a", "PAGO": "#2a2a2a"}

def _aba_aberto(df: pd.DataFrame):
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0].copy()

    situacoes    = _safe_options(df_ab, "SITUACAO")
    situacao_sel = st.radio(
        "Filtrar por situação:",
        options=["Todos"] + [s for s in situacoes if s != "PAGO"],
        horizontal=True, key="cr_situacao_aberto",
    )

    df_ab = calcular_dias_prazo(df_ab)
    df_tab = df_ab if situacao_sel == "Todos" else df_ab[df_ab["SITUACAO"] == situacao_sel]

    colunas = [c for c in COLUNAS_EXIBIR if c in df_tab.columns]
    df_exib = df_tab[colunas].copy()
    for col in COLUNAS_DATA:
        if col in df_exib.columns:
            df_exib[col] = pd.to_datetime(df_exib[col], errors="coerce").dt.strftime("%d/%m/%Y")
    for col in COLUNAS_MOEDA:
        if col in df_exib.columns:
            df_exib[col] = df_exib[col].apply(formatar_moeda)

    if "DIAS_VENCIDO" in df_exib.columns and "SITUACAO" in df_exib.columns:
        df_exib["DIAS_VENCIDO"] = df_exib.apply(formatar_dias_unificado_html, axis=1)

    render_tabela_html(
        df_exib,
        colunas_renomear={"DIAS_VENCIDO": "Dias Vencto.", "SITUACAO": "Situação Vencto."},
        colunas_moeda=["LIQUIDO_FIN", "SALDO_EM_ABERTO"],
        coluna_situacao="SITUACAO",
        colunas_centralizar=["DIAS_VENCIDO", "SITUACAO"],
    )

    st.markdown("---")
    # Exporta os dados numéricos crus (df_tab), não a versão formatada em texto
    # (df_exib) — assim as colunas de moeda saem como número real no Excel.
    df_excel = df_tab[colunas].rename(columns={"DIAS_VENCIDO": "Dias Vencto.", "SITUACAO": "Situação Vencto."})
    excel_bytes = exportar_excel(
        df_excel, nome_aba="Títulos em Aberto",
        colunas_verde_vermelho=("Dias Vencto.",),
        colunas_situacao_sem_fundo=("Situação Vencto.",),
    )
    botao_exportar_excel(excel_bytes, "titulos_em_aberto.xlsx", key="cr_export_aberto")


# ── Entry point ───────────────────────────────────────────────────────────────

def render(df: pd.DataFrame, mostrar_titulo: bool = True, df_grupo_agentes=None, df_grupo_geral=None) -> None:
    df_filtrado = df

    if len(df_filtrado) == 0:
        st.info("Nenhum dado de Contas a Receber disponível.")
        return

    if "cr_ocultar" not in st.session_state:
        st.session_state["cr_ocultar"] = False

    if mostrar_titulo:
        # Tela avulsa: o botão de ocultar valores fica ao lado do título.
        _oc = st.session_state["cr_ocultar"]
        col_t, col_btn, col_atualizar = st.columns([9, 1.4, 1.4])
        with col_t:
            st.title("Contas a Receber - Mercado Interno")
        with col_btn:
            st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
            if st.button(
                "🙈 Ocultar" if not _oc else "👁 Exibir",
                key="btn_ocultar_cr", use_container_width=True,
                help="Ocultar/exibir valores",
            ):
                st.session_state["cr_ocultar"] = not _oc
        with col_atualizar:
            st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
            if st.button("🔄 Atualizar", key="cr_mi_atualizar", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

    st.divider()
    _cards_totais(df_filtrado, ocultar=st.session_state["cr_ocultar"])
    st.divider()

    col_aging, col_sit, col_banco = st.columns([1.1, 0.75, 1.15])
    with col_aging:
        _cards_aging_a_vencer(df_filtrado, ocultar=st.session_state["cr_ocultar"])
    with col_sit:
        _card_situacao_rosca(df_filtrado, ocultar=st.session_state["cr_ocultar"])
    with col_banco:
        _cards_banco(df_filtrado, ocultar=st.session_state["cr_ocultar"])

    st.divider()
    col_tb, col_rank = st.columns([1, 1])
    with col_tb:
        st.markdown("#### Recebimentos por Data")
        _tabela_recebimentos_dia(df_filtrado, ocultar=st.session_state["cr_ocultar"])
    with col_rank:
        _ranking_clientes(df_filtrado, ocultar=st.session_state["cr_ocultar"], df_grupo_agentes=df_grupo_agentes, df_grupo_geral=df_grupo_geral)

    st.divider()

    aba_resumo, aba_aberto = st.tabs(["Resumo", "Títulos em Aberto"])

    with aba_resumo:
        _aba_resumo(df_filtrado, ocultar=st.session_state["cr_ocultar"])

    with aba_aberto:
        _aba_aberto(df_filtrado)
