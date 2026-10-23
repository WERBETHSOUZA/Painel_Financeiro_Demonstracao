"""
Painel Financeiro — demonstração com dados 100% fictícios.

Roda as mesmas telas do painel (Relatórios, Financeiro, Comercial e Acessos), com o mesmo menu e os mesmos botões, mas sem banco de dados e sem
nenhuma informação real. O login é de demonstração: usuário `admin`, senha `admin`.

    streamlit run app_demo.py --server.port 8590

Parâmetros opcionais na URL (usados para tirar prints):  ?entrar=1&tela=faturamento&sem_menu=1
"""

import sys
from datetime import datetime, timedelta
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import streamlit as st

from config.settings import aplicar_configuracoes

aplicar_configuracoes()

from dados_ficticios import gerar  # noqa: E402
from dados_ficticios_extra import gerar_extra  # noqa: E402
from services import permissoes  # noqa: E402
from views import (  # noqa: E402
    acessos, inconsistencias, faturamento_estado,
    contas_receber_painel, faturamento_cliente_grupo, grupo_credito, situacao_cliente,
    relatorio_boleto_nao_gerado, relatorio_contas_receber, relatorio_desconto_financeiro_pendente,
    relatorio_grupos_credito, relatorio_variacao_cambial_me,
    boletos_dda, relatorio_contas_apagar, relatorios,
)

USUARIO_DEMO, SENHA_DEMO, NOME_DEMO = "admin", "admin", "Administrador"

