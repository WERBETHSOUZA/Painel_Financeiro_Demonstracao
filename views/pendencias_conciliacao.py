"""Pendências de Conciliação (Tesouraria): lançamentos do extrato bancário ainda não conciliados no Mega, das contas com conciliação automática.
Período com calendário (abre no mês vigente) e botão Gerar Relatório, organização (abre na Demo; sem nenhuma marcada traz todas as empresas) e filtros de conta/natureza (a importação, manual ou automática, aparece sempre), cards, resumo por banco,
detalhe e saídas em Excel e PDF."""
import calendar
import datetime

import pandas as pd
import streamlit as st

from components.buttons import botoes_acao_row
from components.cards import card_html, render_cards_row, render_tabela_html
from utils.exporters import exportar_excel
from utils.imagem_email import gerar_imagem_pendencias_conciliacao
from utils.pdf_conciliacao import gerar_pdf, nome_empresa
from views.contas_receber import formatar_moeda

_MANUAL = "Importação Manual"
_gerar_imagem_cached = st.cache_data(show_spinner=False, max_entries=20)(gerar_imagem_pendencias_conciliacao)
_gerar_pdf_cached = st.cache_data(show_spinner="Preparando o PDF...", max_entries=10)(gerar_pdf)       # pronto antes do clique: o botão abre o PDF numa aba nova na hora


def _fmt_importacao(v) -> str:
    return _MANUAL if pd.isna(v) else f"{pd.Timestamp(v):%d/%m/%Y %H:%M}"


