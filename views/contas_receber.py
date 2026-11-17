import streamlit as st
import pandas as pd
from utils.prazos import calcular_dias_prazo, formatar_dias_html, formatar_dias_unificado_html, nullar_zeros_dias, VERDE_DIAS, VERMELHO_DIAS
from components.buttons import botao_exportar_excel, botao_salvar_imagem, botoes_acao_row
from components.cards import card_html, render_cards_row, render_ranking_barras, render_tabela_html, tamanho_auto
from utils.exporters import exportar_excel, exportar_excel_abas_recebimentos
from views.relatorio_desconto_financeiro_pendente import resumo_descontos_pendentes
from utils.imagem_email import gerar_imagem_resumo_titulos
from config.pdd import COR_PDD, ocultar_pdd, COR_PDD_TEXTO, DIAS_PDD, DIAS_PDD_PERDA, classificar_vencidos, qtd_acima_perda


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
    "TRANSFERÊNCIA":   {"cor_barra": "#1BADA6"},
}


def _banco_do_titulo(df: pd.DataFrame) -> pd.Series:
    """Banco de cada título para a Distribuição por Banco: clientes que pagam por transferência (Admin > Clientes por
    Transferência) viram "TRANSFERÊNCIA"; os demais seguem o banco de cobrança (sem banco = OUTROS)."""
    banco = df["BANCO_NOME"].apply(_normalizar_banco)
    from services import clientes_transferencia
    transf = clientes_transferencia.codigos()
    if transf and "COD_CLIENTE" in df.columns:
        banco = banco.mask(df["COD_CLIENTE"].astype(str).isin(transf), "TRANSFERÊNCIA")
    return banco

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
    df = classificar_vencidos(df)
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

    vencido = df_ab[df_ab["CLASSIF_VENCIDO"] == "VENCIDO"]["SALDO_EM_ABERTO"].sum()      # vencido sem o PDD
    pdd = df_ab[df_ab["CLASSIF_VENCIDO"] == "PDD"]["SALDO_EM_ABERTO"].sum()

    st.markdown("#### Aging — A Vencer")

    total_av = resumo["SALDO"].sum()
    maximo = max(resumo["SALDO"].max() or 1, vencido, pdd)
    linhas = ""

    for _rotulo, _valor, _cor in (("Vencidos", vencido, "#E24B4A"), ("PDD", pdd, COR_PDD_TEXTO)):
        if _valor <= 0:
            continue
        vp = _valor / maximo * 100
        vv = "••••••" if ocultar else formatar_moeda(_valor)
        linhas += (
            '<div style="display:grid;grid-template-columns:minmax(92px,132px) minmax(56px,1fr) minmax(92px,128px);gap:10px;'
            'align-items:center;font-size:13px;padding:5px 0">'
            f'<span style="color:{_cor};font-weight:600">{_rotulo}</span>'
            f'<div style="height:14px;border-radius:4px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div class="an-wipe" style="width:{vp:.1f}%;height:100%;background:{_cor if _rotulo == "Vencidos" else COR_PDD}"></div></div>'
            f'<span style="color:{_cor};text-align:right;font-weight:600">{vv}</span></div>'
        )
    if vencido > 0 or pdd > 0:
        linhas += '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'

    for i, row in enumerate(resumo.itertuples()):
        valor = "••••••" if ocultar else formatar_moeda(row.SALDO)
        pct = row.SALDO / maximo * 100 if maximo else 0
        cor = _PALETA_AGING[i % len(_PALETA_AGING)]
        linhas += (
            '<div style="display:grid;grid-template-columns:minmax(92px,132px) minmax(56px,1fr) minmax(92px,128px);gap:10px;'
            'align-items:center;font-size:13px;padding:5px 0">'
            f'<span style="color:#e0e0e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{row.FAIXA_DIAS}">{row.FAIXA_DIAS}</span>'
            f'<div style="height:14px;border-radius:4px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div class="an-wipe" style="width:{pct:.1f}%;height:100%;background:{cor}"></div></div>'
            f'<span style="color:#8892A4;text-align:right;">{valor}</span></div>'
        )

    total_fmt = "••••••" if ocultar else formatar_moeda(total_av + vencido + pdd)
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:12px;border-top:4px solid #22c55e;box-sizing:border-box;padding:16px 18px;width:100%;min-height:224px">'
        + linhas
        + '<div style="height:1px;background:#2a2a3a;margin:10px 0"></div>'
        + '<div style="display:flex;justify-content:space-between">'
        + '<span style="color:#e0e0e0;font-size:13px;font-weight:600">Saldo em aberto</span>'
        + f'<span style="color:#e0e0e0;font-size:13px;font-weight:600">{total_fmt}</span></div></div>',
        unsafe_allow_html=True,
    )


def _nomes_curtos(nomes: list[str]) -> list[str]:
    """Nome curto do cliente para o ticker: a primeira palavra ("ALFA SUPERMERCADOS" -> "Alfa"); palavra de até 3
    letras leva a seguinte ("JM FRUTAS" -> "JM Frutas"). Se dois clientes ficarem com o mesmo nome curto, os dois usam
    as duas primeiras palavras."""
    def palavra(p: str) -> str:
        return p.upper() if len(p) <= 3 else p.capitalize()

    def curto(nome: str, n: int) -> str:
        partes = [p for p in str(nome).replace(",", " ").split() if p]
        if not partes:
            return "-"
        if n == 1 and len(partes[0]) <= 3 and len(partes) > 1:
            n = 2
        return " ".join(palavra(p) for p in partes[:n])

    um = [curto(n, 1) for n in nomes]
    return [curto(n, 2) if um.count(c) > 1 else c for n, c in zip(nomes, um)]


def _card_descontos_pendentes(desc: dict, ocultar: bool = False) -> None:
    """Card "Descontos Contratuais Pendentes" (descontos contratuais financeiros ainda não lançados no Mega): quantidade de títulos
    no topo, um ticker automático que passa de cliente em cliente (nome e quantidade de títulos; pausa com o mouse em
    cima) e, fixo embaixo, o total a lançar e o número de clientes. O ticker é só CSS, sem script. 224 px de altura,
    como os cards vizinhos."""
    from html import escape
    ALT, SEG = 56, 4          # altura de um cliente no ticker (px) e segundos por cliente
    pend, erros = desc["pendentes"], desc["erros"]
    cor = "#ef4444" if erros else "#F59E0B" if pend else "#22c55e"
    clientes = desc["por_cliente"][:10]
    ticker, estilo = "", ""
    if clientes:
        curtos = _nomes_curtos([c[0] for c in clientes])
        itens = list(zip(clientes, curtos))
        linhas = "".join(
            f'<div class="tkdp-item" title="{escape(c[0])}"><span class="tkdp-nome">{escape(curto)}</span>'
            f'<span class="tkdp-qtd" style="color:{cor}">{c[1]:02d} título{"s" if c[1] != 1 else ""}</span></div>'
            for c, curto in itens + itens[:1]          # repete o 1º no fim: a volta do ciclo fica contínua
        )
        n = len(itens)
        quadros = "".join(
            f"{k * 100 / n:.3f}%,{k * 100 / n + 82 / n:.3f}%{{transform:translateY(-{ALT * k}px)}}" for k in range(n)
        ) + f"100%{{transform:translateY(-{ALT * n}px)}}"
        bolinhas, anim_bolinhas = "", ""
        for k in range(n):
            a, b = k * 100 / n, (k + 1) * 100 / n
            ini = f"0%,{a - 0.01:.3f}%{{background:#4b5563}}" if k else ""
            fim = f"{b:.3f}%,100%{{background:#4b5563}}" if k < n - 1 else ""
            anim_bolinhas += (f"@keyframes tkdot{k}{{{ini}{a:.3f}%,{b - 0.01:.3f}%{{background:{cor}}}{fim}}}"
                              f".tkdp-dot{k}{{animation:tkdot{k} {SEG * n}s infinite}}")
            bolinhas += f'<span class="tkdp-dot tkdp-dot{k}"></span>'
        estilo = (
            f"<style>@keyframes tkdp{{{quadros}}}{anim_bolinhas}"
            f".tkdp-janela{{height:{ALT}px;overflow:hidden}}"
            f".tkdp-lista{{animation:tkdp {SEG * n}s infinite}}"
            f".tkdp-card:hover .tkdp-lista,.tkdp-card:hover .tkdp-dot{{animation-play-state:paused}}"
            f".tkdp-item{{height:{ALT}px;display:flex;flex-direction:column;justify-content:center}}"
            ".tkdp-nome{font-size:20px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
            ".tkdp-qtd{font-size:13px}"
            ".tkdp-dot{width:6px;height:6px;border-radius:50%;background:#4b5563;display:inline-block;margin:0 2px}"
            "@media (prefers-reduced-motion:reduce){.tkdp-lista,.tkdp-dot{animation:none}}</style>"
        )
        ticker = (f'<div class="tkdp-janela"><div class="tkdp-lista">{linhas}</div></div>'
                  f'<div style="text-align:center;margin:0 0 6px">{bolinhas}</div>')
    if pend:
        total = "R$ ••••••" if ocultar else formatar_moeda(desc["valor"])
        rodape = (f'<div style="font-size:16px;font-weight:700;color:#fff">{total}</div>'
                  f'<div style="font-size:11px;color:#8892a4">a lançar · {desc["clientes"]} cliente(s)'
                  + (f' · <span style="color:#ef4444">{erros} com erro</span>' if erros else "") + "</div>")
    else:
        rodape = (f'<div style="font-size:16px;font-weight:700;color:{cor};margin-top:14px">Tudo aplicado</div>'
                  f'<div style="font-size:11px;color:#8892a4">nenhum desconto a lançar</div>')
    with st.container(key="cr_desc_pend"):
        _desenhar_card_descontos(estilo, cor, pend, ticker, rodape)