# ── Estilo global (igual ao painel original) ───────────────────────────────────
_css = RAIZ / "assets" / "styles.css"
if _css.exists():
    st.markdown(f"<style>{_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.markdown("""
<style>
    [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
        background-color: #0f1117 !important; color: #e0e0e0 !important; }
    header[data-testid="stHeader"] { visibility: hidden; height: 0; overflow: visible; }
    [data-testid="stExpandSidebarButton"] { visibility: visible !important; position: fixed !important;
        top: 12px !important; left: 12px !important; z-index: 9999 !important; }
    div.block-container { padding-top: 1rem; }
        /* separadores da lateral mais próximos do conteúdo */
        [data-testid="stSidebar"] hr, [data-testid="stSidebar"] [data-testid="stDivider"] { margin-top: 0.55rem !important; margin-bottom: 0.55rem !important; }
    /* não esmaece o conteúdo antigo enquanto a tela recarrega (Atualizar, troca de filtro) */
    [data-stale="true"], .stApp [data-stale="true"] { opacity: 1 !important; transition: none !important; }
    [data-testid="stAppViewContainer"] .stMain, [data-testid="stMainBlockContainer"] { opacity: 1 !important; }
    [data-testid="stSidebarHeader"] { min-height: 0 !important; padding: 0 !important; }
    [data-testid="stLogoSpacer"] { display: none !important; }
    [data-testid="stSidebarCollapseButton"] { visibility: visible !important; }
    [data-testid="stSidebarUserContent"] { padding-top: 0 !important; }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: #2a3350 !important; border: 1px solid #4A7FB5 !important; color: #ffffff !important; }
    .st-key-nav_hub_relatorios button { border: 1px solid rgba(250,250,250,0.2); justify-content: flex-start !important;
        padding-left: 2.4rem !important; }
    .st-key-nav_hub_relatorios button > div { width: 100%; justify-content: flex-start !important; }
    .st-key-nav_hub_relatorios button[data-testid="stBaseButton-secondary"] { background: transparent !important; }
</style>
""", unsafe_allow_html=True)
if st.query_params.get("sem_menu"):
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='stExpandSidebarButton']{display:none !important}</style>", unsafe_allow_html=True)


# ── Login de demonstração ──────────────────────────────────────────────────────
def _tela_login():
    st.markdown("""
    <style>
        div.login-header { background-color:#1c1c1c; border:1px solid #333; border-bottom:none;
            border-radius:14px 14px 0 0; padding:26px 24px 14px 24px; display:flex; flex-direction:column;
            align-items:center; box-shadow:0 4px 18px rgba(0,0,0,0.35); }
        div[data-testid="stForm"] { background-color:#1c1c1c; border:1px solid #333; border-top:none;
            border-radius:0 0 14px 14px; box-shadow:0 4px 18px rgba(0,0,0,0.35); padding:8px 24px 20px 24px; }
        div[data-testid="stForm"] button { width:100%; border-radius:8px; font-weight:600; }
        div.dica-demo { background:#1f2a40; border:1px solid #2f4a75; border-radius:8px; padding:8px 12px;
            font-size:12.5px; color:#a9c9ee; margin:10px 0 0 0; text-align:center; }
    </style>
    """, unsafe_allow_html=True)
    _, centro, _ = st.columns([1.3, 1, 1.3])
    with centro:
        st.markdown(
            "<div class='login-header'><div style='font-size:34px;line-height:1'>📊</div>"
            "<div style='font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;"
            "color:#94a3b8;margin-top:4px'>BI-FINANCEIRO</div>"
            "<div style='font-size:11px;color:#94a3b8;margin-top:6px;letter-spacing:1.2px'>DEMONSTRAÇÃO</div></div>",
            unsafe_allow_html=True)
        with st.form("login_demo"):
            usuario = st.text_input("Usuário", placeholder="admin")
            senha = st.text_input("Senha", type="password", placeholder="admin")
            enviar = st.form_submit_button("Entrar", type="primary")
        st.markdown(f"<div class='dica-demo'>Acesso de demonstração: usuário <b>{USUARIO_DEMO}</b> · senha "
                    f"<b>{SENHA_DEMO}</b><br>Todos os dados são fictícios.</div>", unsafe_allow_html=True)
        if enviar:
            if usuario.strip().lower() == USUARIO_DEMO and senha == SENHA_DEMO:
                st.session_state["autenticado"] = True
                st.session_state["_login_demo"] = datetime.now()
                st.rerun()
            else:
                st.error(f"Usuário ou senha inválidos. Use {USUARIO_DEMO} / {SENHA_DEMO}.")


if st.query_params.get("entrar") and not st.session_state.get("autenticado"):
    st.session_state["autenticado"] = True
    st.session_state["_login_demo"] = datetime.now()

if not st.session_state.get("autenticado"):
    _tela_login()
    st.stop()


# ── Permissões de demonstração (grupos e usuários fictícios) ───────────────────
if not permissoes.ARQUIVO.exists():
    permissoes.salvar({"grupos": {
        permissoes.GRUPO_ADMIN: {"membros": ["elisa.ramos"]},
        "Financeiro": {"paineis": ["Financeiro > Visão Geral MI-ME", "Financeiro > Mercado Interno",
                                    "Financeiro > Mercado Externo", "Financeiro > Inconsistências"],
                       "relatorios": ["📄 Contas a Receber - Exportação", "💱 Variação Cambial ME", "📄 Boleto Não Gerado"],
                       "membros": ["ana.souza", "bruno.lima"]},
        "Comercial": {"paineis": ["Comercial > Grupo de Crédito", "Comercial > Situação Cliente",
                                   "Comercial > Faturamento Cliente/Grupo"],
                      "relatorios": ["💳 Grupo de Crédito"], "membros": ["carla.mendes", "diego.prado"]},
    }}, USUARIO_DEMO)


# ── Dados fictícios ────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _dados():
    return gerar()


@st.cache_data(show_spinner=False)
def _dados_extra():
    return gerar_extra()


d = _dados()
x = _dados_extra()
# A tela Contas a Receber busca o faturado direto no serviço: aponta para os dados fictícios.
contas_receber_painel.carregar_total_faturado_cliente = lambda: d["faturado"].copy()


def _adiantamento():
    return d["adiantamento"]


def _painel_cr(secao):
    return lambda: contas_receber_painel.render(
        d["contas_receber"], df_grupo_agentes=d["grupo_agentes"], df_grupo_geral=d["grupo_geral"], secao=secao)


# Menu (igual ao do painel): grupo -> itens. Cada item abre a tela "Grupo > Item".
MENU = [
    ("🏦", "Financeiro", [("📊", "Visão Geral MI-ME"), ("🇧🇷", "Mercado Interno"), ("🌎", "Mercado Externo"),
                          ("❌", "Inconsistências")]),
    ("🛒", "Comercial", [("💳", "Grupo de Crédito"), ("🔍", "Situação Cliente"), ("📄", "Faturamento Cliente/Grupo"),
                           ("🗺️", "Faturamento por Estado")]),
]
TELAS = {
    "Financeiro > Visão Geral MI-ME": _painel_cr("geral"),
    "Financeiro > Mercado Interno": _painel_cr("mi"),
    "Financeiro > Mercado Externo": _painel_cr("me"),
    "Financeiro > Inconsistências": lambda: inconsistencias.render(x["erros"]),
    "Comercial > Grupo de Crédito": lambda: grupo_credito.render(
        d["grupo_geral"], d["grupo_agentes"], _adiantamento, df_contas_receber=d["contas_receber"]),
    "Comercial > Situação Cliente": lambda: situacao_cliente.render(
        d["contas_receber"], d["grupo_agentes"], d["grupo_geral"], d["faturado"], _adiantamento),
    "Comercial > Faturamento Cliente/Grupo": lambda: faturamento_cliente_grupo.render(
        d["contas_receber"], d["faturado"], d["grupo_geral"], d["grupo_agentes"], _adiantamento,
        df_fat_mensal=d["faturado_mensal"]),
    "Comercial > Faturamento por Estado": lambda: faturamento_estado.render(
        d["contas_receber"], d["faturado_mensal"], d["grupo_agentes"], d["faturado"]),
}

# ── Relatórios (página inicial de cartões) ─────────────────────────────────────
AREAS_RELATORIOS = {"Contas a Pagar": "#4A7FB5", "Contas a Receber": "#1BADA6",
                    "Grupo de Crédito": "#7B68B5"}
RELATORIOS = {   # título -> (descrição, área, função que desenha a tela)
    "👤 Aprovadores": ("APs pendentes de aprovação", "Contas a Pagar",
        lambda: relatorios.render(x["aprovacoes"])),
    "💰 Contas a Pagar": ("Títulos por período e status", "Contas a Pagar",
        lambda: relatorio_contas_apagar.render(x["contas_pagar"])),
    "📊 Boletos DDA": ("Boletos recebidos via DDA", "Contas a Pagar",
        lambda: boletos_dda.render(x["boletos_dda"])),
    "📄 Contas a Receber - Exportação": ("Exportação completa dos títulos em aberto", "Contas a Receber",
        lambda: relatorio_contas_receber.render(d["contas_receber"], d["grupo_agentes"], d["grupo_geral"])),
    "💱 Variação Cambial ME": ("Variação cambial de títulos ME com PTAX BCB escolhida", "Contas a Receber",
        lambda: relatorio_variacao_cambial_me.render(d["contas_receber"])),
    "📄 Desconto Financeiros Pendentes": ("Mercado Interno, regra Financeiro, ainda não aplicado", "Contas a Receber",
        lambda: relatorio_desconto_financeiro_pendente.render(d["contas_receber"])),
    "📄 Boleto Não Gerado": ("Todos os títulos sem boleto, com status Liberado/Bloqueado", "Contas a Receber",
        lambda: relatorio_boleto_nao_gerado.render(d["contas_receber"])),
    "💳 Grupo de Crédito": ("Limite, disponível, % utilizado, documentação e status de faturamento por grupo",
        "Grupo de Crédito", lambda: relatorio_grupos_credito.render(d["grupo_geral"], d["grupo_agentes"], d["contas_receber"])),
}


def _hub_relatorios():
    st.title("Relatórios")
    busca = st.text_input("Buscar relatório", placeholder="Buscar relatório...", key="busca_relatorios",
                          label_visibility="collapsed").strip().lower()
    por_area = {}
    for titulo, (descricao, area, _) in RELATORIOS.items():
        if busca and busca not in f"{titulo} {descricao} {area}".lower():
            continue
        por_area.setdefault(area, []).append((titulo, descricao))
    if not por_area:
        st.info("Nenhum relatório encontrado.")
        return
    areas = sorted(por_area, key=lambda a: (-len(por_area[a]), list(AREAS_RELATORIOS).index(a)))
    css = ""
    for n, area in enumerate(areas):
        cor = AREAS_RELATORIOS.get(area, "#6366f1")
        css += (f".st-key-area_{n} button:hover {{ border-color:{cor}; }}"
                f".st-key-area_{n} button p {{ line-height:1.5; margin:0; font-size:.9rem; color:rgba(180,180,180,0.75); }}"
                f".st-key-area_{n} button p strong {{ font-size:1.05rem; color:rgba(250,250,250,1); }}")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    POR_LINHA = 4
    for inicio in range(0, len(areas), POR_LINHA):
        for coluna, (n, area) in zip(st.columns(POR_LINHA), enumerate(areas[inicio:inicio + POR_LINHA], start=inicio)):
            with coluna:
                st.markdown(f"<h3 style='text-align:center;font-size:1.6rem;font-weight:600;margin:10px 0 12px;'>"
                            f"{area}</h3>", unsafe_allow_html=True)
                with st.container(key=f"area_{n}"):
                    for titulo, descricao in por_area[area]:
                        with st.container(border=True):
                            if st.button(f"**{titulo}**  \n{descricao}", key=f"abrir_{titulo}", width="stretch"):
                                st.session_state["_painel_demo"] = f"Relatórios > {titulo}"
                                st.rerun()


# ── Navegação ──────────────────────────────────────────────────────────────────
_ATALHOS = {"contas": "Financeiro > Visão Geral MI-ME", "mi": "Financeiro > Mercado Interno",
            "me": "Financeiro > Mercado Externo", "inconsistencias": "Financeiro > Inconsistências",
            "grupo": "Comercial > Grupo de Crédito", "situacao": "Comercial > Situação Cliente",
            "faturamento": "Comercial > Faturamento Cliente/Grupo", "estado": "Comercial > Faturamento por Estado", "relatorios": "Relatórios", "acessos": "Acessos"}
if "_painel_demo" not in st.session_state:
    st.session_state["_painel_demo"] = _ATALHOS.get(st.query_params.get("tela", ""), "")   # "" = abre vazio
ativo = st.session_state["_painel_demo"]


def _ir(painel):
    st.session_state["_painel_demo"] = painel
    st.rerun()


with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:10px 0 4px;margin-top:-34px;'><div style='font-size:34px;line-height:1'>📊</div>"
        "<div style='font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#94a3b8;"
        "margin-top:4px'>BI-FINANCEIRO</div></div>", unsafe_allow_html=True)
    # usuário, tempo de acesso e botão Sair (antes ficavam no canto superior direito)
    _expira = st.session_state["_login_demo"] + timedelta(hours=8)
    st.markdown("""<style>
        .st-key-sair_lateral button { border:1px solid #5a2b2b; background:#2a1b1f; color:#f5a3a3; }
        .st-key-sair_lateral button:hover { border-color:#E24B4A; background:#3a2127; color:#ffd0d0; }
    </style>""", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:center;padding:6px 0 0;font-size:17px;font-weight:600;color:#ffffff'>"
                f"{NOME_DEMO}</div>", unsafe_allow_html=True)
    st.iframe(f"""
    <style>html, body {{ margin:0; padding:0; overflow:hidden; background:transparent; }}</style>
    <div id="acesso_expira_txt" style="text-align:center;font-size:12px;color:#e8a05a;
         font-family:'Source Sans Pro', sans-serif;">Acesso expira em: --</div>
    <script>
        var expiracao = new Date("{_expira.strftime('%Y-%m-%dT%H:%M:%S')}");
        var el = document.getElementById("acesso_expira_txt");
        function atualizar() {{
            var diffSeg = Math.floor((expiracao - new Date()) / 1000);
            if (diffSeg <= 0) {{ el.innerText = "Acesso expirado"; return; }}
            el.innerText = "Acesso expira em: " + Math.floor(diffSeg / 3600) + "h " +
                Math.floor((diffSeg % 3600) / 60) + "m " + (diffSeg % 60) + "s";
        }}
        atualizar(); setInterval(atualizar, 1000);
    </script>""", height=24)
    col_admin, col_sair = st.columns(2)
    with col_admin:
        if st.button("🔐 Admin", key="admin_lateral", width="stretch",
                     type="primary" if ativo == "Acessos" else "secondary"):
            _ir("Acessos")
    with col_sair:
        if st.button("Sair", icon=":material/logout:", key="sair_lateral", width="stretch"):
            st.session_state.clear()
            st.rerun()
    st.divider()
    st.markdown("### 📂 Menu")
    if st.button("✅ Relatórios", width="stretch", key="nav_hub_relatorios",
                 type="primary" if ativo == "Relatórios" or ativo.startswith("Relatórios > ") else "secondary"):
        if ativo != "Relatórios":
            _ir("Relatórios")
    for icone_g, nome_g, itens in MENU:
        with st.expander(f"{icone_g} {nome_g}", expanded=ativo.startswith(f"{nome_g} > ")):
            for icone, nome in itens:
                completo = f"{nome_g} > {nome}"
                if st.button(f"{icone} {nome}", width="stretch", key=f"nav_{completo}",
                             type="primary" if ativo == completo else "secondary"):
                    if ativo != completo:
                        _ir(completo)
    st.markdown("---")

# ── Roteamento ─────────────────────────────────────────────────────────────────
if ativo == "":
    st.markdown("<div style='height:12vh'></div>", unsafe_allow_html=True)
    st.title(f"👋 Olá, {NOME_DEMO}!")
    st.write("Selecione um painel no menu ao lado para começar.")
elif ativo == "Relatórios":
    _hub_relatorios()
elif ativo.startswith("Relatórios > "):
    if st.button("← Voltar aos relatórios", key="voltar_relatorios"):
        _ir("Relatórios")
    RELATORIOS[ativo.removeprefix("Relatórios > ")][2]()
elif ativo == "Acessos":
    acessos.render(
        [("✅", "Relatórios", {t: None for t in RELATORIOS})] + [(i, n, it) for i, n, it in MENU],
        {t: (dsc, area) for t, (dsc, area, _) in RELATORIOS.items()}, list(AREAS_RELATORIOS),
        USUARIO_DEMO, (USUARIO_DEMO,))
else:
    TELAS[ativo]()