def render(carregar, carregar_organizacoes, carregar_contas) -> None:
    """`carregar(data_inicio, data_fim)` busca no banco só o período escolhido (datas DD/MM/AAAA); `carregar_organizacoes()` lista as organizações do filtro e
    `carregar_contas()` as contas de cada uma (o filtro Conta mostra só as da organização escolhida, mesmo antes de gerar o relatório)."""
    c_t, c_at = st.columns([8, 1])
    with c_t:
        st.title("Pendências de Conciliação")
    with c_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="pc_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── Período (barra lateral): abre no mês vigente; só o período gerado vai ao banco ──
    hoje = datetime.date.today()
    mes_vigente = (hoje.replace(day=1), hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]))
    orgs = carregar_organizacoes()
    if orgs is None or orgs.empty:
        st.warning("Não foi possível listar as organizações agora. Use Atualizar para tentar de novo.")
        return
    orgs = orgs.sort_values("COD_ORG").reset_index(drop=True)
    nomes_org = {int(c): nome_empresa(n) for c, n in zip(orgs["COD_ORG"], orgs["ORGANIZACAO"])}
    with st.sidebar:
        st.caption("Pendências de Conciliação")
        # abre só com a primeira da lista marcada (Demo); desmarcando tudo o relatório traz todas as empresas, e dá para marcar mais de uma
        org_sel = st.multiselect("Organização", list(nomes_org), default=[next(iter(nomes_org))], key="pc_org", placeholder="Todas as empresas",
                                 format_func=lambda c: f"{c} - {nomes_org[c]}", help="Abre na Demo. Marque uma ou mais; sem nenhuma marcada, traz todas as empresas.")
        periodo = st.date_input("Data do lançamento (período)", value=mes_vigente, format="DD/MM/YYYY", key="pc_periodo",
                                help="Data do lançamento no extrato; abre no mês vigente. Só o período escolhido é buscado no banco; o dia final entra.")
        # Conta: só as contas das organizações escolhidas (todas, se nenhuma marcada); chave própria por escolha, para não carregar a seleção de outra
        contas_df = carregar_contas()
        contas_org = {}
        if contas_df is not None and not contas_df.empty:
            doc = contas_df[contas_df["COD_ORG"].astype(int).isin([int(c) for c in org_sel])] if org_sel else contas_df
            contas_org = {int(c): str(n) for c, n in zip(doc["COD_BANCO"], doc["CONTA"])}
        conta_sel = st.multiselect("Conta", sorted(contas_org), key="pc_conta_" + ("_".join(str(c) for c in sorted(org_sel)) or "todas"), placeholder="Todas as contas",
                                   format_func=lambda c: f"{c} - {contas_org.get(c, '')}")
        nat_sel = st.multiselect("Natureza", ["Crédito", "Débito"], key="pc_nat", placeholder="Crédito e Débito",
                                 help="Sem seleção, o relatório traz Crédito e Débito; escolha uma só para filtrar.")
        gerar = st.button("Gerar Relatório", use_container_width=True, key="pc_gerar")
    if gerar:
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            st.session_state["_pc_periodo"] = (periodo[0], periodo[1])
            st.session_state["_pc_org"] = [int(c) for c in org_sel]
        else:
            st.session_state.pop("_pc_periodo", None)
            st.session_state.pop("_pc_org", None)
            st.warning("Selecione a data inicial e a final do período na barra lateral e clique em Gerar Relatório.")
            return
    sel = st.session_state.get("_pc_periodo")
    if not sel:
        st.info("O período abre no **mês vigente** e a organização em **Demo**. Ajuste-os na barra lateral, se precisar (sem nenhuma organização marcada, o relatório traz **todas as empresas**), e clique em **Gerar Relatório**.")
        return
    dt_ini, dt_fim = sel
    _guardada = st.session_state.get("_pc_org", [int(c) for c in org_sel])
    orgs_ger = [int(c) for c in (_guardada if isinstance(_guardada, (list, tuple)) else [_guardada])]       # organizações do relatório gerado; vazio = todas as empresas
    nome_org = ", ".join(nomes_org.get(c, str(c)) for c in orgs_ger) if orgs_ger else "Todas as empresas"
    st.caption(f"Organização: **{', '.join(f'{c} - ' + nomes_org.get(c, '') for c in orgs_ger) if orgs_ger else 'Todas as empresas'}** · período {dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}")

    with st.spinner("Carregando as pendências de conciliação..."):
        df = carregar(dt_ini.strftime("%d/%m/%Y"), dt_fim.strftime("%d/%m/%Y"))
    df = df if (df is None or not orgs_ger) else df[df["COD_ORG"].astype(int).isin(orgs_ger)]
    if df is None or df.empty:
        st.success(f"Nenhuma pendência de conciliação de {nome_org} entre {dt_ini:%d/%m/%Y} e {dt_fim:%d/%m/%Y}.")
        return
    df = df.assign(EMPRESA=df["ORGANIZACAO"].map(nome_empresa))

    # ── Filtros (barra lateral, acima): conta e natureza; valem para cards, resumo, tabela, Excel, PNG e PDF ──
    d = df
    if conta_sel and sorted(int(c) for c in org_sel) == sorted(orgs_ger):          # a conta escolhida é das organizações do relatório gerado; senão só vale depois de gerar de novo
        d = d[d["COD_BANCO"].astype(int).isin(conta_sel)]
    if nat_sel:                                   # sem seleção traz as duas naturezas; só filtra quando uma é escolhida
        d = d[d["NATUREZA"].isin(nat_sel)]
    if d.empty:
        st.info("Nenhuma pendência para os filtros escolhidos.")
        return

    cred = d["NATUREZA"].eq("Crédito")
    varias = d["EMPRESA"].nunique() > 1            # mais de uma empresa: as tabelas ganham a coluna Empresa
    n_man = int(d["DATA_IMPORTACAO"].isna().sum())
    render_cards_row([
        card_html("Lançamentos pendentes", str(len(d)),
                  f"em {d['CONTA'].nunique()} conta(s)" + (f" · {d['EMPRESA'].nunique()} empresas" if varias else "") + (f" · {n_man} de importação manual" if n_man else ""),
                  cor_borda="#378ADD", largura="280px"),
        card_html("Débitos pendentes", formatar_moeda(d.loc[~cred, "VALOR"].sum()), f"{int((~cred).sum())} lançamento(s)", cor_borda="#E24B4A", largura="280px"),
        card_html("Créditos pendentes", formatar_moeda(d.loc[cred, "VALOR"].sum()), f"{int(cred.sum())} lançamento(s)", cor_borda="#22c55e", largura="280px"),
    ])
    st.divider()

    # ── Resumo por banco ──
    st.subheader("Resumo por banco")
    resumo = (d.assign(_CRED=d["VALOR"].where(cred, 0.0), _DEB=d["VALOR"].where(~cred, 0.0), _MAN=d["DATA_IMPORTACAO"].isna().astype(int))
               .groupby(["EMPRESA", "COD_BANCO", "CONTA"], as_index=False)
               .agg(QTD=("VALOR", "size"), CRED=("_CRED", "sum"), DEB=("_DEB", "sum"), MAN=("_MAN", "sum"), ANT=("DATA", "min"))
               .sort_values(["EMPRESA", "QTD"], ascending=[True, False]))
    tela_resumo = pd.DataFrame({
        **({"Empresa": resumo["EMPRESA"]} if varias else {}),
        "Cód.": resumo["COD_BANCO"].astype(int), "Banco": resumo["CONTA"], "Pendências": resumo["QTD"].astype(int),
        "Créditos": resumo["CRED"].map(lambda v: formatar_moeda(v) if v else "—"), "Débitos": resumo["DEB"].map(lambda v: formatar_moeda(v) if v else "—"),
        "Imp. manual": resumo["MAN"].astype(int), "Mais antigo": resumo["ANT"].dt.strftime("%d/%m/%Y")})
    render_tabela_html(tela_resumo, colunas_moeda=["Créditos", "Débitos"], colunas_centralizar=["Cód.", "Pendências", "Imp. manual", "Mais antigo"], altura=300)
    st.divider()

    # ── Detalhe ──
    c_tit, c_qtd = st.columns([6, 1], vertical_alignment="center")
    with c_tit:
        st.subheader("Lançamentos pendentes")
    with c_qtd:
        st.caption(f"{len(d)} registro(s)")
    d = d.sort_values(["EMPRESA", "CONTA", "DATA"], kind="stable")
    nat_html = d["NATUREZA"].map(lambda n: f'<span style="color:{"#6fd69a" if n == "Crédito" else "#f3a3a2"}">{n}</span>')
    imp_html = d["DATA_IMPORTACAO"].map(lambda v: f'<span style="color:#f5c070;font-weight:600">{_MANUAL}</span>' if pd.isna(v) else _fmt_importacao(v))
    tela = pd.DataFrame({
        **({"Empresa": d["EMPRESA"]} if varias else {}),
        "Cód.": d["COD_BANCO"].astype(int), "Banco": d["CONTA"], "Data": d["DATA"].dt.strftime("%d/%m/%Y"), "Docto Banco": d["DOCTO_BANCO"].fillna(""),
        "Tipo Docto": d["TIPO_DOCTO"].fillna(""), "Histórico": d["HISTORICO"].fillna(""), "Valor": d["VALOR"].map(formatar_moeda),
        "Natureza": nat_html, "Importação": imp_html})
    render_tabela_html(tela, colunas_moeda=["Valor"], altura=480)

    # ── Excel e PDF (gerados só no clique) ──
    excel_df = pd.DataFrame({
        "Organização": d["EMPRESA"], "Cód. Banco": d["COD_BANCO"], "Banco": d["CONTA"], "Data": d["DATA"], "Docto Banco": d["DOCTO_BANCO"],
        "Tipo Docto": d["TIPO_DOCTO"], "Histórico": d["HISTORICO"], "Valor": d["VALOR"], "Natureza": d["NATUREZA"],
        "Importação": d["DATA_IMPORTACAO"].map(_fmt_importacao)})
    sufixo = (nome_org.split()[0].title() if len(orgs_ger) == 1 else "Todas" if not orgs_ger else "Varias") + "_"
    base_nome = f"Pendencias_Conciliacao_{sufixo}{datetime.date.today():%d%m%Y}"       # dia, mês e ano (23112026)
    titulo_img = f"Pendências de Conciliação — {nome_org} — {dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}"
    imagem_bytes = _gerar_imagem_cached(d, titulo=titulo_img)
    pdf_bytes = _gerar_pdf_cached(d, dt_ini, dt_fim)
    # linha padrão: Excel baixa; PDF e imagem abrem numa aba nova do navegador (de lá se baixa, se quiser)
    botoes_acao_row(
        excel={"data": lambda: exportar_excel(excel_df, "PENDENCIAS_CONCILIACAO", colunas_moeda=("Valor",),
                                              titulo_planilha=f"Pendências de conciliação - {dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}"),
               "file_name": f"{base_nome}.xlsx", "key": "pc_excel"},
        imagem={"data": imagem_bytes, "file_name": f"{base_nome}.png", "key": "pc_img"},
        pdf={"data": pdf_bytes, "file_name": f"{base_nome}.pdf", "key": "pc_pdf"},
    )