def _desenhar_card_descontos(estilo: str, cor: str, pend: int, ticker: str, rodape: str) -> None:
    st.markdown("#### Descontos Contratuais Pendentes")
    st.markdown(
        "<style>.st-key-cr_desc_pend{container-type:inline-size}.st-key-cr_desc_pend h4{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:min(1.5rem,5.3cqw) !important;line-height:1.8rem !important}</style>"
        + estilo
        + f'<div class="tkdp-card" style="background:#1e1e2e;border-radius:12px;border-top:4px solid {cor};width:100%;'
          'height:224px;box-sizing:border-box;padding:12px 16px;display:flex;flex-direction:column;overflow:hidden">'
          '<div style="display:flex;align-items:baseline;justify-content:space-between">'
          '<span style="font-size:11px;color:#8892a4">Pendentes</span>'
          f'<span><b style="font-size:26px;color:#fff;line-height:1">{pend}</b> '
          f'<span style="font-size:11px;color:{cor}">título(s)</span></span></div>'
          '<div style="height:1px;background:#2a2a3a;margin:8px 0 2px"></div>'
        + ticker
        + ('<div style="height:1px;background:#2a2a3a;margin:0 0 8px"></div>' if ticker else "")
        + rodape + '</div>',
        unsafe_allow_html=True,
    )


def _card_situacao_rosca(df: pd.DataFrame, ocultar: bool = False, vertical: bool = False):
    df = classificar_vencidos(df)
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    if "SITUACAO" not in df_ab.columns:
        return
    total = df_ab["SALDO_EM_ABERTO"].sum() or 1
    vencido  = df_ab[df_ab["CLASSIF_VENCIDO"] == "VENCIDO"]["SALDO_EM_ABERTO"].sum()     # vencido sem o PDD
    pdd      = df_ab[df_ab["CLASSIF_VENCIDO"] == "PDD"]["SALDO_EM_ABERTO"].sum()
    a_vencer = df_ab[df_ab["SITUACAO"] == "A VENCER"]["SALDO_EM_ABERTO"].sum()
    pct_av = a_vencer / total * 100
    av_deg = pct_av * 3.6
    if pdd > 0 and pdd / total * 360 < 4:       # PDD pequeno ainda aparece na rosca: tira o que falta da fatia verde (só o desenho)
        av_deg -= 4 - pdd / total * 360
    venc_deg = av_deg + vencido / total * 360
    fundo_rosca = (f"conic-gradient(#1baf7a 0deg {av_deg:.2f}deg,#E24B4A {av_deg:.2f}deg {venc_deg:.2f}deg,"
                   f"{COR_PDD} {venc_deg:.2f}deg 360deg)")

    val_av   = "••••••" if ocultar else formatar_moeda(a_vencer)
    val_v    = "••••••" if ocultar else formatar_moeda(vencido)
    val_tot  = "••••••" if ocultar else formatar_moeda(total)
    pct_venc = vencido / total * 100
    pct_pdd = pdd / total * 100
    pct_av_t  = "••••%" if ocultar else f"{pct_av:.2f}%"
    pct_venc_t = "••••%" if ocultar else f"{pct_venc:.2f}%"
    pct_pdd_t = "••••%" if ocultar else f"{pct_pdd:.2f}%"

    st.markdown("#### Situação")
    if vertical:      # coluna estreita (4 cards na faixa): rosca em cima e a legenda embaixo
        st.markdown(
            '<div style="background:#1e1e2e;border-radius:12px;border-top:4px solid #6366f1;width:100%;height:224px;box-sizing:border-box;display:flex;'
            'flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:6px 0 4px">'
            '<div style="position:relative;width:92px;height:92px;flex-shrink:0">'
            f'<div class="an-rosca" style="width:92px;height:92px;border-radius:50%;'
            f'background:{fundo_rosca};'
            '-webkit-mask:radial-gradient(farthest-side,transparent 60%,black 60%);'
            'mask:radial-gradient(farthest-side,transparent 60%,black 60%)"></div>'
            '<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;'
            'justify-content:center;pointer-events:none">'
            f'<span style="font-size:13px;font-weight:700;color:#e0e0e0">{pct_av_t}</span>'
            '<span style="font-size:9px;color:#8892A4">a vencer</span></div></div>'
            '<div style="display:grid;grid-template-columns:auto auto;column-gap:10px;row-gap:5px;font-size:12.5px;color:#e0e0e0;align-items:center">'
            f'<span><span style="color:#1baf7a">■</span> A Vencer</span><strong style="color:#1baf7a;text-align:right">{pct_av_t}</strong>'
            f'<span><span style="color:#E24B4A">■</span> Vencido</span><strong style="color:#E24B4A;text-align:right">{pct_venc_t}</strong>'
            + (f'<span><span style="color:{COR_PDD}">■</span> PDD</span><strong style="color:{COR_PDD_TEXTO};text-align:right">{pct_pdd_t}</strong>' if pdd > 0 else '')
            + '</div></div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        '<div style="background:#1e1e2e;border-radius:12px;border-top:4px solid #6366f1;box-sizing:border-box;padding:20px 20px;width:100%;'
        'min-height:200px;display:flex;align-items:center;justify-content:center">'
        '<div style="display:flex;align-items:center;justify-content:center;gap:24px">'
        # donut CSS conic-gradient
        '<div style="position:relative;width:100px;height:100px;flex-shrink:0">'
        f'<div class="an-rosca" style="width:100px;height:100px;border-radius:50%;'
        f'background:{fundo_rosca};'
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
        + (f'<div style="display:flex;align-items:center;gap:8px;margin-top:14px"><span style="width:10px;height:10px;border-radius:2px;'
           f'background:{COR_PDD};display:inline-block;flex-shrink:0"></span>'
           f'<span style="font-size:13px;color:#e0e0e0">PDD &nbsp;<strong style="color:{COR_PDD_TEXTO}">{pct_pdd_t}</strong></span></div>' if pdd > 0 else '')
        + '</div></div></div>',
        unsafe_allow_html=True,
    )


def _cards_banco(df: pd.DataFrame, ocultar: bool = False):
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    if "BANCO_NOME" not in df_ab.columns:
        return
    df_ab["_B"] = _banco_do_titulo(df_ab)
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
        '<div style="background:#1e1e2e;border-radius:12px;border-top:4px solid #378ADD;box-sizing:border-box;padding:16px 18px;width:100%;min-height:224px">'
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


