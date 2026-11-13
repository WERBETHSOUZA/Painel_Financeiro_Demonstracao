import streamlit as st
import streamlit.components.v1 as components
import base64
from datetime import datetime, timedelta
from pathlib import Path
from config import frases
from config.settings import aplicar_configuracoes
from services.auth_service import authenticate_user, sanitize_username
from services import permissoes
from services.data_service import (
    carregar_aps_erro,
    carregar_relatorio_approvo, carregar_contas_receber, carregar_total_faturado_cliente,
    carregar_faturado_mensal_cliente, carregar_faturado_mensal_mi,
    carregar_contas_apagar, carregar_boletos_dda, DATA_CORTE_CONTAS_APAGAR, atualizar_se_antigo,
    carregar_grupo_credito_geral, carregar_grupo_credito_saldo_agente,
    carregar_adiantamento_geral, carregar_adiantamento_total_agente,
    carregar_adiantamento_saldo_agente, carregar_variacao_cambial_me,
)
from components import rodape_lateral
from views import inconsistencias, relatorios, contas_receber, relatorio_contas_apagar, grupo_credito, situacao_cliente, boletos_dda, adiantamentos, contas_receber_painel, relatorio_contas_receber, relatorio_contas_receber_mi, relatorio_fretes_mot_matriz_filial, faturamento_cliente_grupo, relatorio_desconto_financeiro_pendente, relatorio_descontos_operacionais_mi, relatorio_recebimentos, relatorio_boleto_nao_gerado, relatorio_grupos_credito, relatorio_variacao_cambial_me, acessos, faturamento_estado, visao_geral_comercial, resumo_pendencias


def _pagina_aprovadores():
    with st.spinner("Carregando dados..."):
        df = carregar_relatorio_approvo()
    relatorios.render(df, lambda: atualizar_se_antigo(carregar_relatorio_approvo, "aprovadores"))


def _pagina_contas_pagar():
    with st.spinner("Carregando dados..."):
        df = carregar_contas_apagar()
    relatorio_contas_apagar.render(
        df, carregar_contas_apagar, DATA_CORTE_CONTAS_APAGAR,
        lambda: atualizar_se_antigo(carregar_contas_apagar, "contas_apagar"),
    )


def _pagina_boletos_dda():
    with st.spinner("Carregando dados..."):
        df = carregar_boletos_dda()
    boletos_dda.render(df)


def _pagina_adiantamentos():
    with st.spinner("Carregando adiantamento..."):
        df_geral = carregar_adiantamento_geral()
        df_total = carregar_adiantamento_total_agente()
    adiantamentos.render(df_geral, df_total)


def _pagina_contas_receber_relatorio():
    with st.spinner("Carregando dados..."):
        df = carregar_contas_receber()
        df_grupo_agentes = carregar_grupo_credito_saldo_agente()
        df_grupo_geral = carregar_grupo_credito_geral()
    relatorio_contas_receber.render(df, df_grupo_agentes, df_grupo_geral)


def _pagina_contas_receber_mi():
    with st.spinner("Carregando dados..."):
        df_grupo_agentes = carregar_grupo_credito_saldo_agente()
        df_grupo_geral = carregar_grupo_credito_geral()
    relatorio_contas_receber_mi.render(df_grupo_agentes, df_grupo_geral)


def _pagina_faturamento_cliente_grupo():
    with st.spinner("Carregando dados..."):
        df_cr = carregar_contas_receber()
        df_fat = carregar_total_faturado_cliente()
        df_fat_mensal = carregar_faturado_mensal_cliente()
        df_grupo_geral = carregar_grupo_credito_geral()
        df_grupo_agentes = carregar_grupo_credito_saldo_agente()
    # Adiantamento não carrega aqui: a consulta é lenta/instável (função Oracle por
    # linha, ORA-20003) e só é feita quando o usuário clica em "Carregar adiantamento".
    faturamento_cliente_grupo.render(df_cr, df_fat, df_grupo_geral, df_grupo_agentes, carregar_adiantamento_saldo_agente,
                                    df_fat_mensal=df_fat_mensal)


def _pagina_desconto_financeiro_pendente():
    with st.spinner("Carregando dados..."):
        df_cr = carregar_contas_receber()
    relatorio_desconto_financeiro_pendente.render(df_cr)


def _pagina_boleto_nao_gerado():
    with st.spinner("Carregando dados..."):
        df_cr = carregar_contas_receber()
    relatorio_boleto_nao_gerado.render(df_cr)


def _pagina_relatorio_grupos_credito():
    with st.spinner("Carregando dados..."):
        df_gc_geral   = carregar_grupo_credito_geral()
        df_gc_agentes = carregar_grupo_credito_saldo_agente()
        df_cr         = carregar_contas_receber()
    relatorio_grupos_credito.render(df_gc_geral, df_gc_agentes, df_cr)


def _pagina_variacao_cambial_me():
    with st.spinner("Carregando dados..."):
        df = carregar_contas_receber()
    relatorio_variacao_cambial_me.render(df)


# Agrupamento de páginas por domínio
PAGINAS_RELATORIOS = {
    "👤 Aprovadores": _pagina_aprovadores,
    "💰 Contas a Pagar": _pagina_contas_pagar,
    "📊 Boletos DDA": _pagina_boletos_dda,
    "💰 Adiantamentos": _pagina_adiantamentos,
    "📄 Contas a Receber - Exportação": _pagina_contas_receber_relatorio,
    "📄 Contas a Receber - MI": _pagina_contas_receber_mi,
    "📄 Fretes Mot - Matriz x Filial": lambda: relatorio_fretes_mot_matriz_filial.render(),
    "📄 Descontos Contratuais Pendentes MI": _pagina_desconto_financeiro_pendente,
    "📄 Descontos Realizados": lambda: relatorio_descontos_operacionais_mi.render(),
    "📄 Boleto Não Gerado": _pagina_boleto_nao_gerado,
    "💳 Grupo de Crédito": _pagina_relatorio_grupos_credito,
    "💱 Variação Cambial ME": _pagina_variacao_cambial_me,
}

