"""Painel Tesouraria > Inconsistências de Lançamentos: lançamentos do período que quebram alguma regra (uma consulta por regra em
query/inconsistencias). Layout: barra lateral com o período e o solicitante; no corpo, o card escuro com os botões de regra (com a contagem) e a
tabela (rolagem interna); Excel e imagem logo abaixo. Linha ao passar o mouse: AP, classe, centro de custo, conta do agente e observação."""
import calendar
import datetime
from html import escape

import streamlit as st
import pandas as pd
from components.buttons import botoes_acao_row
from utils.exporters import exportar_excel
from utils.imagem_email import gerar_imagem_inconsistencias
from services.email_service import obter_obs_inconsistencia

# cor de cada regra: (traço, fundo da etiqueta, texto da etiqueta); regra nova sem cor aqui pega a próxima da paleta
_COR_REGRA = {
    "ERRO TIPO FAVORECIDO CLIENTE": ("#E24B4A", "rgba(226,75,74,.25)", "#f3a3a2"),
    "ERRO ACAO SEGMENTO": ("#BA7517", "rgba(186,117,23,.25)", "#f5c070"),
    "ERRO ACAO BAIXA EMPRESTIMO": ("#4A7FB5", "rgba(74,127,181,.25)", "#8ec2f5"),
    "ERRO CLASSE ADIANTAMENTO": ("#7B68B5", "rgba(123,104,181,.25)", "#c3b8ee"),
    "ERRO CLASSE 271 AGENTE NAO EMPRESTIMO": ("#1BADA6", "rgba(27,173,166,.25)", "#7fdcd7"),
    "ERRO BAIXA ND A PAGAR": ("#D4537E", "rgba(212,83,126,.25)", "#f2a5c0"),
    "ERRO BAIXA ND A RECEBER": ("#8FBF3F", "rgba(143,191,63,.22)", "#c5e08f"),
}
_PALETA_EXTRA = [("#2ECC71", "rgba(46,204,113,.2)", "#8be6b0"), ("#E8724A", "rgba(232,114,74,.25)", "#f5b090"), ("#1BADA6", "rgba(27,173,166,.25)", "#7fdcd7")]
_GRADE = "150px 150px 190px 175px 110px minmax(200px,1fr) 88px minmax(200px,1fr) 104px 330px 150px"        # larguras fixas: o título de uma coluna nunca cai em cima de outra

_gerar_imagem_cached = st.cache_data(show_spinner=False, max_entries=20)(gerar_imagem_inconsistencias)


def _inteiros_sem_decimal(df: pd.DataFrame) -> pd.DataFrame:
    """Códigos e números (AP, Num_Lancto, Cód_Agente...) chegam do Oracle como decimal (409305.0). Colunas numéricas cujos
    valores são todos inteiros viram inteiro, na tela, no Excel e na imagem. Valores em dinheiro (SALDO) ficam como estão."""
    df = df.copy()
    for c in df.columns:
        if "SALDO" in c or "VALOR" in c or not pd.api.types.is_float_dtype(df[c]):
            continue
        v = df[c].dropna()
        if len(v) and (v % 1 == 0).all():
            df[c] = df[c].astype("Int64").astype(object).where(df[c].notna(), None)
    return df


def _cores(regras: list) -> dict:
    """Cor de cada regra da tela, na ordem em que aparecem; as sem cor definida usam a paleta extra."""
    saida, extras = {}, iter(_PALETA_EXTRA)
    for r in regras:
        saida[r] = _COR_REGRA.get(r) or next(extras, ("#9ca3af", "rgba(156,163,175,.22)", "#d1d5db"))
    return saida


_ORIGEM = {"MOVIMENTO FINANCEIRO": "Mov. Financeiro", "MOV. CONTAS A PAGAR": "Mov. Contas a Pagar", "CONTAS A PAGAR": "Contas a Pagar", "CONTAS A RECEBER": "Contas a Receber"}