def _bloco_recebimento_hoje(ocultar: bool = False) -> str:
    """Bloco "Hoje" do painel Recebimentos por Data: esperado, recebido no banco e a receber para o crédito do dia."""
    from services.data_service import carregar_recebimento_hoje_mi
    info = carregar_recebimento_hoje_mi()
    if not info:
        return ""
    # Esperado = o que estava em aberto no começo do dia para este crédito: o que ainda está em aberto mais o que já foi
    # baixado hoje desses títulos. Fica fixo durante o dia (só o recebido sobe e o a receber desce). O que foi quitado
    # antes de hoje (pago adiantado, compensação, desconto) não entra: já não é cobrança do dia.
    # Recebido = o que foi baixado hoje (data do banco) dos títulos do dia, mais baixa de ND (434) e adiantamento (981) se
    # houver. Pagamento adiantado de títulos de outros vencimentos não entra.
    aberto = max(info["aberto"], 0.0)
    baixa_esperado = max(info.get("baixa_esperado", 0.0), 0.0)
    esperado = aberto + baixa_esperado
    nd = max(info.get("nd", 0.0), 0.0)
    adiantamento = max(info.get("adiantamento", 0.0), 0.0)
    recebido = baixa_esperado + nd + adiantamento
    pct = baixa_esperado / esperado * 100 if esperado > 0 else 0.0
    fmt = lambda v: "••••••" if ocultar else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    pct_txt = "••" if ocultar else f"{pct:.2f}".replace(".", ",") + "%"
    # Barra na escala do esperado mais o que entrou fora dele: baixado hoje, em aberto, ND e adiantamento
    escala = esperado + nd + adiantamento
    larg = lambda v: f"{v / escala * 100:.2f}" if escala > 0 else "0.00"
    marca = (f'<div style="position:absolute;left:{larg(esperado)}%;top:-3px;width:2px;height:14px;background:#fff;border-radius:1px"></div>'
             if nd + adiantamento > 0 else "")
    barra = (
        '<div style="position:relative;margin-top:9px">'
        '<div class="an-wipe" style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:rgba(128,128,128,0.15)">'
        f'<span style="width:{larg(baixa_esperado)}%;background:#4fa3e0"></span>'
        f'<span style="width:{larg(aberto)}%;background:#5a6280"></span>'
        f'<span style="width:{larg(nd)}%;background:#1BADA6"></span>'
        f'<span style="width:{larg(adiantamento)}%;background:#D4537E"></span></div>'
        + marca + '</div>'
    )
    itens = [f'baixado do esperado {fmt(baixa_esperado)}'] if esperado > 0 else []
    if nd > 0:
        itens.append(f'<span style="color:#1BADA6">+{fmt(nd)} ND baixadas</span>')
    if adiantamento > 0:
        itens.append(f'<span style="color:#D4537E">+{fmt(adiantamento)} adiantamento recebido</span>')
    sem_esperado = esperado <= 0
    rotulo = f'<span>{pct_txt} recebido</span>' if not sem_esperado else '<span>nada em aberto previsto para hoje</span>'
    # o detalhe só aparece quando entrou algo além do baixado do esperado (ND ou adiantamento)
    detalhe = f'<div style="color:#8892A4;font-size:10px;margin-top:2px">{" · ".join(itens)}</div>' if len(itens) > 1 else ""

    hoje = info["data"]
    venc = info["vencimentos"]
    origem = (f"vencidos em {venc[0]:%d/%m}" if len(venc) == 1 else f"vencidos de {min(venc):%d/%m} a {max(venc):%d/%m}")
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return (
        '<div style="background:#252B3D;border:1px solid #3a4160;border-radius:8px;padding:10px 12px;margin-bottom:10px">'
        '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap">'
        '<div style="display:flex;align-items:center;gap:8px">'
        '<span style="background:rgba(27,173,166,0.2);color:#1BADA6;font-size:10px;font-weight:700;border-radius:4px;padding:1px 6px">HOJE</span>'
        f'<span style="color:#e0e0e0;font-size:13px;font-weight:500">{_DOW_PT[hoje.weekday()]} {hoje.day:02d}/{meses[hoje.month - 1]}</span></div>'
        f'<span style="color:#8892A4;font-size:11px">crédito de títulos {origem}</span></div>'
        '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:8px">'
        f'<div><div style="color:#8892A4;font-size:11px">Esperado</div><div style="color:#fff;font-size:15px;font-weight:600;white-space:nowrap">{fmt(esperado)}</div></div>'
        f'<div><div style="color:#8892A4;font-size:11px">Recebido no banco</div><div style="color:#4fa3e0;font-size:15px;font-weight:600;white-space:nowrap">{fmt(recebido)}</div></div>'
        f'<div><div style="color:#8892A4;font-size:11px">A receber</div><div style="color:#fff;font-size:15px;font-weight:600;white-space:nowrap">{fmt(aberto)}</div></div></div>'
        + barra +
        '<div style="display:flex;justify-content:space-between;color:#8892A4;font-size:10px;margin-top:4px">'
        f'{rotulo}' + ('' if sem_esperado else f'<span>{info["abertas"]} parcela(s) em aberto</span>') + '</div>'
        + detalhe + '</div>'
        '<div style="color:#8892A4;font-size:11px;margin:0 0 6px">Próximos recebimentos</div>'
    )


_COLUNAS_TITULO_BOTAO = [1.0, 0.05, 0.6, 1.3]   # título | folga | (mês) | botão no canto direito, iguais nos dois painéis
# Botão quadrado encostado no canto direito da coluna (os dois painéis usam o mesmo)
_CSS_BOTAO_CANTO = ("<style>.st-key-cr_rec_canto, .st-key-cr_rank_canto{width:100%}"
                    ".st-key-cr_rec_canto [data-testid='stButtonGroup'], .st-key-cr_rank_canto [data-testid='stButtonGroup']"
                    "{display:flex;justify-content:flex-end;width:100%}.st-key-cr_rec_canto button, .st-key-cr_rank_canto button{white-space:nowrap}</style>")
_CSS_GIRO = ("<style>@keyframes crGiro{from{transform:perspective(1200px) rotateX(-90deg);opacity:0}"
             "to{transform:perspective(1200px) rotateX(0);opacity:1}}</style>")
_ANIM_GIRO = "animation:crGiro .45s ease-out;transform-origin:center top;"