# Áreas da página inicial de Relatórios (ordem de exibição -> cor do cartão)
# e cartões: título -> (descrição, área). Para um relatório novo, basta
# incluir a descrição e a área dele em CARTOES_RELATORIOS.
AREAS_RELATORIOS = {
    "Contas a Receber": "#1BADA6",
    "Contas a Pagar": "#4A7FB5",
    "Movimento Financeiro": "#E8724A",
    "Grupo de Crédito": "#7B68B5",
}
CARTOES_RELATORIOS = {
    "👤 Aprovadores":    ("APs pendentes de aprovação", "Contas a Pagar"),
    "💰 Contas a Pagar": ("Títulos por período e status", "Contas a Pagar"),
    "📊 Boletos DDA":    ("Boletos recebidos via DDA", "Contas a Pagar"),
    "💰 Adiantamentos":  ("Efetuados e recebidos em aberto", "Movimento Financeiro"),
    "📄 Contas a Receber - Exportação": ("Exportação completa dos títulos em aberto", "Contas a Receber"),
    "📄 Contas a Receber - MI": ("Mercado Interno: pagos, vencidos e a vencer, com data de pagamento, desconto e baixa de adiantamento", "Contas a Receber"),
    "📄 Fretes Mot - Matriz x Filial": ("Contas a pagar de fretes (classe Mot) da Demo à Filial e da Filial à Siderúrgica, por período de prorrogação", "Contas a Pagar"),
    "💱 Variação Cambial ME": ("Variação cambial de títulos ME com PTAX BCB escolhida", "Contas a Receber"),
    "📄 Descontos Contratuais Pendentes MI": ("Regra Financeiro: pendentes e aplicados no Mega, com a classe de desconto a lançar", "Contas a Receber"),
    "📄 Descontos Realizados": ("Descontos já realizados (ação 948), MI e ME: contratuais, operacionais e concedidos", "Movimento Financeiro"),
    "📄 Boleto Não Gerado": ("Todos os títulos sem boleto, com status Liberado/Bloqueado", "Contas a Receber"),
    "💳 Grupo de Crédito": ("Limite, disponível, % utilizado, documentação e status de faturamento por grupo", "Grupo de Crédito"),
}

# Etiqueta "Novo" na página de Relatórios: título -> data em que o relatório foi criado. Ela some sozinha depois de
# DIAS_ETIQUETA_NOVO dias; para um relatório novo, basta incluir o título e a data aqui.
DIAS_ETIQUETA_NOVO = 10
NOVOS_RELATORIOS = {
    "📄 Descontos Realizados": datetime(2026, 10, 26),
    "📄 Contas a Receber - MI": datetime(2026, 10, 30),
    "📄 Fretes Mot - Matriz x Filial": datetime(2026, 11, 3),
}

# ── Configurações globais ──────────────────────────────────────────────────────
aplicar_configuracoes()