def numeracao(r: dict) -> str:
    """Número do documento em destaque (branco, negrito)."""
    return f'<b style="color:#fff;font-size:14px;font-weight:700">{escape(_txt(r.get("DOCUMENTO")))}</b>'


def numero_ap(r: dict) -> str:
    """AP em destaque (branco, negrito): vem do lançamento do contas a pagar ou, na movimentação (acréscimo...), da AP do documento; varias parcelas
    mostram a lista. Só o lançado direto no movimento financeiro não tem AP (traço)."""
    ap = _txt(r.get("AP"))
    if not ap:
        return '<span style="color:#6b7385">-</span>'
    try:
        ap = str(int(float(ap)))
    except ValueError:
        pass
    return f'<b style="color:#fff;font-size:14px;font-weight:700">{escape(ap)}</b>'


def agente(r: dict, papel: str) -> str:
    """"código · nome" do banco (conta financeira) ou do fornecedor da operação; vazio quando a operação não tem aquele lado."""
    cod, nome = _txt(r.get(f"COD_{papel}")), _txt(r.get(f"NOME_{papel}"))
    try:
        cod = str(int(float(cod))) if cod else ""
    except ValueError:
        pass
    return f"{cod} · {nome}" if cod and nome else cod or nome


def _acao(r: dict) -> str:
    """Código e nome da ação: "255 - Rural - Devolução de Adiantamento"."""
    cod, nome = _txt(r.get("COD_ACAO")), _txt(r.get("ACAO"))
    return f"{cod} - {nome}" if cod and nome else cod or nome


def detalhe_erro(r: dict) -> str:
    """A evidência do erro, conforme o tipo: erro de ação mostra o código e a ação; erro de classe, a classe (e o centro de custo); erro de projeto, o
    projeto. Regra de outro tipo (ex.: favorecido cliente) mostra a ação. Várias regras no mesmo lançamento juntam as evidências."""
    cats = _txt(r.get("CATEGORIA_ERRO")).upper()
    partes = []
    if "CLASSE" in cats:
        classe = _txt(r.get("CLASSE")).replace(chr(10), " | ")
        cc = _txt(r.get("CENTRO_CUSTO")).replace(chr(10), " | ")
        partes.append("Classe: " + classe + (f" · CC: {cc}" if cc else ""))
    if "AGENTE" in cats:
        partes.append("Grupo financeiro: " + (_txt(r.get("GRUPO_FINANCEIRO")) or "sem grupo"))
    if "PROJETO" in cats:
        partes.append("Projeto: " + _txt(r.get("PROJETO")).replace(chr(10), " | "))
    if "ACAO" in cats or not partes:
        partes.insert(0, _acao(r))
    return " | ".join(x for x in partes if x)


def _nome_curto(regra: str) -> str:
    return str(regra).replace("ERRO ", "")


def _txt(v) -> str:
    return "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)