def _excel_recebimentos(df_base: pd.DataFrame, ano: int, mes: int) -> bytes:
    """Excel do card Recebimentos por Data: aba "A receber" (o que ainda vai entrar, por data de crédito) e aba
    "Recebido" (baixas do mês escolhido, um título por linha)."""
    from services.data_service import carregar_recebido_periodo_mi
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
             "Novembro", "Dezembro"]
    hoje = pd.Timestamp.today().normalize()
    # A receber: os mesmos títulos do card (em aberto, vencimento de hoje em diante)
    ab = df_base[df_base["SALDO_EM_ABERTO"].fillna(0) > 0].copy()
    ab["PRORROGADO"] = pd.to_datetime(ab["PRORROGADO"], errors="coerce")
    ab = ab[ab["PRORROGADO"] >= hoje].sort_values(["PRORROGADO", "CLIENTE", "NF"])
    a_receber = pd.DataFrame({
        "Data Crédito": ab["PRORROGADO"].map(_credito_d1),
        "Cód. Cliente": pd.to_numeric(ab["COD_CLIENTE"], errors="coerce").astype("Int64"),
        "Cliente": ab["CLIENTE"], "NF": ab["NF"], "Parcela": ab["PARCELA"], "Vencimento": ab["PRORROGADO"],
        "Dias p/ Vencer": (ab["PRORROGADO"] - hoje).dt.days, "Saldo em Aberto": ab["SALDO_EM_ABERTO"],
    })
    # Recebido: baixas do mês escolhido
    inicio = pd.Timestamp(year=ano, month=mes, day=1)
    fim = min(inicio + pd.offsets.MonthEnd(0), hoje)
    df = carregar_recebido_periodo_mi(inicio.date(), fim.date())
    if df.empty:
        recebido = pd.DataFrame()
    else:
        det = df[df["VALOR_PAGO"] > 0].copy()
        cred = det["VENCIMENTO"].map(lambda v: _credito_d1(v) if pd.notna(v) else pd.NaT)
        det["SITUACAO"] = ["Em atraso" if a else "Em dia" for a in det["DIA"] > cred]
        det["DIAS"] = (det["DIA"] - det["VENCIMENTO"]).dt.days   # positivo = pago depois do vencimento
        det = det.sort_values(["DIA", "CLIENTE", "DOC", "PARC"], ascending=[False, True, True, True])
        recebido = pd.DataFrame({
            "Data Pagamento": det["DIA"], "Cód. Cliente": det["AGN"].astype("Int64"), "Cliente": det["CLIENTE"], "Banco": det["BANCO"],
            "NF": det["DOC"], "Parcela": det["PARC"], "Vencimento": det["VENCIMENTO"],
            "Dias (Pagto - Vencto.)": det["DIAS"].astype("Int64"), "Situação": det["SITUACAO"],
            "Valor Pago": det["VALOR_PAGO"],
        })
    # Resumos (só no Excel): recebido por banco (só o valor pago; desconto e adiantamento ficam de fora) e a receber
    # por mês de crédito e por banco de cobrança
    def _com_total(g: pd.DataFrame, rotulo: str, clientes_total: int) -> pd.DataFrame:
        tot = g["Valor"].sum() or 1
        g = g.assign(Pct=g["Valor"] / tot)
        total = pd.DataFrame([{rotulo: "TOTAL", "Titulos": g["Titulos"].sum(), "Clientes": clientes_total,
                               "Valor": g["Valor"].sum(), "Pct": 1.0}])
        return pd.concat([g, total], ignore_index=True)

    if recebido.empty:
        rec_banco = pd.DataFrame()
    else:
        pg = recebido[recebido["Valor Pago"] > 0]
        g = (pg.groupby("Banco").agg(Titulos=("NF", "size"), Clientes=("Cód. Cliente", "nunique"), Valor=("Valor Pago", "sum"))
             .reset_index().sort_values("Valor", ascending=False))
        rec_banco = _com_total(g, "Banco", pg["Cód. Cliente"].nunique())   # cliente que paga por 2 bancos conta 1 vez no total
        rec_banco.columns = ["Banco", "Títulos", "Clientes", "Valor Recebido", "% do Total"]
    if a_receber.empty:
        ar_mes = ar_banco = pd.DataFrame()
    else:
        base_ar = a_receber.assign(_COD=ab["COD_CLIENTE"].values, _BANCO=_banco_do_titulo(ab).values,
                                   _MES=a_receber["Data Crédito"].dt.strftime("%Y-%m"))
        n_clientes = base_ar["_COD"].nunique()

        def _agrupa(chave):
            return (base_ar.groupby(chave).agg(Titulos=("NF", "size"), Clientes=("_COD", "nunique"),
                                               Valor=("Saldo em Aberto", "sum")).reset_index())
        g = _agrupa("_MES").sort_values("_MES")
        g["_MES"] = g["_MES"].map(lambda m: f"{meses[int(m[5:]) - 1]}/{m[:4]}")
        ar_mes = _com_total(g, "_MES", n_clientes)
        ar_mes.columns = ["Mês de Crédito", "Títulos", "Clientes", "Valor a Receber", "% do Total"]
        g = _agrupa("_BANCO").sort_values("Valor", ascending=False)
        ar_banco = _com_total(g, "_BANCO", n_clientes)
        ar_banco.columns = ["Banco de Cobrança", "Títulos", "Clientes", "Valor a Receber", "% do Total"]
    return exportar_excel_abas_recebimentos([
        {"nome": "Resumo", "titulo": f"Resumo - Mercado Interno - posição em {hoje:%d/%m/%Y}", "blocos": [
            {"titulo": f"Recebido por banco - {meses[mes - 1]}/{ano} ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y})", "df": rec_banco,
             "moeda": ("Valor Recebido",), "verde": ("Valor Recebido",), "percentual": ("% do Total",),
             "centro": ("Títulos", "Clientes"), "total_na_ultima": True},
            {"titulo": "A receber por mês de crédito (vencimento + 1 dia útil)", "df": ar_mes,
             "moeda": ("Valor a Receber",), "percentual": ("% do Total",), "centro": ("Títulos", "Clientes"),
             "total_na_ultima": True},
            {"titulo": "A receber por banco de cobrança", "df": ar_banco,
             "moeda": ("Valor a Receber",), "percentual": ("% do Total",), "centro": ("Títulos", "Clientes"),
             "total_na_ultima": True},
        ]},
        {"nome": "A receber", "titulo": f"A receber - Mercado Interno - posição em {hoje:%d/%m/%Y}", "df": a_receber,
         "moeda": ("Saldo em Aberto",), "centro": ("Parcela", "Dias p/ Vencer")},
        {"nome": "Recebido",
         "titulo": f"Recebido - Mercado Interno - {meses[mes - 1]}/{ano} ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y})",
         "df": recebido, "moeda": ("Valor Pago",), "verde": ("Valor Pago",),
         "centro": ("Parcela", "Dias (Pagto - Vencto.)", "Situação"), "situacao": "Situação"},
    ])


@st.fragment
def _card_recebimentos_dia(df: pd.DataFrame, ocultar: bool = False):
    """Card Recebimentos por Data com o botão A receber | Recebido: o card gira e mostra o outro lado."""
    hoje = pd.Timestamp.today().normalize()
    meses_nome = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
                  "Outubro", "Novembro", "Dezembro"]
    opcoes = []   # últimos 12 meses, o atual primeiro
    for i in range(12):
        m = hoje.replace(day=1) - pd.DateOffset(months=i)
        opcoes.append((m.year, m.month))
    c_tit, _, c_mes, c_modo = st.columns(_COLUNAS_TITULO_BOTAO, vertical_alignment="center")
    with c_tit:
        st.markdown("#### Recebimentos por Data")
    with c_modo:
        st.markdown(_CSS_BOTAO_CANTO, unsafe_allow_html=True)
        with st.container(key="cr_rec_canto"):
            modo = st.segmented_control("Recebimentos", ["A receber", "Recebido"], default="A receber",
                                        key="cr_rec_modo", label_visibility="collapsed", width="stretch")
    ano, mes = st.session_state.get("cr_rec_mes", opcoes[0])
    if modo == "Recebido":
        with c_mes:
            ano, mes = st.selectbox("Mês", opcoes, key="cr_rec_mes", label_visibility="collapsed",
                                    format_func=lambda o: f"{meses_nome[o[1] - 1][:3]}/{o[0]}")
        _recebido_mes(ocultar, ano, mes)
    else:
        _tabela_recebimentos_dia(df, ocultar)
    botao_exportar_excel(lambda: _excel_recebimentos(df, ano, mes), f"Recebimentos_MI_{ano}-{mes:02d}.xlsx",
                         key="cr_export_recebimentos",
                         help="Três abas: Resumo, A receber (títulos em aberto) e Recebido (só o que entrou no banco no mês selecionado)")