# ── CSS global ────────────────────────────────────────────────────────────────
_css_path = Path(__file__).parent / "assets" / "styles.css"
if _css_path.exists():
    st.markdown(f"<style>{_css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ── Esconde a barra superior nativa do Streamlit (menu ☰, Deploy, ⋮) ─────────
st.markdown("""
<style>
        [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .main {
        background-color: #0f1117 !important;
        color: #e0e0e0 !important;
    }
    header[data-testid="stHeader"] {
        visibility: hidden;
        height: 0;
        overflow: visible;
    }
    /* Botão de expandir sidebar (aparece quando sidebar está oculta) */
    [data-testid="stExpandSidebarButton"] {
        visibility: visible !important;
        position: fixed !important;
        top: 12px !important;
        left: 12px !important;
        z-index: 9999 !important;
    }
    div.block-container {
        padding-top: 1rem;
    }
    /* Remove espaço do header nativo do Streamlit na sidebar */
    [data-testid="stSidebarHeader"] {
        min-height: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stLogoSpacer"] {
        display: none !important;
    }
    /* Botão de colapso: sempre visível */
    [data-testid="stSidebarCollapseButton"] {
        visibility: visible !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Logo em base64 ────────────────────────────────────────────────────────────
logo_path = Path(__file__).parent / "assets" / "demo_logo.png"
logo_b64  = base64.b64encode(logo_path.read_bytes()).decode()

# ── Tela de login personalizada ───────────────────────────────────────────────
if not st.session_state.get("authentication_status"):

    st.markdown("""
    <style>
        /* topo do card: logo + título */
        div.login-header {
            background-color: #1c1c1c;
            border: 1px solid #333;
            border-bottom: none;
            border-radius: 14px 14px 0 0;
            padding: 26px 24px 14px 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            box-shadow: 0 4px 18px rgba(0,0,0,0.35);
        }

        /* corpo do card: formulário, colado embaixo do header */
        div[data-testid="stAlert"] {
            max-width: none !important;
            width: 100% !important;
            margin: 0 !important;
            background-color: #1c1c1c !important;
            border: 1px solid #333 !important;
            border-top: none !important;
            border-radius: 0 0 14px 14px !important;
            box-shadow: 0 4px 18px rgba(0,0,0,0.35) !important;
        }
        div[data-testid="stAlert"] p {
            color: #e8d27a !important;
        }

        div[data-testid="stForm"] div[data-testid="stTextInput"] {
            margin-bottom: 14px;
        }

        div[data-testid="stForm"] div[data-baseweb="base-input"] {
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
            border-radius: 8px !important;
            border: 1px solid #3a3a3a !important;
            background: #141414 !important;
            overflow: hidden !important;
        }

        div[data-testid="stForm"] input {
            flex: 1 !important;
            width: auto !important;
            min-width: 0 !important;
            padding: 10px 12px !important;
            border: none !important;
            background: transparent !important;
            order: 1 !important;
        }

        div[data-testid="stForm"] div[data-baseweb="base-input"] button {
            flex-shrink: 0 !important;
            background: transparent !important;
            border: none !important;
            margin-right: 6px !important;
            order: 2 !important;
        }

        div[data-testid="stForm"] label {
            font-size: 13px !important;
            color: #cfcfcf !important;
            margin-bottom: 4px !important;
        }

        div.st-key-FormSubmitter-ad_login_form-Entrar {
            width: 100% !important;
        }
        div.st-key-FormSubmitter-ad_login_form-Entrar button {
            width: 100% !important;
            border-radius: 8px !important;
            padding: 10px 0 !important;
            margin-top: 6px !important;
            font-weight: 600 !important;
        }

        /* remove o título "Login" duplicado do componente, sem deixar espaço vazio */
        div[data-testid="stForm"] h1 {
            display: none !important;
            margin: 0 !important;
            padding: 0 !important;
            height: 0 !important;
        }
        div[data-testid="stForm"] > div:first-child {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }

        /* deixa o aviso/erro do login com a mesma largura do card */
        div[data-testid="stAlert"] {
            max-width: 320px;
            margin: 14px auto 0 auto;
        }
    </style>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1.3, 1, 1.3])
    with col_c:
        st.markdown(f"""
        <div class="login-header">
            <img src="data:image/png;base64,{logo_b64}" style="width:90px; margin-bottom:4px;" />
            <div style="font-size:11px; font-weight:700; letter-spacing:1.2px;
                        text-transform:uppercase; color:#94a3b8;">BI-FINANCEIRO</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("ad_login_form"):
            login_username = st.text_input(
                "Usuário",
                placeholder="nome.sobrenome",
                help="Demonstração: use admin / admin.",
            )
            login_password = st.text_input("Senha", type="password")
            login_submitted = st.form_submit_button("Entrar", type="primary")

        if login_submitted:
            username_clean = sanitize_username(login_username)
            attempts = st.session_state.setdefault("_ad_login_attempts", {})
            attempt_key = username_clean or "_invalid"
            attempt = attempts.get(attempt_key, {"count": 0, "blocked_until": None})
            now = datetime.now()

            if attempt["blocked_until"] and now < attempt["blocked_until"]:
                seconds = int((attempt["blocked_until"] - now).total_seconds()) + 1
                st.error(f"Muitas tentativas. Tente novamente em {seconds} segundos.")
            else:
                result = authenticate_user(login_username, login_password)
                if result.get("success"):
                    attempts.pop(attempt_key, None)
                    st.session_state["authentication_status"] = True
                    st.session_state["username"] = result["username"]
                    st.session_state["name"] = result["name"]
                    st.session_state["ad_groups"] = result.get("groups", [])
                    st.session_state["email"] = result.get("email")
                    st.session_state["department"] = result.get("department")
                    st.session_state["_login_time"] = now
                    st.rerun()
                else:
                    count = attempt["count"] + 1
                    attempts[attempt_key] = {
                        "count": 0 if count >= 5 else count,
                        "blocked_until": now + timedelta(minutes=5) if count >= 5 else None,
                    }
                    st.error(result.get("error", "Falha na autenticação."))
        else:
            st.info("Acesso de demonstração: usuário **admin** · senha **admin**. Todos os dados são fictícios.")

    st.stop()

# ── Usuário autenticado ───────────────────────────────────────────────────────
usuario = st.session_state.get("username", "")
nome = st.session_state.get("name", "")
grupos_ad = st.session_state.get("ad_groups", [])

# Ajustes locais de acesso
USUARIOS_ADMIN = {
    "admin",
    # Adicione outros usuários aqui
}

GRUPOS_ADMIN = {
    "BI_FINANCEIRO_ADMIN",
    # Adicione os grupos do AD aqui
}

grupos_ad_normalizados = {
    str(grupo).strip().upper()
    for grupo in grupos_ad
}

perfil = (
    "admin"
    if usuario.lower() in {u.lower() for u in USUARIOS_ADMIN}
    or grupos_ad_normalizados.intersection(
        {grupo.upper() for grupo in GRUPOS_ADMIN}
    )
    else "analista"
)

# ── Controle de expiração da sessão (8 horas) ─────────────────────────────────
HORAS_EXPIRACAO_SESSAO = 8

if "_login_time" not in st.session_state:
    st.session_state["_login_time"] = datetime.now()

horario_expiracao = st.session_state["_login_time"] + timedelta(hours=HORAS_EXPIRACAO_SESSAO)
if datetime.now() >= horario_expiracao:
    st.session_state.clear()
    st.warning("Sua sessão expirou. Entre novamente.")
    st.rerun()

# ── Painéis disponíveis por perfil ───────────────────────────────────────────
# Nome mostrado no menu quando é diferente do nome interno do painel (o interno é a chave das permissões em
# config/permissoes.json e do roteamento; renomear a chave exigiria migrar as permissões de todos os usuários).
ROTULOS_MENU = {
    "Financeiro > Mercado Interno": "Contas a Receber - MI",
    "Financeiro > Mercado Externo": "Contas a Receber - ME",
    "Financeiro > Visão Geral MI-ME": "Contas a Receber - Visão Geral",
    "Financeiro > Inconsistências": "Inconsistências de Lançamento",
    "Tesouraria > Recebimento por Banco": "Recebimentos por Banco",
    "Comercial > Visão Geral Comercial": "Visão Geral Comercial - MI",
    "Comercial > Grupo de Crédito": "Limite Grupo de Crédito",
    "Comercial > Situação Cliente": "Situação do Cliente",
    "Comercial > Faturamento Cliente/Grupo": "Faturamento por Cliente ou Grupo",
    "Comercial > Faturamento por UF": "Faturamento por Estado - MI",
}
PAINEIS_ADMIN = [
    ("📑", "Relatórios", PAGINAS_RELATORIOS),
    ("💲", "Financeiro", [
        ("📊", "Visão Geral MI-ME"),
        ("🇧🇷", "Mercado Interno"),
        ("🌎", "Mercado Externo"),
        ("❌", "Inconsistências"),
    ]),
    ("🏛️", "Tesouraria", [
        ("💵", "Recebimento por Banco"),
    ]),
    ("🛒", "Comercial", [
        ("🧭", "Visão Geral Comercial"),
        ("💳", "Grupo de Crédito"),
        ("🔍", "Situação Cliente"),
        ("📄", "Faturamento Cliente/Grupo"),
        ("🗺️", "Faturamento por UF"),
    ]),
]
PAINEIS_ANALISTA = [
    ("📑", "Relatórios", PAGINAS_RELATORIOS),
    ("💲", "Financeiro", [
        ("📊", "Visão Geral MI-ME"),
        ("🇧🇷", "Mercado Interno"),
        ("🌎", "Mercado Externo"),
        ("❌", "Inconsistências"),
    ]),
    ("🏛️", "Tesouraria", [
        ("💵", "Recebimento por Banco"),
    ]),
    ("🛒", "Comercial", [
        ("🧭", "Visão Geral Comercial"),
        ("💳", "Grupo de Crédito"),
        ("🔍", "Situação Cliente"),
        ("📄", "Faturamento Cliente/Grupo"),
        ("🗺️", "Faturamento por UF"),
    ]),
]
# Menu conforme config/permissoes.json (admin e usuário não cadastrado com padrão "completo" veem tudo).
_dados_perm = permissoes.carregar()
eh_admin = perfil == "admin" or permissoes.eh_admin_por_grupo(usuario, _dados_perm)
_perm = permissoes.permissoes_do_usuario(usuario, eh_admin, _dados_perm)
paineis = permissoes.filtrar_menu(PAINEIS_ADMIN, _perm)
paginas_relatorios_visiveis = (
    PAGINAS_RELATORIOS if _perm is None
    else {k: v for k, v in PAGINAS_RELATORIOS.items() if k in _perm["relatorios"]}
)
# Painéis e relatórios desativados pelo administrador padrão (tela Acessos > Painéis): somem para todos, inclusive admins.
_desativados = permissoes.desativados(_dados_perm)
paineis = permissoes.remover_desativados(paineis, _desativados)
# Saldos Bancários está em teste: só o administrador vê no menu
if not eh_admin:
    _menu_sem_teste = []
    for _item in paineis:
        if len(_item) == 3 and isinstance(_item[2], list):
            _subs = [_x for _x in _item[2] if _x[1] != "Saldos Bancários"]
            if _subs:
                _menu_sem_teste.append((_item[0], _item[1], _subs))
        else:
            _menu_sem_teste.append(_item)
    paineis = _menu_sem_teste
# Resumo Pendências: só quem foi incluído no grupo fixo de mesmo nome (tela Acessos) vê o item, até o administrador
if permissoes.tem_resumo_pendencias(usuario, _dados_perm):
    paineis = [("⚠️", "Resumo Pendências")] + list(paineis)
paginas_relatorios_visiveis = {k: v for k, v in paginas_relatorios_visiveis.items() if k not in _desativados}
st.session_state["_relatorios_visiveis"] = list(paginas_relatorios_visiveis)
PAINEIS_FIXOS = ["Acessos"] if eh_admin else []  # abre pelo botão "Admin" ao lado de Sair, fora da lista do menu

def _paineis_folha(lista):
    folhas = []
    for item in lista:
        if len(item) == 3:
            _, nome_pai, paginas = item
            if isinstance(paginas, dict):
                folhas.extend(f"{nome_pai} > {pagina}" for pagina in paginas)
            else:
                for _, sub in paginas:
                    folhas.append(f"{nome_pai} > {sub}")
        else:
            _, nome = item
            folhas.append(nome)
    return folhas

def _pagina_inicial_relatorios():
    st.title("Relatórios")
    busca = st.text_input("Buscar relatório", placeholder="Buscar relatório...",
                          key="busca_relatorios", label_visibility="collapsed").strip().lower()

    por_area = {}
    for titulo in paginas_relatorios_visiveis:
        descricao, area = CARTOES_RELATORIOS.get(titulo, ("", "Outros"))
        if busca and busca not in f"{titulo} {descricao} {area}".lower():
            continue
        por_area.setdefault(area, []).append((titulo, descricao))

    if not por_area:
        st.info("Nenhum relatório encontrado.")
        return

    # Áreas sempre na ordem de AREAS_RELATORIOS (fixa, não por quantidade de relatórios); áreas fora da lista vão por último.
    ordem_base = [a for a in AREAS_RELATORIOS if a in por_area]
    ordem_base += [a for a in por_area if a not in ordem_base]
    areas = ordem_base

    # Cartões compactos: título e, embaixo, a descrição em uma linha só (cortada com reticências).
    css = ""
    for n, area in enumerate(areas):
        cor = AREAS_RELATORIOS.get(area, "#6366f1")
        css += (
            f".st-key-area_{n} {{ gap:11px; }}"
            f".st-key-area_{n} button {{ justify-content:flex-start; min-height:56px; padding:.3rem .75rem; }}"
            f".st-key-area_{n} button div, .st-key-area_{n} button span "
            f"{{ justify-content:flex-start; text-align:left; width:100%; min-width:0; }}"
            f".st-key-area_{n} button {{ border-left:4px solid {cor}; }}"
            f".st-key-area_{n} button:hover {{ border-color:{cor}; }}"
            f".st-key-area_{n} button p {{ display:block; width:100%; margin:0; font-size:.78rem; line-height:1.4; "
            f"color:rgba(136,146,164,1); text-align:left; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}"
            f".st-key-area_{n} button p strong {{ font-size:.92rem; color:rgba(250,250,250,1); }}"
        )
    css += ".st-key-rel_areas [data-testid=\"stHorizontalBlock\"] { gap:8px; }"
    css += (
        ".st-key-rel_areas [class*='st-key-novo_'] button p strong::after { content:'Novo'; margin-left:8px; "
        "padding:1px 6px; border-radius:4px; background:rgba(46,204,113,0.18); color:#6fd69a; font-size:.65rem; "
        "font-weight:600; vertical-align:middle; }"
    )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    POR_LINHA = 4
    with st.container(key="rel_areas"):
        for inicio in range(0, len(areas), POR_LINHA):
            grupo = areas[inicio:inicio + POR_LINHA]
            for coluna, (n, area) in zip(st.columns(POR_LINHA), enumerate(grupo, start=inicio)):
                with coluna:
                    cor = AREAS_RELATORIOS.get(area, "#6366f1")
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;font-size:1rem;font-weight:600;margin:14px 0 17px;'>"
                        f"<span style='width:9px;height:9px;border-radius:2px;background:{cor};flex:none'></span>{area}</div>",
                        unsafe_allow_html=True,
                    )
                    with st.container(key=f"area_{n}"):
                        for i, (titulo, descricao) in enumerate(por_area[area]):
                            rotulo = f"**{titulo}**  \n{descricao}" if descricao else f"**{titulo}**"
                            criado = NOVOS_RELATORIOS.get(titulo)
                            novo = criado is not None and (datetime.now() - criado).days < DIAS_ETIQUETA_NOVO
                            # o contêiner com a chave "novo_*" é o que liga a etiqueta (CSS acima); os demais ficam como estão
                            with st.container(key=f"novo_{n}_{i}") if novo else st.container():
                                if st.button(rotulo, key=f"abrir_{titulo}", width="stretch"):
                                    _resetar_filtros(f"Relatórios > {titulo}")


# ── Estado inicial ────────────────────────────────────────────────────────────
if "_painel_ativo" not in st.session_state:
    # quem está no grupo Resumo Pendências abre direto nele (só ao entrar; depois navega normalmente)
    st.session_state["_painel_ativo"] = "Resumo Pendências" if permissoes.tem_resumo_pendencias(usuario, _dados_perm) else None

# ── Identificação na barra recolhida: globo da logo + iniciais de quem entrou ─────────────────────────────
@st.cache_resource
def _globo_logo_uri() -> str:
    """Recorte do globo da logo (sem o nome) em 88 px, como data URI, para o topo da barra recolhida."""
    import base64
    import io
    from PIL import Image
    try:
        im = Image.open(logo_path).convert("RGBA").crop((120, -8, 330, 202)).resize((88, 88), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _iniciais(login: str) -> str:
    """'admin' -> 'WL'; sem separador, as duas primeiras letras."""
    import re
    partes = [p for p in re.split(r"[.\s_-]+", (login or "").strip()) if p]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    return (partes[0][:2] if partes else "?").upper()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Só aparece com a barra recolhida (o CSS esconde na barra expandida): globo da logo e iniciais do usuário.
    st.markdown(
        '<div class="ibc-rail-id">'
        f'<img src="{_globo_logo_uri()}" alt="Demo" class="ibc-rail-logo">'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("""
    <style>
        [data-testid="stSidebarUserContent"] {
            padding-top: 0 !important;
        }
        /* separadores da lateral mais próximos do conteúdo */
        /* o 1º item depois da linha que fecha o menu (nome do relatório e filtros) sobe um pouco */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(> [data-testid="stMarkdownContainer"] hr) + [data-testid="stElementContainer"] { margin-top: -0.7rem !important; }
        [data-testid="stSidebar"] hr, [data-testid="stSidebar"] [data-testid="stDivider"] { margin-top: 0.55rem !important; margin-bottom: 0.55rem !important; }
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(> iframe[height="0"]) { height: 0 !important; margin: 0 !important; overflow: hidden !important; }
        /* Menu em popover: a janelinha com os painéis do grupo abre colada na lateral da barra, na altura do botão, num painel azul
           com o nome do grupo em cima e os painéis como linhas de texto; não empurra os filtros da barra lateral. */
        div[data-testid="stPopoverBody"] {
            left: 281px !important;
            margin-top: -46px !important;
            min-width: 240px !important;
            background: #151b28 !important;
            border: 1px solid #2a3350 !important;
            border-left: none !important;
            border-radius: 0 12px 12px 0 !important;
            padding: 10px 18px 12px 14px !important;
            box-shadow: 8px 8px 24px rgba(0,0,0,0.5) !important;
        }
        /* identificação (globo + iniciais): escondida na barra expandida, aparece só na recolhida */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.ibc-rail-id) { display: none; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stElementContainer"]:has(.ibc-rail-id) { display: block !important; }
        .ibc-rail-id { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 4px 0 10px; margin-bottom: 2px; border-bottom: 0.5px solid #2a3350; }
        .ibc-rail-logo { width: 44px; height: 44px; border-radius: 50%; }
        .ibc-rail-av { width: 38px; height: 38px; border-radius: 50%; background: #2a3350; border: 1.5px solid #4A7FB5; color: #e8eaf0; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; cursor: default; }
        /* Menu recolhido (botão « da lateral): a barra vira uma coluna estreita só com os ícones; os grupos abrem a janelinha ao lado.
           O estado vem do atributo data-ibc-rail, que o script do menu (mais abaixo) coloca na lateral; a tela sempre abre expandida. */
        section[data-testid="stSidebar"][data-ibc-rail="1"] { width: 72px !important; min-width: 72px !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] { padding-left: 0 !important; padding-right: 0 !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarContent"] { padding-left: 0 !important; padding-right: 0 !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stLayoutWrapper"] { width: 100% !important; justify-content: center !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stElementContainer"]:not(:has(.ibc-rail-id)):not(.st-key-nav_hub_relatorios):not(.st-key-nav_resumo_pendencias):not(.st-key-admin_lateral):not(.st-key-sair_lateral):not(:has([data-testid="stPopover"])):not(:has(> iframe[height="0"])) { display: none !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stHorizontalBlock"] { flex-direction: column !important; gap: 0.5rem !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarHeader"] > *:not([data-testid="stSidebarCollapseButton"]) { display: none !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarCollapseButton"] { transform: rotate(180deg); margin: 0 auto !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button p,
        section[data-testid="stSidebar"][data-ibc-rail="1"] .st-key-admin_lateral button p,
        section[data-testid="stSidebar"][data-ibc-rail="1"] .st-key-sair_lateral button p,
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stPopover"] button p { font-size: 0 !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button p::before,
        section[data-testid="stSidebar"][data-ibc-rail="1"] .st-key-admin_lateral button p::before,
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stPopover"] button p::before { content: attr(data-ico); font-size: 1.35rem; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stPopover"] button [data-testid="stIconMaterial"] { display: none !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] .stButton button, section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stPopover"] button { padding-left: 0 !important; padding-right: 0 !important; justify-content: center !important; }
        /* botões da barra recolhida: quadrados de 48 px centralizados, com o ícone no meio (sem cortar) */
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stElementContainer"],
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stPopover"],
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stColumn"] { width: 100% !important; min-width: 0 !important; flex: none !important; display: flex; justify-content: center; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] .stButton,
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stPopover"] { width: 48px !important; max-width: 48px !important; margin: 0 auto !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] .stButton button,
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stPopover"] > button,
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] [data-testid="stPopover"] button { width: 48px !important; min-width: 48px !important; height: 44px !important; padding: 0 !important; overflow: visible !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] button > div,
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] button [data-testid="stMarkdownContainer"] { width: 100% !important; margin: 0 !important; display: flex !important; justify-content: center !important; align-items: center !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stSidebarUserContent"] button p { margin: 0 !important; width: 100%; display: flex !important; justify-content: center; line-height: 1 !important; }
        /* grupos (popover): a setinha do lado do nome ocupava espaço e empurrava o ícone para a esquerda; some, e o ícone fica no centro */
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stPopover"] button > div > *:not(:first-child) { display: none !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [data-testid="stPopover"] button > div > *:first-child { flex: 1 1 100% !important; width: 100% !important; justify-content: center !important; }
        /* todos os ícones do mesmo tamanho (emojis e o ícone de sair) */
        section[data-testid="stSidebar"][data-ibc-rail="1"] .st-key-sair_lateral button [data-testid="stIconMaterial"],
        section[data-testid="stSidebar"][data-ibc-rail="1"] .st-key-sair_lateral button span { font-size: 1.5rem !important; width: auto !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] button p::before { font-size: 1.5rem !important; line-height: 1 !important; }
        /* menu do usuário, barra expandida: cartão de perfil (círculo com as iniciais, nome e tempo de acesso, seta à direita) */
        [data-testid="stSidebar"] [class*="st-key-menu_usuario"] button { background: #1a2133 !important; border: 0.5px solid #2a3350 !important; border-radius: 10px !important; padding: 10px 12px !important; height: auto !important; min-height: 0 !important; }
        [data-testid="stSidebar"] [class*="st-key-menu_usuario"] button p { display: grid !important; grid-template-columns: 34px minmax(0, 1fr); column-gap: 10px; align-items: center; text-align: left; margin: 0 !important; line-height: 1.25 !important; }
        [data-testid="stSidebar"] [class*="st-key-menu_usuario"] button p strong { width: 34px; height: 34px; min-width: 34px; flex: none; white-space: nowrap; padding: 0; border-radius: 50%; background: #2a3350; border: 1.5px solid #4A7FB5; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; color: #e8eaf0; }
        [data-testid="stSidebar"] [class*="st-key-menu_usuario"] button p em { font-style: normal; font-weight: 500; font-size: 14px; color: #ffffff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        /* barra recolhida: só o símbolo redondo com as iniciais (sem caixa, sem nome, sem seta) */
        section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button { background: transparent !important; border: none !important; padding: 0 !important; height: 44px !important; width: 48px !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button p { display: flex !important; justify-content: center; align-items: center; font-size: 14px !important; width: 100% !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button { overflow: visible !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button > div, section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button [data-testid="stMarkdownContainer"] { width: 100% !important; min-width: 0 !important; display: flex !important; justify-content: center !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button p::before { content: none !important; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button p strong { width: 40px; height: 40px; min-width: 40px; }
        section[data-testid="stSidebar"][data-ibc-rail="1"] [class*="st-key-menu_usuario"] button p em { display: none !important; }
        div[data-testid="stPopoverBody"] .pop-titulo { color: #8892a4; font-size: 0.8rem; margin: 0 0 4px 12px; }
        div[data-testid="stPopoverBody"] button {
            background: transparent !important; border: none !important; box-shadow: none !important;
            color: #ffffff !important; justify-content: flex-start !important; padding: 0.15rem 0.7rem !important; min-height: 2rem !important;
        }
        div[data-testid="stPopoverBody"] button > div, div[data-testid="stPopoverBody"] button p { justify-content: flex-start !important; text-align: left !important; width: 100%; }
        div[data-testid="stPopoverBody"] button:hover { background: rgba(255,255,255,0.08) !important; }
        div[data-testid="stPopoverBody"] button[data-testid="stBaseButton-primary"] { background: #2a3350 !important; border-left: 3px solid #4A7FB5 !important; font-weight: 700; }
        /* Botão "Relatórios": mesma aparência dos grupos (Financeiro, Comercial). */
        /* Item selecionado do menu (painel aberto). */
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
            background: #2a3350 !important;
            border: 1px solid #4A7FB5 !important;
            color: #ffffff !important;
        }
        :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button {
            border: 1px solid rgba(250, 250, 250, 0.2);
            justify-content: center !important;
        }
        :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button > div {
            width: 100%;
            justify-content: center !important;
        }
        :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button [data-testid="stMarkdownContainer"],
        :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button p {
            text-align: center !important;
            width: 100%;
        }
        :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button[data-testid="stBaseButton-secondary"] {
            background: transparent !important;
        }
        :is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button[data-testid="stBaseButton-secondary"]:hover {
            border-color: rgba(250, 250, 250, 0.45) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        f"""<div style="text-align:center;padding:4px 0 4px;margin-top:-34px;">
            <img src="data:image/png;base64,{logo_b64}" style="width:90px;margin-bottom:4px;" />
            <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;
                        text-transform:uppercase;color:#94a3b8;">BI-FINANCEIRO</div>
        </div>""",
        unsafe_allow_html=True,
    )
    # usuário, tempo de acesso e botão Sair (antes ficavam no canto superior direito)
    st.markdown(
        """<style>
            .st-key-sair_lateral button { border:1px solid #5a2b2b; background:#2a1b1f; color:#f5a3a3; }
            .st-key-sair_lateral button:hover { border-color:#E24B4A; background:#3a2127; color:#ffd0d0; }
        </style>""",
        unsafe_allow_html=True,
    )
    # Usuário: as iniciais (e o nome, na barra expandida) abrem um menu com o tempo de acesso, Admin e Sair.
    _ini_usuario = _iniciais(usuario or nome)
    # Rótulo em markdown: **iniciais** (círculo) e *nome*; o CSS monta o cartão de perfil. O tempo de acesso fica na janelinha.
    with st.popover(f"**{_ini_usuario}** *{usuario or nome}*", width="stretch",
                    key=f"menu_usuario_{st.session_state['_painel_ativo'] or ''}"):   # chave nova a cada painel: reabre fechado
        st.markdown(f'<div class="pop-titulo">{usuario or nome}</div>', unsafe_allow_html=True)
        st.iframe(f"""
        <style>html, body {{ margin:0; padding:0; overflow:hidden; background:transparent; }}</style>
        <div id="acesso_expira_txt" style="font-size:12px;color:#e8a05a;padding-left:12px;
             font-family:'Source Sans Pro', sans-serif;">Acesso expira em: --</div>
        <script>
            var expiracao = new Date("{horario_expiracao.strftime('%Y-%m-%dT%H:%M:%S')}");
            var el = document.getElementById("acesso_expira_txt");
            function atualizar() {{
                var diffSeg = Math.floor((expiracao - new Date()) / 1000);
                if (diffSeg <= 0) {{ el.innerText = "Acesso expirado"; return; }}
                el.innerText = "Acesso expira em: " + Math.floor(diffSeg / 3600) + "h " +
                    Math.floor((diffSeg % 3600) / 60) + "m " + (diffSeg % 60) + "s";
            }}
            atualizar(); setInterval(atualizar, 1000);
        </script>""", height=24)
        if eh_admin:
            if st.button("🔐 Admin", key="admin_lateral", width="stretch",
                         type="primary" if st.session_state["_painel_ativo"] == "Acessos" else "secondary"):
                st.session_state["_painel_ativo"] = "Acessos"
                st.rerun()
        if st.button("Sair", icon=":material/logout:", key="sair_lateral", width="stretch"):
            st.session_state.clear()
            st.rerun()
    # Frase do dia logo abaixo do nome (uma por dia, a mesma para todos; lista em config/frases.py).
    # Some na barra recolhida, onde não cabe.
    st.markdown(
        '<div style="padding:4px 2px;margin:10px 0 2px;font-size:12.5px;line-height:1.5;color:#cfd3dc;">'
        f'{frases.frase_do_dia()[0]}</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("### 📂 Menu")

    def _resetar_filtros(nome_painel: str):
        st.session_state["_painel_ativo"] = nome_painel
        st.session_state.pop("_rel_gerou", None)
        st.session_state.pop("_cap_gerou", None)
        for chave_cap in ["cap_org", "cap_status", "cap_data_ini", "cap_data_fim"]:
            st.session_state.pop(chave_cap, None)
        for chave_dda in ["dda_data_inicial", "dda_data_final", "dda_valor_minimo", "dda_status", "dda_sacados"]:
            st.session_state.pop(chave_dda, None)
        for chave_rmf in ["_rmf_gerou", "_rmf_df", "_rmf_contas", "_rmf_periodo"]:
            st.session_state.pop(chave_rmf, None)
        for chave_rfm in ["_rfm_periodo", "rfm_periodo"]:
            st.session_state.pop(chave_rfm, None)
        for chave_rcmi in ["_rcmi_periodo", "rcmi_vencimento", "rcmi_status", "rcmi_grupo"]:
            st.session_state.pop(chave_rcmi, None)
        for chave in ["vencidas", "inconsistencias", "filtro_padrao",
                       "contas_receber", "contas_apagar", "adiantamentos"]:
            st.session_state.pop(f"_filtrou_{chave}", None)
            st.session_state.pop(f"_df_filtrado_{chave}", None)
            st.session_state.pop(f"_painel_origem_{chave}", None)
        st.rerun()

    painel_ativo_menu = st.session_state["_painel_ativo"] or ""

    for item in paineis:
        if len(item) == 3:
            icone, nome_pai, paginas = item
            if isinstance(paginas, dict):
                # Relatórios: um único botão que abre a página de cartões.
                ativo_hub = painel_ativo_menu == nome_pai or painel_ativo_menu.startswith(f"{nome_pai} > ")
                if st.button(f"{icone} {nome_pai}", width="stretch", key="nav_hub_relatorios",
                             type="primary" if ativo_hub else "secondary"):
                    if st.session_state["_painel_ativo"] != nome_pai:
                        _resetar_filtros(nome_pai)
                continue
            ativo_no_grupo = (st.session_state["_painel_ativo"] or "").startswith(f"{nome_pai} > ")
            # Cada grupo é um botão que abre uma janelinha (popover) com os painéis: o menu fica sempre com uma linha por grupo
            # e os filtros dos relatórios, logo abaixo, não descem quando um grupo é aberto.
            with st.popover(f"{icone} {nome_pai}", width="stretch", key=f"pop_{nome_pai}_{painel_ativo_menu}",   # chave nova a cada painel: a janelinha reabre fechada
                            type="primary" if ativo_no_grupo else "secondary"):
                st.markdown(f'<div class="pop-titulo">{nome_pai}</div>', unsafe_allow_html=True)
                for sub_icone, sub_nome in paginas:
                    nome_completo = f"{nome_pai} > {sub_nome}"
                    if st.button(f"{sub_icone} {ROTULOS_MENU.get(nome_completo, sub_nome)}", width="stretch", key=f"nav_{nome_completo}",
                                 type="primary" if painel_ativo_menu == nome_completo else "secondary"):
                        if st.session_state["_painel_ativo"] != nome_completo:
                            _resetar_filtros(nome_completo)
        else:
            icone, nome_painel = item
            if st.button(f"{icone} {nome_painel}", width="stretch",
                         key="nav_resumo_pendencias" if nome_painel == "Resumo Pendências" else f"nav_{nome_painel}",   # chave fixa: o menu recolhido mostra só o ícone
                         type="primary" if painel_ativo_menu == nome_painel else "secondary"):
                if st.session_state["_painel_ativo"] != nome_painel:
                    _resetar_filtros(nome_painel)

    st.markdown("---")

    # Menu em popover: abre ao passar o mouse sobre o grupo (sem clicar) e fecha ao tirar o mouse; o clique continua funcionando.
    # O Streamlit não tem "abrir ao passar o mouse" nativo; este script pequeno só dispara o clique do botão do grupo.
    components.html("""
    <script>
    (function () {
      const doc = window.parent.document;
      if (doc.__menuHoverV4) return;
      doc.__menuHoverV3 = true;
      // ── Menu recolhido: o botão « da lateral alterna entre expandida e só ícones (sem esconder a lateral por inteiro) ──
      const SEL_SIDE = 'section[data-testid="stSidebar"]';
      const side = () => doc.querySelector(SEL_SIDE);
      const recolhido = () => { const s = side(); return !!(s && s.getAttribute('data-ibc-rail') === '1'); };
      doc.addEventListener('click', function (e) {
        const c = e.target && e.target.closest ? e.target.closest('[data-testid="stSidebarCollapseButton"]') : null;
        if (!c) return;
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
        const s = side(); if (!s) return;
        s.setAttribute('data-ibc-rail', recolhido() ? '0' : '1');
      }, true);
      // cada botão do menu mostra só o ícone (primeiro caractere do texto) quando recolhido; o nome completo vira dica ao passar o mouse
      const seg = (window.Intl && Intl.Segmenter) ? new Intl.Segmenter('pt', { granularity: 'grapheme' }) : null;
      function marcaIcones() {
        const s = side(); if (!s) return;
        s.querySelectorAll(':is(.st-key-nav_hub_relatorios, .st-key-nav_resumo_pendencias) button, .st-key-admin_lateral button, .st-key-sair_lateral button, [data-testid="stPopover"] button').forEach(function (b) {
          const p = b.querySelector('p'); if (!p) return;
          const t = (p.textContent || '').trim();
          if (!b.title) b.title = t;
          if (p.getAttribute('data-ico') === null) {
            if (b.closest('[class*="st-key-menu_usuario"]')) { p.setAttribute('data-ico', t.split(' ')[0]); return; }
            const g = seg ? Array.from(seg.segment(t), (x) => x.segment)[0] : Array.from(t)[0];
            p.setAttribute('data-ico', g && !/^[A-Za-zÀ-ÿ]/.test(g) ? g : '');
          }
        });
      }
      // Barra recolhida + abriu uma tela que tem filtros na lateral (período, organização etc.): expande sozinha, uma vez por tela.
      // Se você recolher de novo na mesma tela, ela respeita; só volta a expandir quando entrar em outra tela com filtros.
      const SEL_FILTROS = '[data-testid="stSidebarUserContent"] :is([data-testid="stDateInput"], [data-testid="stMultiSelect"], [data-testid="stSelectbox"], [data-testid="stTextInput"], [data-testid="stNumberInput"], [data-testid="stRadio"], [data-testid="stCheckbox"], [data-testid="stSegmentedControl"], [data-testid="stSlider"])';
      let tinhaFiltros = false;
      function expandeSeTemFiltros() {
        const s = side(); if (!s) return;
        const tem = !!s.querySelector(SEL_FILTROS);
        if (tem && !tinhaFiltros && recolhido()) s.setAttribute('data-ibc-rail', '0');
        tinhaFiltros = tem;
      }
      const SEL_BOTAO = '[data-testid="stSidebar"] [data-testid="stPopover"] button';
      const SEL_CORPO = '[data-testid="stPopoverBody"]';
      const botoes = () => Array.from(doc.querySelectorAll(SEL_BOTAO));
      const aberto = (b) => b.getAttribute('aria-expanded') === 'true';
      let sobre = false;          // o mouse está em cima de um botão de grupo ou do painel aberto
      let ultimo = Date.now();    // última vez em que esteve
      const marca = (t) => {
        sobre = !!(t && t.closest && (t.closest(SEL_BOTAO) || t.closest(SEL_CORPO)));
        if (sobre) ultimo = Date.now();
      };
      // passar o mouse no botão do grupo abre o painel (e fecha o de outro grupo)
      doc.addEventListener('mouseover', function (e) {
        marca(e.target);
        const bt = e.target.closest ? e.target.closest(SEL_BOTAO) : null;
        if (bt) {
          const outra = botoes().find((b) => aberto(b) && b !== bt);
          if (outra) outra.click();
          if (!aberto(bt)) setTimeout(function () { if (!aberto(bt)) bt.click(); }, 60);
        }
      });
      doc.addEventListener('mousemove', (e) => marca(e.target));
      // saiu da janela do navegador: nenhum elemento recebe evento, então marca como "fora"
      doc.documentElement.addEventListener('mouseleave', () => { sobre = false; });
      // Tela baixa: sem espaço embaixo, o Streamlit joga a janelinha para cima do botão. Aqui ela volta para a altura do botão
      // (alinhada ao topo dele), sem sair da tela por cima nem por baixo.
      function alinha() {
        const b = botoes().find(aberto);
        const c = doc.querySelector(SEL_CORPO);
        if (!b || !c) return;
        const rb = b.getBoundingClientRect(), rc = c.getBoundingClientRect();
        const m = parseFloat(c.style.marginTop) || -46;
        const natural = rc.top - m;                       // posição sem o ajuste de margem
        let alvo = rb.top - 6;                            // topo da janelinha = topo do botão
        const h = window.parent.innerHeight;
        alvo = Math.min(alvo, h - rc.height - 8);         // não passa do fim da tela
        alvo = Math.max(alvo, 8);                         // nem do começo
        const novo = alvo - natural;
        if (Math.abs(novo - m) > 1) c.style.setProperty('margin-top', novo + 'px', 'important');
        // recolhido: a janelinha encosta na borda direita da barra estreita (expandida: segue a regra do CSS)
        const s = side();
        if (s && recolhido()) {
          const ml = parseFloat(c.style.marginLeft) || 0;
          const dx = s.getBoundingClientRect().right - (rc.left - ml);
          if (Math.abs(dx - ml) > 1) c.style.setProperty('margin-left', dx + 'px', 'important');
        } else if (c.style.marginLeft) {
          c.style.removeProperty('margin-left');
        }
      }
      // tirou o mouse de cima do botão e do painel (por 0,3 s, para dar tempo de ir do botão ao painel): fecha
      setInterval(function () {
        marcaIcones();
        expandeSeTemFiltros();
        alinha();
        if (sobre || Date.now() - ultimo < 300) return;
        const b = botoes().find(aberto);
        if (b) b.click();
      }, 150);
    })();
    </script>
    """, height=0)

rodape_lateral.render()

# Converte a navegação antiga para a nova página de relatórios sem perder
# qual relatório estava aberto durante um hot reload da aplicação.
_relatorios_antigos = {
    "Relatórios > Aprovadores": "Relatórios > 👤 Aprovadores",
    "Relatórios > Contas a Pagar": "Relatórios > 💰 Contas a Pagar",
}
if st.session_state["_painel_ativo"] in _relatorios_antigos:
    st.session_state["_painel_ativo"] = _relatorios_antigos[st.session_state["_painel_ativo"]]
    st.session_state.pop("relatorios_tab", None)

# ── Garante que analista não acesse painéis restritos ─────────────────────────
paineis_permitidos = _paineis_folha(paineis) + PAINEIS_FIXOS + (["Relatórios"] if paginas_relatorios_visiveis else [])
if st.session_state["_painel_ativo"] is not None and st.session_state["_painel_ativo"] not in paineis_permitidos:
    st.session_state["_painel_ativo"] = None
    st.rerun()

# ── Roteamento ────────────────────────────────────────────────────────────────
painel_atual = st.session_state["_painel_ativo"]

with st.container():
    if painel_atual is None:
        st.markdown(f"### 👋 Olá, {nome}!")
        if paineis_permitidos:
            st.caption("Selecione um painel no menu ao lado para começar.")
        else:
            st.warning("Seu usuário ainda não tem acesso a nenhum painel. Solicite a liberação ao administrador.")

    elif painel_atual == "Financeiro > Inconsistências":
        with st.spinner("Carregando dados..."):
            df_erros = carregar_aps_erro()
        inconsistencias.render(df_erros)

    elif painel_atual in ("Financeiro > Visão Geral MI-ME", "Financeiro > Mercado Interno", "Financeiro > Mercado Externo"):
        with st.spinner("Carregando dados..."):
            df_cr = carregar_contas_receber()
            df_gc_agentes_cr = carregar_grupo_credito_saldo_agente()
            df_gc_geral_cr   = carregar_grupo_credito_geral()
        contas_receber_painel.render(df_cr, df_grupo_agentes=df_gc_agentes_cr, df_grupo_geral=df_gc_geral_cr,
                                     secao={"Visão Geral MI-ME": "geral", "Mercado Interno": "mi", "Mercado Externo": "me"}[painel_atual.split(" > ")[1]])

    elif painel_atual == "Comercial > Grupo de Crédito":
        # Só informação atual (o que precisamos analisar antes de faturar) — sem
        # Total Faturado (histórico, foi para o relatório "Faturamento por
        # Cliente/Grupo"). Adiantamento (função Oracle por linha, às vezes
        # lenta/falha: ORA-20003) não carrega aqui: só quando o usuário clica em
        # "Carregar adiantamento" dentro da própria tela.
        with st.spinner("Carregando dados do Grupo de Crédito..."):
            df_gc_geral   = carregar_grupo_credito_geral()
            df_gc_agentes = carregar_grupo_credito_saldo_agente()
            df_cr_gc      = carregar_contas_receber()
        grupo_credito.render(df_gc_geral, df_gc_agentes, carregar_adiantamento_saldo_agente, df_contas_receber=df_cr_gc)

    elif painel_atual == "Comercial > Situação Cliente":
        with st.spinner("Carregando dados da Situação Cliente..."):
            df_cr_sc          = carregar_contas_receber()
            df_gc_agentes_sc  = carregar_grupo_credito_saldo_agente()
            df_gc_geral_sc    = carregar_grupo_credito_geral()
            df_faturado_sc    = carregar_total_faturado_cliente()
        # Adiantamento não é carregado aqui: a consulta é lenta e só é feita quando o
        # usuário clica em "Carregar adiantamento" dentro da própria tela.
        situacao_cliente.render(df_cr_sc, df_gc_agentes_sc, df_gc_geral_sc, df_faturado_sc,
                                 carregar_adiantamento_saldo_agente)

    elif painel_atual == "Comercial > Faturamento Cliente/Grupo":
        _pagina_faturamento_cliente_grupo()

    elif painel_atual == "Comercial > Faturamento por UF":
        with st.spinner("Carregando dados..."):
            df_cr_fe = carregar_contas_receber()
            df_fat_mensal_fe = carregar_faturado_mensal_cliente()
            df_agentes_fe = carregar_grupo_credito_saldo_agente()
            df_fat_fe = carregar_total_faturado_cliente()
        faturamento_estado.render(df_cr_fe, df_fat_mensal_fe, df_agentes_fe, df_fat_fe)

    elif painel_atual == "Comercial > Visão Geral Comercial":
        with st.spinner("Carregando dados..."):
            df_cr_vgc = carregar_contas_receber()
            df_agentes_vgc = carregar_grupo_credito_saldo_agente()
            df_geral_vgc = carregar_grupo_credito_geral()
        visao_geral_comercial.render(df_cr_vgc, df_agentes_vgc, df_geral_vgc)

    elif painel_atual == "Resumo Pendências":
        with st.spinner("Carregando dados..."):
            df_cr_rp = carregar_contas_receber()
        resumo_pendencias.render(df_cr_rp)

    elif painel_atual == "Tesouraria > Recebimento por Banco":
        relatorio_recebimentos.render()

    elif painel_atual == "Acessos":
        acessos.render(PAINEIS_ADMIN, CARTOES_RELATORIOS, AREAS_RELATORIOS, usuario, USUARIOS_ADMIN, admin_padrao=perfil == "admin")

    elif painel_atual == "Relatórios":
        _pagina_inicial_relatorios()

    elif painel_atual.startswith("Relatórios > "):
        pagina_relatorio = painel_atual.removeprefix("Relatórios > ")
        if st.button("← Voltar aos relatórios", key="voltar_relatorios"):
            _resetar_filtros("Relatórios")
        PAGINAS_RELATORIOS[pagina_relatorio]()