def _html_card(df: pd.DataFrame, cores: dict, dt_ini, dt_fim, coluna_cat: str, ocultar: bool = False) -> str:
    """O card escuro: título, contagem e a tabela com rolagem interna."""
    n_sol = df["SOLICITANTE"].nunique() if "SOLICITANTE" in df.columns else 0
    grade = _GRADE
    largura = 1960
    cabeca = ('<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
              '<span style="color:#e0e0e0;font-size:14px;font-weight:600">Inconsistências de lançamento</span>'
              f'<span style="font-size:11px;color:#8892a4">{len(df)} lançamento(s) · {dt_ini:%d/%m} a {dt_fim:%d/%m} · {n_sol} solicitante(s)</span></div>')
    topo = (f'<div class="inc-g" style="grid-template-columns:{grade};font-size:11px;color:#8892a4;padding:4px 0;border-bottom:1px solid #2a2a3a">'
            '<span>Filial</span><span>Origem</span><span>Regra</span><span>Documento</span><span>AP</span><span>Banco</span><span>Data</span><span>Fornecedor</span>'
            '<span style="text-align:right">Saldo</span><span>Detalhe do erro</span><span>Solicitante</span></div>')
    linhas = ""
    for r in df.to_dict("records"):
        etiquetas = "".join(
            f'<span class="inc-et" style="background:{cores[c][1]};color:{cores[c][2]}">{escape(_nome_curto(c))}</span>'
            for c in [x.strip() for x in _txt(r.get(coluna_cat)).split("|") if x.strip()])
        saldo = r.get("SALDO")
        saldo_txt = "••••••" if ocultar else ("" if pd.isna(saldo) else f"{float(saldo):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        cor_saldo = "#f3a3a2" if pd.notna(saldo) and float(saldo) < 0 else "#e0e0e0"
        data = pd.Timestamp(r["DATA"]).strftime("%d/%m/%Y") if pd.notna(r.get("DATA")) else ""
        dica = "\n".join(x for x in (
            f"AP {_txt(r.get('AP'))}" if _txt(r.get("AP")) else "",
            f"Filial: {_txt(r.get('NOME_FILIAL'))} ({_txt(r.get('SEGMENTO'))}) · Origem: {_ORIGEM.get(_txt(r.get('ORIGEM')), _txt(r.get('ORIGEM')))}",
            f"Classe: {_txt(r.get('CLASSE')).replace(chr(10), ' | ')}" if _txt(r.get("CLASSE")) else "",
            f"Centro de custo: {_txt(r.get('CENTRO_CUSTO')).replace(chr(10), ' | ')}" if _txt(r.get("CENTRO_CUSTO")) else "",
            f"Grupo financeiro: {_txt(r.get('GRUPO_FINANCEIRO'))}" if _txt(r.get("GRUPO_FINANCEIRO")) else "",
            f"Conta do agente: {_txt(r.get('CONTA_FINANCEIRA'))}" if _txt(r.get("CONTA_FINANCEIRA")) else "",
            f"Ação: {_acao(r)}",
            f"Projeto: {_txt(r.get('PROJETO')).replace(chr(10), ' | ')}" if _txt(r.get("PROJETO")) else "",
            f"Lançamento {_txt(r.get('NUM_LANCTO'))}",
            obter_obs_inconsistencia(_txt(r.get(coluna_cat))),
        ) if x)
        linhas += (f'<div class="inc-g inc-r" style="grid-template-columns:{grade}" title="{escape(dica, quote=True)}">'
                   f'<span class="inc-t" style="color:#aab0c0">{escape(_txt(r.get("NOME_FILIAL")))}</span>'
                   f'<span class="inc-t" style="color:#c9d1e3">{escape(_ORIGEM.get(_txt(r.get("ORIGEM")), _txt(r.get("ORIGEM"))))}</span><span>{etiquetas}</span>'
                   f'<span class="inc-t">{numeracao(r)}</span><span class="inc-t">{numero_ap(r)}</span>'
                   f'<span class="inc-t" style="color:#c9d1e3">{escape(agente(r, "BANCO"))}</span><span style="color:#8892a4">{data}</span><span class="inc-t" style="color:#aab0c0">{escape(agente(r, "FORNECEDOR"))}</span>'
                   f'<span style="text-align:right;font-variant-numeric:tabular-nums;color:{cor_saldo}">{saldo_txt}</span>'
                   f'<span class="inc-t" style="color:#aab0c0">{escape(detalhe_erro(r))}</span>'
                   f'<span class="inc-t" style="color:#8892a4">{escape(_txt(r.get("SOLICITANTE")))}</span>'
                   + '</div>')
    legenda = ('<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:#8892a4;margin-top:10px">'
               + "".join(f'<span><span style="color:{c[0]}">■</span> {escape(_nome_curto(k).lower())}</span>' for k, c in cores.items())
               + '<span>passe o mouse na linha: AP, classe, centro de custo e observação</span></div>')
    css = ("<style>.inc-g{display:grid;gap:12px;align-items:center}.inc-r{font-size:12.5px;padding:6px 0;border-bottom:1px solid #26263a}"
           ".inc-t{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
           ".inc-et{display:inline-block;border-radius:4px;padding:2px 7px;font-size:10px;font-weight:600;white-space:nowrap;margin-right:4px}</style>")
    return (css + '<div style="background:#1e1e2e;border-radius:12px;border-top:4px solid #E24B4A;box-sizing:border-box;padding:14px 18px;width:100%">'
            f'{cabeca}<div style="overflow-x:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e"><div style="min-width:{largura}px">{topo}'
            '<div style="max-height:420px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">'
            f'{linhas}</div></div></div>{legenda}</div>')


def render(carregar_erros):
    """`carregar_erros(data_inicio, data_fim)` busca no banco só o período escolhido (datas DD/MM/AAAA)."""
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Inconsistências de Lançamentos")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        # o cache é limpo no clique (callback), sem st.rerun() no meio da tela: parar antes dos filtros da barra lateral faria o Streamlit esquecê-los
        st.button("🔄 Atualizar", key="inc_atualizar", use_container_width=True, on_click=st.cache_data.clear)

    with st.sidebar:
        st.caption("Inconsistências de Lançamentos")

    # ── Filtro por período (barra lateral): abre no mês vigente (do dia 1 ao último dia) e vale para tudo na tela ──
    hoje = datetime.date.today()
    mes_vigente = (hoje.replace(day=1), hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]))
    with st.sidebar:
        periodo = st.date_input(
            "Data (período)", value=mes_vigente, format="DD/MM/YYYY", key="inc_periodo",
            help="Data do lançamento (prorrogada); abre no mês vigente. Só o período escolhido é buscado no banco; o dia final entra.",
        )
        lugar_emp = st.container()           # Empresa e Solicitante dependem do que veio do banco: nascem depois, mas aparecem acima do botão
        lugar_sol = st.container()
        gerar = st.button("Gerar Relatório", use_container_width=True, key="inc_gerar")
    if gerar:
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            st.session_state["_inc_periodo"] = (periodo[0], periodo[1])
        else:
            st.session_state.pop("_inc_periodo", None)
            st.warning("Selecione a data inicial e a final do período na barra lateral e clique em Gerar Relatório.")
            return
    periodo_sel = st.session_state.get("_inc_periodo")
    if not periodo_sel:
        st.info("O período abre no **mês vigente**. Ajuste-o na barra lateral, se precisar, e clique em **Gerar Relatório**.")
        return
    dt_ini, dt_fim = periodo_sel
    titulo_periodo = f" — {dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}"

    with st.spinner("Carregando as inconsistências do período..."):
        df_erros = carregar_erros(dt_ini.strftime("%d/%m/%Y"), dt_fim.strftime("%d/%m/%Y"))
    df_filtrado = _inteiros_sem_decimal(df_erros)
    if len(df_filtrado) == 0:
        st.success(f"Nenhuma inconsistência entre {dt_ini:%d/%m/%Y} e {dt_fim:%d/%m/%Y}.")
        return

    # ── Filtro por empresa (organização) e por solicitante (barra lateral, acima do botão): valem para a tabela, o Excel e a imagem ──────────────
    emp_sel, sol_sel = [], []
    if "ORGANIZACAO" in df_filtrado.columns:
        nomes = {}
        for org, g in df_filtrado.sort_values("COD_FILIAL").groupby("ORGANIZACAO"):
            nomes[org] = f"{org} - {_txt(g['NOME_FILIAL'].iloc[0]).split(' - ')[0].strip()}"
        st.session_state["inc_filtro_emp"] = [o for o in st.session_state.get("inc_filtro_emp", []) if o in nomes]      # depois de Atualizar, o que saiu da lista não derruba o filtro
        with lugar_emp:
            emp_sel = st.multiselect("Empresa", sorted(nomes, key=lambda o: nomes[o].split(' - ', 1)[1]), key="inc_filtro_emp", placeholder="Todas as empresas",
                                     format_func=lambda o: nomes[o], help="Organização do lançamento. Vazio traz todas.")
        if emp_sel:
            df_filtrado = df_filtrado[df_filtrado["ORGANIZACAO"].isin(emp_sel)]
            if df_filtrado.empty:
                st.info("Nenhuma inconsistência para as empresas selecionadas.")
                return
    if "SOLICITANTE" in df_filtrado.columns:
        solicitantes_lista = sorted(df_filtrado["SOLICITANTE"].dropna().unique().tolist())
        st.session_state["inc_filtro_sol"] = [v for v in st.session_state.get("inc_filtro_sol", []) if v in solicitantes_lista]
        with lugar_sol:
            sol_sel = st.multiselect("Solicitante", solicitantes_lista, key="inc_filtro_sol", placeholder="Todos os solicitantes")
        if sol_sel:
            df_filtrado = df_filtrado[df_filtrado["SOLICITANTE"].isin(sol_sel)]
            if df_filtrado.empty:
                st.info("Nenhuma inconsistência para os solicitantes selecionados.")
                return

    # ── Botões de regra (com a contagem): um lançamento com mais de uma regra conta em cada uma ──────────────
    coluna_cat = "CATEGORIA_ERRO"
    contagem = (df_filtrado[coluna_cat].str.split(r"\s*\|\s*").explode().str.strip().value_counts())
    regras = sorted(contagem.index, key=lambda r: (-contagem[r], r))
    cores = _cores(regras)
    opcoes = ["Todas"] + regras
    if st.session_state.get("inc_regra") not in opcoes:
        st.session_state.pop("inc_regra", None)                  # a regra escolhida não existe neste período/solicitante: volta para Todas
    regra_sel = st.segmented_control(
        "Regra", opcoes, default="Todas", key="inc_regra", label_visibility="collapsed",
        format_func=lambda o: f"Todas {len(df_filtrado)}" if o == "Todas" else f"{_nome_curto(o)} {int(contagem[o])}") or "Todas"
    df_tabela = df_filtrado if regra_sel == "Todas" else df_filtrado[df_filtrado[coluna_cat].str.contains(regra_sel, regex=False, na=False)]

    st.html(_html_card(df_tabela, cores, dt_ini, dt_fim, coluna_cat, ocultar=bool(st.session_state.get("cr_ocultar", False))))

    # ── Excel e PNG: sempre com todas as colunas e o que está filtrado ─────────────────────────────────────
    df_exib = df_tabela.copy()
    df_exib["Observação"] = df_exib[coluna_cat].apply(obter_obs_inconsistencia)
    arquivo_excel = exportar_excel(df_exib, "LANCAMENTOS_ERRO")
    titulo_png = "Inconsistências de Lançamentos" + titulo_periodo
    if regra_sel != "Todas":
        titulo_png += " — " + _nome_curto(regra_sel)
    if emp_sel:
        titulo_png += " — " + ", ".join(nomes[o].split(" - ", 1)[1] for o in emp_sel)
    if sol_sel:
        titulo_png += " — " + ", ".join(sol_sel)
    imagem_bytes = _gerar_imagem_cached(df_exib, titulo=titulo_png)

    botoes_acao_row(
        excel={"data": arquivo_excel, "file_name": "Inconsistencias_Lancamento.xlsx", "key": "inc_excel"},
        imagem={"data": imagem_bytes, "file_name": "Inconsistencias_Lancamento.png", "key": "inc_png"},
        copiar={"data": imagem_bytes, "key": "inc_copiar"},
    )