def _recebido_mes(ocultar: bool, ano: int, mes: int):
    """Lado "Recebido" do card: o que foi baixado no banco no mês escolhido (o atual vai até hoje), por dia da baixa."""
    from services.data_service import carregar_recebido_periodo_mi
    hoje = pd.Timestamp.today().normalize()
    inicio = pd.Timestamp(year=ano, month=mes, day=1)
    fim = min(inicio + pd.offsets.MonthEnd(0), hoje)
    df = carregar_recebido_periodo_mi(inicio.date(), fim.date())
    if df.empty:
        st.info("Nenhum recebimento neste mês.")
        return
    fmt = lambda v: "••••••" if ocultar else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    pago = df[df["VALOR_PAGO"] > 0].copy()
    total = pago["VALOR_PAGO"].sum()
    titulos = pago[["DOC", "AGN", "PARC"]].drop_duplicates().shape[0]
    clientes = pago["AGN"].nunique()
    rot_mes = "MÊS ATUAL" if (ano, mes) == (hoje.year, hoje.month) else f"{meses[mes - 1].upper()}/{ano}"

    por_dia =pago.groupby("DIA")["VALOR_PAGO"].sum().reset_index().sort_values("DIA", ascending=False)
    maximo = por_dia["VALOR_PAGO"].max() or 1
    total_geral = total or 1
    linhas = ""
    for i, (_, row) in enumerate(por_dia.iterrows()):
        ts = pd.Timestamp(row["DIA"])
        opac = "1" if i < 3 else "0.6"
        pct = row["VALOR_PAGO"] / total_geral * 100
        linhas += (
            '<div style="display:grid;grid-template-columns:36px 52px 38px minmax(0,1fr) 115px;'
            'gap:6px;align-items:center;font-size:13px;padding:1px 0">'
            f'<span style="background:rgba(79,163,224,0.15);color:#4fa3e0;font-size:10px;font-weight:700;'
            f'border-radius:4px;padding:1px 4px;text-align:center;white-space:nowrap">{_DOW_PT[ts.weekday()]}</span>'
            f'<span style="color:#e0e0e0;white-space:nowrap">{ts.day:02d}/{meses[ts.month - 1]}</span>'
            f'<span style="color:#4fa3e0;font-size:11px;font-weight:600;text-align:right;white-space:nowrap">'
            f'{"••" if ocultar else f"{pct:.2f}%"}</span>'
            '<div style="height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div class="an-wipe" style="animation-delay:{min(i, 14) * 45}ms;width:{row["VALOR_PAGO"] / maximo * 100:.1f}%;height:100%;background:rgba(79,163,224,{opac})"></div></div>'
            f'<span style="color:#ffffff;font-size:12px;text-align:right;white-space:nowrap">{fmt(row["VALOR_PAGO"])}</span>'
            '</div>'
        )
    cabecalho = (
        '<div style="background:#252B3D;border:1px solid #3a4160;border-radius:8px;padding:10px 12px;margin-bottom:10px">'
        '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap">'
        '<div style="display:flex;align-items:center;gap:8px">'
        f'<span style="background:rgba(79,163,224,0.2);color:#4fa3e0;font-size:10px;font-weight:700;border-radius:4px;padding:1px 6px">{rot_mes}</span>'
        f'<span style="color:#e0e0e0;font-size:13px;font-weight:500">{inicio.day:02d}/{meses[inicio.month - 1]} a {fim.day:02d}/{meses[fim.month - 1]}</span></div>'
        '<span style="color:#8892A4;font-size:11px">por data da baixa no banco</span></div>'
        '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:8px">'
        f'<div><div style="color:#8892A4;font-size:11px">Recebido</div><div style="color:#00B050;font-size:15px;font-weight:600;white-space:nowrap">{fmt(total)}</div></div>'
        f'<div><div style="color:#8892A4;font-size:11px">Títulos</div><div style="color:#fff;font-size:15px;font-weight:600;white-space:nowrap">{"••" if ocultar else titulos}</div></div>'
        f'<div><div style="color:#8892A4;font-size:11px">Clientes</div><div style="color:#fff;font-size:15px;font-weight:600;white-space:nowrap">{"••" if ocultar else clientes}</div></div></div>'
        '</div>'
        '<div style="color:#8892A4;font-size:11px;margin:0 0 6px">Recebimentos por dia (mais recente primeiro)</div>'
    )
    st.markdown(
        _CSS_GIRO
        + f'<div style="{_ANIM_GIRO}background:#1e1e2e;border-radius:8px;padding:12px 16px;min-height:400px">'
        + cabecalho
        + '<div style="max-height:255px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
        + linhas + '</div>'
        + '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'
        + '<span style="color:#8892A4;font-size:11px">Data = dia da baixa (pagamento no banco)</span></div>',
        unsafe_allow_html=True,
    )


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

    bloco_hoje = _bloco_recebimento_hoje(ocultar)
    if df_dia.empty:
        if bloco_hoje:
            st.markdown('<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px">' + bloco_hoje + '</div>',
                        unsafe_allow_html=True)
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
            f'<div class="an-wipe" style="animation-delay:{min(i, 14) * 45}ms;width:{barw:.1f}%;height:100%;background:rgba(79,163,224,{opac})"></div></div>'
            f'<span style="color:#ffffff;font-size:12px;text-align:right;white-space:nowrap">{val_txt}</span>'
            '</div>'
        )
    st.markdown(
        _CSS_GIRO
        + f'<div style="{_ANIM_GIRO}background:#1e1e2e;border-radius:8px;padding:12px 16px;min-height:400px">'
        + bloco_hoje
        + f'<div style="max-height:{255 if bloco_hoje else 375}px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
        + linhas
        + '</div>'
        + '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'
        + '<span style="color:#8892A4;font-size:11px">Data de crédito = vencimento + 1 dia útil</span>'
        + '</div>',
        unsafe_allow_html=True,
    )


_OPACIDADES_RANKING = ["1","1","1","0.70","0.55","0.45","0.38","0.32","0.28","0.24",
                        "0.21","0.18","0.16","0.14","0.12"]


def _ranking_clientes(df: pd.DataFrame, ocultar: bool = False, df_grupo_agentes=None, df_grupo_geral=None, altura_lista: int = 375):
    """Ranking dos top clientes/grupos com maior valor a vencer."""
    tem_grupos = (
        df_grupo_agentes is not None and not df_grupo_agentes.empty
        and {"COD_AGENTE", "COD_GRUPO"}.issubset(df_grupo_agentes.columns)
        and df_grupo_geral is not None and not df_grupo_geral.empty
        and {"GRUPO_CODIGO", "NOME_GRUPO"}.issubset(df_grupo_geral.columns)
    )

    if tem_grupos:
        col_t, _, _, col_m = st.columns(_COLUNAS_TITULO_BOTAO, vertical_alignment="center")
        with col_t:
            st.markdown("#### Top Clientes a Receber")
        with col_m:
            st.markdown(_CSS_BOTAO_CANTO, unsafe_allow_html=True)
            with st.container(key="cr_rank_canto"):
                modo = st.segmented_control(
                    "Agrupar por", ["Por Grupo", "Por Cliente"], default="Por Grupo",
                    key="cr_rank_modo_seg", label_visibility="collapsed", width="stretch",
                ) or "Por Grupo"
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
            f'<div class="an-wipe" style="animation-delay:{min(i, 14) * 45}ms;width:{barw:.1f}%;height:100%;background:rgba(46,204,113,{opac})"></div></div>'
            f'<span style="color:#ffffff;font-size:12px;text-align:right;white-space:nowrap">{val_txt}</span>'
            '</div>'
        )
    nota_rodape = (
        "agrupado por grupo econômico (Grupo de Crédito)"
        if modo == "Por Grupo"
        else "% sobre saldo total em aberto"
    )
    st.markdown(
        f'<div style="background:#1e1e2e;border-radius:12px;padding:16px 18px;width:100%;min-height:{altura_lista + 25}px">'
        + '<div style="color:#8892A4;font-size:11px;margin-bottom:8px">% sobre saldo total em aberto</div>'
        + f'<div style="max-height:{altura_lista}px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
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
    df = classificar_vencidos(df)
    df_ab = df[df["SALDO_EM_ABERTO"].fillna(0) > 0]
    tv    = df_ab[df_ab["CLASSIF_VENCIDO"] == "VENCIDO"]["SALDO_EM_ABERTO"].sum()
    tpdd  = df_ab[df_ab["CLASSIF_VENCIDO"] == "PDD"]["SALDO_EM_ABERTO"].sum()
    tav   = df_ab[df_ab["SITUACAO"] == "A VENCER"]["SALDO_EM_ABERTO"].sum()
    tg    = df_ab["SALDO_EM_ABERTO"].sum()
    qv    = len(df_ab[df_ab["CLASSIF_VENCIDO"] == "VENCIDO"])
    qav   = len(df_ab[df_ab["SITUACAO"] == "A VENCER"])
    qt    = len(df_ab)
    perc  = (tv / tg * 100) if tg > 0 else 0
    cor_p = (239, 68, 68) if perc > 20 else (245, 158, 11) if perc > 10 else (34, 197, 94)

    if ocultar:
        _v, _av, _tg, _p, _pdd = "••••••", "••••••", "••••••", "••••", "••••••"
    else:
        _v, _av, _tg, _p, _pdd = formatar_moeda(tv), formatar_moeda(tav), formatar_moeda(tg), f"{perc:.2f}%", formatar_moeda(tpdd)

    cards_para_imagem = [
        {"label": "Inadimplência", "valor": _p, "cor": cor_p},
        {"label": "Total Vencido", "valor": _v, "cor": (239, 68, 68)},
        *([] if ocultar_pdd() else [{"label": "Total PDD", "valor": _pdd, "cor": (139, 92, 246)}]),
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
        df_banco["_B"] = _banco_do_titulo(df_banco)
        bancos_img = (
            df_banco.groupby("_B")["SALDO_EM_ABERTO"].sum()
            .reset_index().query("SALDO_EM_ABERTO > 0")
            .sort_values("SALDO_EM_ABERTO", ascending=False)
        )
        _cores_banco_rgb = {
            "SANTANDER":       (226, 75,  74),
            "CAIXA ECONÔMICA": (92,  143, 214),
            "OUTROS":          (186, 117, 23),
            "TRANSFERÊNCIA":   (27, 173, 166),
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
        "VENCIMENTO": "Vencimento",
        "LIQUIDO_FIN": "Saldo Total",
        "SALDO_EM_ABERTO": "Saldo em Aberto",
        "DIAS": "Atraso",
        "CLASSIF_VENCIDO": "Classificação",
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
    for _c in ("ENTRADA", "VENCIMENTO"):
        if _c in df_img.columns:
            df_img[_c] = pd.to_datetime(df_img[_c], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
    if "COMPLEMENTO" in df_img.columns:
        df_img["COMPLEMENTO"] = df_img["COMPLEMENTO"].fillna("-").replace("", "-")
    df_img = df_img.rename(columns=colunas_origem)

    arquivo_excel = exportar_excel(df_excel, "TITULOS_VENCIDOS", colunas_situacao_sem_fundo=("Classificação",))

    # ── Rankings para a imagem ───────────────────────────────────────────────
    def _rank_img(df_base, situacao, cor, top=10):
        df_s = df_base[(df_base["SALDO_EM_ABERTO"].fillna(0) > 0) & (df_base["SITUACAO"] == situacao)
                       & (df_base["CLASSIF_VENCIDO"] != "PDD")]
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
        cards_por_linha=5,
    )
    botoes_acao_row(
        excel={"data": arquivo_excel, "file_name": "Contas_a_Receber_Vencidos.xlsx", "key": "cr_export_excel"},
        imagem={"data": imagem_png, "file_name": "Contas_a_Receber_Vencidos.png", "key": "cr_export_imagem"},
        copiar={"data": imagem_png, "key": "cr_copiar"},
    )


def _cards_totais(df: pd.DataFrame, ocultar: bool = False):
    """Cards principais. Vencido e Inadimplência só contam o que NÃO é PDD; o card de inadimplência tem um botão
    Vencido | Total (Total = vencido + PDD) no canto superior direito, aberto em "Vencido"."""
    df = classificar_vencidos(df)
    df_ab  = df[df["SALDO_EM_ABERTO"].fillna(0) > 0]
    ven    = df_ab[df_ab["CLASSIF_VENCIDO"] == "VENCIDO"]
    pdd    = df_ab[df_ab["CLASSIF_VENCIDO"] == "PDD"]
    tv     = ven["SALDO_EM_ABERTO"].sum()
    tpdd   = pdd["SALDO_EM_ABERTO"].sum()
    tav    = df_ab[df_ab["SITUACAO"] == "A VENCER"]["SALDO_EM_ABERTO"].sum()
    tg     = df_ab["SALDO_EM_ABERTO"].sum()
    qv, qpdd = len(ven), len(pdd)
    qav    = len(df_ab[df_ab["SITUACAO"] == "A VENCER"])
    qt     = len(df_ab)

    sem_pdd = ocultar_pdd()     # Admin > Opções do relatório: sem PDD não há card de PDD nem botão Vencido | Total
    modo   = "Vencido" if sem_pdd else (st.session_state.get("cr_inad_modo") or "Vencido")
    base   = tv + tpdd if modo == "Total" else tv
    perc   = (base / tg * 100) if tg > 0 else 0
    cor_p  = "#ef4444" if perc > 20 else "#f59e0b" if perc > 10 else "#22c55e"

    _v  = "••••••" if ocultar else formatar_moeda(tv)
    _pd = "••••••" if ocultar else formatar_moeda(tpdd)
    _av = "••••••" if ocultar else formatar_moeda(tav)
    _tg = "••••••" if ocultar else formatar_moeda(tg)
    _p  = "••••" if ocultar else f"{perc:.2f}%"
    _base = "••••••" if ocultar else formatar_moeda(base)

    sub_pdd = f"{qpdd} título(s) · acima de {DIAS_PDD} dias"
    if qpdd and qtd_acima_perda(pdd):
        sub_pdd += f" · {qtd_acima_perda(pdd)} acima de {DIAS_PDD_PERDA}"
    # Cada card ocupa a largura da sua coluna; o valor encolhe (até 15 px) se não couber, em vez de cortar.
    def _w(valor):
        return dict(largura="100%", tamanho_valor=tamanho_auto(valor, max_px=26, min_px=15, reserva=52))
    cards_tot = [
        card_html("Saldo Total em Aberto", _tg, f"{qt} título(s)", cor_borda="#6366f1", **_w(_tg)),
        card_html("Total a Vencer", _av, f"{qav} título(s)", cor_borda="#22c55e", **_w(_av)),
        card_html("Total Vencido", _v, f"{qv} título(s) · sem o PDD", cor_borda="#ef4444", **_w(_v)),
        card_html("Total PDD", _pd, sub_pdd, cor_borda=COR_PDD, cor_fundo="#241f3a", **_w(_pd)),
    ]
    if sem_pdd:
        cards_tot = cards_tot[:3]
    card_inad = card_html(
        "Inadimplência", _p, f"{'Vencido + PDD' if modo == 'Total' else 'Vencido'}: {_base}", cor_borda=cor_p, **_w(_p),
    )
    # Com 5 cards no notebook eles viram 3 + 2; sem o card de PDD são 4 e seguem em uma linha.
    _css_wrap_cards = "" if sem_pdd else (
        '.st-key-cr_cards_totais [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;row-gap:16px !important}'
        '.st-key-cr_cards_totais [data-testid="stColumn"]{flex:0 0 calc((100% - 2rem) / 3) !important;width:calc((100% - 2rem) / 3) !important;min-width:0 !important}'
    )
    st.markdown(
        "<style>"
        ".st-key-cr_inad_card{position:relative}"
        # o contêiner do botão sai do fluxo (senão ele soma altura ao card e abre um vão grande embaixo da linha de cards)
        '[data-testid="stLayoutWrapper"]:has(> .st-key-cr_inad_toggle){position:absolute;top:9px;right:8px;width:auto !important;height:auto !important;z-index:2}'
        ".st-key-cr_inad_toggle{width:auto !important}"
        ".st-key-cr_inad_toggle button{padding:1px 6px !important;min-height:20px !important;font-size:10px !important}"
        # Notebook (janela de até 1600 px, com a barra lateral aberta): os 5 cards viram 3 + 2 e os 4 quadros viram 2 + 2,
        # para nada ficar espremido ou cortado. Em monitor grande segue tudo em uma linha.
        "@media (max-width:1600px){"
        + _css_wrap_cards +
        # o Streamlit põe margem de -16px no fim do markdown e o card passa da altura da coluna, comendo o espaço entre as linhas
        '.st-key-cr_cards_totais [data-testid="stMarkdownContainer"]{margin-bottom:0 !important}'
        '.st-key-cr_blocos_resumo [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;row-gap:24px !important}'
        '.st-key-cr_blocos_resumo [data-testid="stColumn"]{flex:0 0 calc((100% - 1rem) / 2) !important;width:calc((100% - 1rem) / 2) !important;min-width:0 !important}'
        "}"
        "</style>",
        unsafe_allow_html=True,
    )
    # Os 5 cards em uma linha só, cada um com a largura de uma coluna (no notebook com a barra aberta cada um fica com
    # ~245 px; o valor encolhe sozinho se não couber). O botão Vencido | Total fica no canto do card de Inadimplência.
    with st.container(key="cr_cards_totais"):
        _cols = st.columns(4 if sem_pdd else 5)
        for _k, _card in enumerate(cards_tot):
            with _cols[_k]:
                st.markdown(_card, unsafe_allow_html=True)
        with _cols[-1]:
            with st.container(key="cr_inad_card"):
                st.markdown(card_inad, unsafe_allow_html=True)
                if not sem_pdd:
                    with st.container(key="cr_inad_toggle"):
                        st.segmented_control("Inadimplência", ["Vencido", "Total"], default="Vencido", required=True,
                                             key="cr_inad_modo", label_visibility="collapsed",
                                             help="Vencido = sem o PDD · Total = vencido + PDD")


# ── Aba Resumo: tabela + gráfico ──────────────────────────────────────────────

# Altura da tabela Títulos Vencidos: igual à soma dos blocos da coluna da direita (Vencido por Cliente + Faixa de
# Atraso), que têm altura fixa; assim as duas colunas terminam na mesma linha.
_ALTURA_RESUMO_VENCIDOS = 548

# Faixas de atraso do vencido: o vermelho escurece conforme o atraso aumenta (nome, ini, fim, cor da barra, cor do %).
# O % usa tom claro mesmo nas faixas escuras, para continuar legível no fundo escuro.
_FAIXAS_ATRASO = [
    ("1 a 30 dias", 1, 30, "#fca5a5", "#fca5a5"),
    ("31 a 60 dias", 31, 60, "#f87171", "#f87171"),
    ("61 a 90 dias", 61, 90, "#dc2626", "#f87171"),
    ("Mais de 90", 91, 10**6, "#991b1b", "#f87171"),
]


def _bloco_faixas_vencido(df_venc: pd.DataFrame, ocultar: bool = False) -> str:
    """Bloco "Vencido por Faixa de Atraso": destaque do vencido há mais de 30 dias e barras por faixa de atraso
    (dias desde o vencimento), com o vermelho mais escuro nas faixas mais antigas."""
    if df_venc.empty or "DIAS" not in df_venc.columns:
        return ""
    d = df_venc[["SALDO_EM_ABERTO", "DIAS"] + (["CLIENTE"] if "CLIENTE" in df_venc.columns else [])].copy()
    d["_ATR"] = pd.to_numeric(d["DIAS"], errors="coerce").abs()
    d = d.dropna(subset=["_ATR"])
    total = d["SALDO_EM_ABERTO"].sum()
    if total <= 0:
        return ""
    fmt = lambda v: "••••••" if ocultar else formatar_moeda(v)
    pct_fmt = lambda v: "••" if ocultar else f"{v:.2f}".replace(".", ",") + "%"
    criticos = d[d["_ATR"] > 30]
    v30 = criticos["SALDO_EM_ABERTO"].sum()
    linhas_cr = f"{len(criticos)} título(s)" + (f" · {criticos['CLIENTE'].nunique()} cliente(s)" if "CLIENTE" in criticos.columns else "")
    maior = int(d["_ATR"].max())
    faixas = []
    for nome, ini, fim, cor, cor_pct in _FAIXAS_ATRASO:
        if ini > DIAS_PDD:      # acima do limite de PDD o título sai do vencido: a faixa fica sem títulos e não aparece
            continue
        v = d[(d["_ATR"] >= ini) & (d["_ATR"] <= fim)]["SALDO_EM_ABERTO"].sum()
        faixas.append((nome, v, cor, cor_pct))
    maximo = max((v for _, v, _, _ in faixas), default=0) or 1
    linhas = ""
    for nome, v, cor, cor_pct in faixas:
        linhas += (
            '<div style="display:grid;grid-template-columns:78px minmax(0,1fr) 48px 118px;gap:8px;align-items:center;'
            'font-size:13px;padding:3px 0">'
            f'<span style="color:#e0e0e0;white-space:nowrap">{nome}</span>'
            '<div style="height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
            f'<div style="width:{v / maximo * 100:.1f}%;height:100%;background:{cor}"></div></div>'
            f'<span style="color:{cor_pct};font-size:11px;font-weight:600;text-align:right;white-space:nowrap">{pct_fmt(v / total * 100)}</span>'
            f'<span style="color:#8892A4;font-size:12px;text-align:right;white-space:nowrap">{fmt(v)}</span></div>'
        )
    return (
        '<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px">'
        '<div style="display:flex;justify-content:space-between;align-items:flex-end;gap:10px;flex-wrap:wrap;'
        'background:#252B3D;border:1px solid #3a4160;border-left:4px solid #991b1b;border-radius:8px;padding:9px 12px;margin-bottom:10px">'
        '<div><div style="color:#8892A4;font-size:11px">Vencido há mais de 30 dias</div>'
        f'<div style="color:#fff;font-size:20px;font-weight:600;white-space:nowrap">{fmt(v30)}</div></div>'
        '<div style="text-align:right;color:#8892A4;font-size:11px">'
        f'<div>{linhas_cr}</div>'
        f'<div><span style="color:#E24B4A;font-weight:600">{pct_fmt(v30 / total * 100)}</span> do vencido · maior atraso '
        f'<span style="color:#E24B4A;font-weight:600">{"••" if ocultar else maior} dias</span></div></div></div>'
        + linhas
        + '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'
        + '<span style="color:#8892A4;font-size:11px">% sobre o total vencido · dias de atraso desde o vencimento</span>'
        + '</div>'
    )


def _bloco_vencido_por_cliente(df: pd.DataFrame, df_venc: pd.DataFrame, ocultar: bool = False):
    """Painel "Vencido por Cliente" (título + barras)."""
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
            val_txt = "••••••" if ocultar else formatar_moeda(row["SALDO_EM_ABERTO"])
            pct_txt = "••" if ocultar else f"{pct:.2f}%"
            linhas_v += (
                '<div style="display:grid;grid-template-columns:20px minmax(0,1fr) 42px minmax(0,1fr) 130px;'
                'gap:8px;align-items:center;font-size:13px;padding:4px 0">'
                f'<span style="color:#8892A4;font-size:11px;font-weight:600;text-align:center">{i+1}</span>'
                f'<span style="color:#e0e0e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{nome}</span>'
                f'<span style="color:#E24B4A;font-size:11px;font-weight:600;text-align:right;white-space:nowrap">{pct_txt}</span>'
                f'<div style="height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden">'
                f'<div style="width:{barw:.1f}%;height:100%;background:rgba(226,75,74,{opac})"></div></div>'
                f'<span style="color:#8892A4;font-size:12px;text-align:right;white-space:nowrap">{val_txt}</span>'
                '</div>'
            )
        st.markdown(
            '<div style="background:#1e1e2e;border-radius:8px;padding:12px 16px">'
            + '<div style="height:190px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
            + linhas_v
            + '</div>'
            + '<div style="height:1px;background:#2a2a3a;margin:6px 0"></div>'
            + '<span style="color:#8892A4;font-size:11px">% sobre saldo total em aberto</span>'
            + '</div>',
            unsafe_allow_html=True,
        )


def _html_classificacao(valor) -> str:
    """VENCIDO em vermelho, PDD em roxo (negrito); vazio quando não é título vencido."""
    if valor == "PDD":
        return f'<span style="color:{COR_PDD_TEXTO};font-weight:700">PDD</span>'
    if valor == "VENCIDO":
        return '<span style="color:#E24B4A;font-weight:700">VENCIDO</span>'
    return ""


def _aba_resumo(df: pd.DataFrame, ocultar: bool = False):
    df = classificar_vencidos(df)
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
            colunas = [c for c in ["CLIENTE", "NF", "ENTRADA", "VENCIMENTO", "LIQUIDO_FIN", "SALDO_EM_ABERTO", "DIAS_VENCIDO", "CLASSIF_VENCIDO", "COMPLEMENTO"]
                       if c in df_venc.columns]
            df_exib = df_venc[colunas].copy()
            for _c in ("ENTRADA", "VENCIMENTO"):
                if _c in df_exib.columns:
                    df_exib[_c] = pd.to_datetime(df_exib[_c], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
            if "DIAS_VENCIDO" in df_exib.columns:
                df_exib["DIAS_VENCIDO"] = df_exib["DIAS_VENCIDO"].apply(
                    lambda x: formatar_dias_html(x, VERMELHO_DIAS, negrito=True) if pd.notna(x) else "-"
                )
            for _c in ("LIQUIDO_FIN", "SALDO_EM_ABERTO"):
                if _c in df_exib.columns:
                    df_exib[_c] = df_exib[_c].apply(lambda v: "••••••" if ocultar else formatar_moeda(v))
            if "COMPLEMENTO" in df_exib.columns:
                df_exib["COMPLEMENTO"] = df_exib["COMPLEMENTO"].fillna("-").replace("", "-")
            if "CLASSIF_VENCIDO" in df_exib.columns:
                df_exib["CLASSIF_VENCIDO"] = df_exib["CLASSIF_VENCIDO"].apply(_html_classificacao)
            render_tabela_html(
                df_exib,
                colunas_renomear={
                    "CLIENTE": "Cliente", "NF": "NF", "ENTRADA": "Entrada", "VENCIMENTO": "Vencimento",
                    "LIQUIDO_FIN": "Saldo Total", "SALDO_EM_ABERTO": "Saldo em Aberto",
                    "DIAS_VENCIDO": "Dias Vencto.", "CLASSIF_VENCIDO": "Classificação", "COMPLEMENTO": "Complemento",
                },
                colunas_centralizar=["CLASSIF_VENCIDO"],
                colunas_moeda=["LIQUIDO_FIN", "SALDO_EM_ABERTO"],
                coluna_complemento="COMPLEMENTO",
                altura=_ALTURA_RESUMO_VENCIDOS, altura_fixa=True,
            )

            st.markdown("---")
            _botao_salvar_imagem(df, ocultar=ocultar)

    with col_chart:
        # Vencido por Cliente e Faixa de Atraso: só o vencido que NÃO é PDD
        df_venc_sem_pdd = df_venc[df_venc["CLASSIF_VENCIDO"] == "VENCIDO"]
        _bloco_vencido_por_cliente(df, df_venc_sem_pdd, ocultar)

        bloco_faixas = _bloco_faixas_vencido(df_venc_sem_pdd, ocultar=ocultar)
        if bloco_faixas:
            st.markdown("#### Vencido por Faixa de Atraso")
            st.markdown(bloco_faixas, unsafe_allow_html=True)


# ── Aba Títulos em Aberto ─────────────────────────────────────────────────────

COLUNAS_EXIBIR = [
    "COD_CLIENTE", "CLIENTE", "VENDEDOR",
    "PARCELA", "TIPO_DOC", "NF", "FATURAMENTO",
    "ENTRADA", "VENCIMENTO", "PRORROGADO",
    "DIAS_VENCIDO", "SITUACAO", "CLASSIF_VENCIDO",
    "LIQUIDO_FIN", "SALDO_EM_ABERTO",
    "BANCO_NOME", "SITUACAO_BOLETO", "CENTRO_CUSTO",
]
COLUNAS_MOEDA = ["LIQUIDO_FIN", "SALDO_EM_ABERTO"]
COLUNAS_DATA  = ["ENTRADA", "VENCIMENTO", "PRORROGADO", "FATURAMENTO"]
COR_SITUACAO  = {"VENCIDO": "#3d1a1a", "A VENCER": "#1a3d1a", "PAGO": "#2a2a2a"}

def _aba_aberto(df: pd.DataFrame, ocultar: bool = False):
    df = classificar_vencidos(df)
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
            df_exib[col] = df_exib[col].apply(lambda v: "••••••" if ocultar else formatar_moeda(v))

    if "DIAS_VENCIDO" in df_exib.columns and "SITUACAO" in df_exib.columns:
        df_exib["DIAS_VENCIDO"] = df_exib.apply(formatar_dias_unificado_html, axis=1)

    if "CLASSIF_VENCIDO" in df_exib.columns:
        df_exib["CLASSIF_VENCIDO"] = df_exib["CLASSIF_VENCIDO"].apply(_html_classificacao)
    render_tabela_html(
        df_exib,
        colunas_renomear={"DIAS_VENCIDO": "Dias Vencto.", "SITUACAO": "Situação Vencto.", "CLASSIF_VENCIDO": "Classificação"},
        colunas_moeda=["LIQUIDO_FIN", "SALDO_EM_ABERTO"],
        coluna_situacao="SITUACAO",
        colunas_centralizar=["DIAS_VENCIDO", "SITUACAO", "CLASSIF_VENCIDO"],
    )

    st.markdown("---")
    # Exporta os dados numéricos crus (df_tab), não a versão formatada em texto
    # (df_exib) — assim as colunas de moeda saem como número real no Excel.
    df_excel = df_tab[colunas].rename(columns={"DIAS_VENCIDO": "Dias Vencto.", "SITUACAO": "Situação Vencto.", "CLASSIF_VENCIDO": "Classificação"})
    excel_bytes = exportar_excel(
        df_excel, nome_aba="Títulos em Aberto",
        colunas_verde_vermelho=("Dias Vencto.",),
        colunas_situacao_sem_fundo=("Situação Vencto.", "Classificação"),
    )
    botao_exportar_excel(excel_bytes, "titulos_em_aberto.xlsx", key="cr_export_aberto")


# ── Entry point ───────────────────────────────────────────────────────────────

def render(df: pd.DataFrame, mostrar_titulo: bool = True, df_grupo_agentes=None, df_grupo_geral=None) -> None:
    df_filtrado = classificar_vencidos(df)     # CLASSIF_VENCIDO: VENCIDO ou PDD nos vencidos

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
            st.button(
                "Ocultar" if not _oc else "Exibir",
                icon=":material/visibility_off:" if not _oc else ":material/visibility:",
                key="btn_ocultar_cr", use_container_width=True,
                help="Ocultar/exibir valores",
                on_click=lambda: st.session_state.update(cr_ocultar=not st.session_state.get("cr_ocultar", False)),
            )
        with col_atualizar:
            st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
            st.button("🔄 Atualizar", key="cr_mi_atualizar", use_container_width=True, on_click=st.cache_data.clear)

    st.divider()
    _cards_totais(df_filtrado, ocultar=st.session_state["cr_ocultar"])
    st.divider()

    # Card "Descontos Pendentes" só para quem tem acesso ao relatório de pendentes: a faixa passa a ter 4 cards (Situação
    # em coluna estreita, rosca em cima); sem acesso, ficam os 3 de sempre.
    _desc = (
        resumo_descontos_pendentes(df_filtrado)
        if "📄 Descontos Contratuais Pendentes MI" in st.session_state.get("_relatorios_visiveis", ()) else None
    )
    with st.container(key="cr_blocos_resumo"):
        if _desc is not None:
            col_aging, col_sit, col_desc, col_banco = st.columns([1.0, 0.55, 0.55, 1.0])
        else:
            col_aging, col_sit, col_banco = st.columns([1.1, 0.75, 1.15])
            col_desc = None
        with col_aging:
            _cards_aging_a_vencer(df_filtrado, ocultar=st.session_state["cr_ocultar"])
        with col_sit:
            _card_situacao_rosca(df_filtrado, ocultar=st.session_state["cr_ocultar"], vertical=_desc is not None)
        if col_desc is not None:
            with col_desc:
                _card_descontos_pendentes(_desc, ocultar=st.session_state["cr_ocultar"])
        with col_banco:
            _cards_banco(df_filtrado, ocultar=st.session_state["cr_ocultar"])

    st.divider()
    col_tb, col_rank = st.columns([1, 1])
    with col_tb:
        _card_recebimentos_dia(df_filtrado, ocultar=st.session_state["cr_ocultar"])
    with col_rank:
        _ranking_clientes(df_filtrado, ocultar=st.session_state["cr_ocultar"], df_grupo_agentes=df_grupo_agentes, df_grupo_geral=df_grupo_geral)

    st.divider()

    aba_resumo, aba_aberto = st.tabs(["Resumo", "Títulos em Aberto"])

    with aba_resumo:
        _aba_resumo(df_filtrado, ocultar=st.session_state["cr_ocultar"])

    with aba_aberto:
        _aba_aberto(df_filtrado, ocultar=st.session_state["cr_ocultar"])
