"""
views/acessos.py
================
Tela do administrador: grupos de acesso. Cada grupo tem membros (usuários) e libera painéis e relatórios;
quem está em mais de um grupo recebe a soma. Grava em config/permissoes.json (services/permissoes.py).
"""

import time

import streamlit as st

from config import pdd
from services import auth_service, clientes_transferencia, permissoes
from services.data_service import carregar_lista_clientes

ADMIN = permissoes.GRUPO_ADMIN


def _catalogo(estrutura, cartoes, areas):
    """[(painel, [(tipo, chave, rótulo, subárea)])]; tipo 'r' = relatório, 'p' = painel do menu."""
    saida = []
    for item in estrutura:
        if len(item) != 3:
            continue
        _, nome, conteudo = item
        if isinstance(conteudo, dict):
            ordem = {a: n for n, a in enumerate(areas)}
            titulos = sorted(conteudo, key=lambda t: ordem.get(cartoes.get(t, ("", "Outros"))[1], 99))
            campos = [("r", t, t, cartoes.get(t, ("", "Outros"))[1]) for t in titulos]
        else:
            campos = [("p", f"{nome} > {sub}", f"{ic} {sub}", None) for ic, sub in conteudo]
        saida.append((nome, campos))
    return saida


def _k(g, chave):
    return f"acc_t|{g}|{chave}"


def _sel(g):
    """Conjunto de chaves liberadas no rascunho do grupo (fonte única; os toggles só espelham este conjunto)."""
    return st.session_state[f"acc_sel|{g}"]


def _carregar_rascunho(g, dados, catalogo):
    reg = dados["grupos"][g]
    st.session_state[f"acc_mem|{g}"] = list(reg["membros"])
    st.session_state[f"acc_sel|{g}"] = set(reg["paineis"]) | set(reg["relatorios"])


def _rascunho(g, catalogo):
    paineis, relatorios = [], []
    for _, campos in catalogo:
        for tipo, chave, _, _ in campos:
            if chave in _sel(g):
                (paineis if tipo == "p" else relatorios).append(chave)
    return {"paineis": sorted(paineis), "relatorios": sorted(relatorios),
            "membros": sorted(st.session_state.get(f"acc_mem|{g}", []))}


def _marcar_painel(g, campos, chave_painel):
    for _, chave, _, _ in campos:
        (_sel(g).add if st.session_state[chave_painel] else _sel(g).discard)(chave)


def _alternar(g, chave):
    (_sel(g).add if st.session_state[_k(g, chave)] else _sel(g).discard)(chave)


@st.cache_data(ttl=300, show_spinner=False)
def _buscar(termo):
    return auth_service.buscar_usuarios(termo)


def _nomes(logins):
    """Nome completo dos logins (consulta o AD só dos que faltam; um login sem resposta é tentado de novo após 1 min)."""
    nomes = st.session_state.setdefault("_acc_nomes", {})
    tentativas = st.session_state.setdefault("_acc_nomes_tent", {})
    agora = time.time()
    faltam = [l for l in logins if l not in nomes and agora - tentativas.get(l, 0) > 60]
    if faltam:
        nomes.update(auth_service.nomes_por_login(faltam))
        tentativas.update({l: agora for l in faltam})
    return nomes


def _adicionar_membro(g, usuario, chave_busca, nome=None):
    if nome:
        st.session_state.setdefault("_acc_nomes", {})[usuario] = nome
    if usuario not in st.session_state[f"acc_mem|{g}"]:
        st.session_state[f"acc_mem|{g}"] = st.session_state[f"acc_mem|{g}"] + [usuario]
    st.session_state[chave_busca] = ""


def _remover_membro(g, usuario):
    st.session_state[f"acc_mem|{g}"] = [u for u in st.session_state[f"acc_mem|{g}"] if u != usuario]


def _alternar_painel(chave):
    desligados = st.session_state["acc_pn_des"]
    (desligados.discard if st.session_state[f"acc_pn|{chave}"] else desligados.add)(chave)


def _previa_menu(g, catalogo, desativados):
    """Prévia do menu que o grupo verá, montada do rascunho (o que está marcado agora, mesmo sem salvar). Itens desativados
    para todos (Painéis) não aparecem; painel sem nenhum item liberado some, como no menu real."""
    with st.container(border=True, key="acc_pn_prev"):
        st.markdown("**Prévia do menu**")
        st.caption("Como o menu fica para este grupo, com o que está marcado agora.")
        total = 0
        for nome_painel, campos in catalogo:
            itens = [rot for _, ch, rot, _ in campos if ch in _sel(g) and ch not in desativados]
            if not itens:
                continue
            total += len(itens)
            st.markdown(f"📁 **{nome_painel}**")
            st.markdown("\n".join(f"- {rot}" for rot in itens))
        if not total:
            st.caption("Nenhum painel liberado: o grupo vê um menu vazio.")
        else:
            st.caption(f"{total} item(ns) no menu.")


def _secao_paineis(dados, catalogo, quem):
    """Painéis ativos/desativados: todos entram marcados; desmarcar desativa para TODOS (inclusive administradores).
    Só o administrador padrão chega aqui."""
    salvo = {str(x) for x in dados.get("desativados", [])}
    if "_acc_pn_init" not in st.session_state:
        st.session_state["acc_pn_des"] = set(salvo)
        st.session_state["_acc_pn_init"] = True
    desligados = st.session_state["acc_pn_des"]

    st.subheader("🔒 Painéis")
    st.caption(f"{len(desligados)} item(ns) desativado(s)." if desligados else "Nenhum item desativado.")
    st.caption("Todos entram marcados. Desmarcar um item o desativa: ele some do menu e da página de Relatórios para "
               "todos, inclusive para você. Para voltar a vê-lo, marque de novo aqui.")
    for nome_painel, campos in catalogo:
        ativos = sum(1 for _, ch, _, _ in campos if ch not in desligados)
        with st.expander(f"{nome_painel}   ·   {ativos}/{len(campos)} ativos", expanded=ativos < len(campos)):
            area_atual = None
            for _, chave, rotulo, area in campos:
                if area and area != area_atual:
                    st.caption(area)
                    area_atual = area
                st.session_state[f"acc_pn|{chave}"] = chave not in desligados
                st.toggle(rotulo, key=f"acc_pn|{chave}", on_change=_alternar_painel, args=(chave,))

    if desligados != salvo:
        with st.container(border=True):
            t, d, s = st.columns([3, 1, 1])
            t.markdown("**Você tem alterações não salvas**")
            if d.button("Descartar", key="acc_pn_desc", width="stretch"):
                st.session_state.pop("_acc_pn_init", None)
                st.rerun()
            if s.button("Salvar", key="acc_pn_salvar", type="primary", width="stretch"):
                dados["desativados"] = sorted(desligados)
                permissoes.salvar(dados, quem)
                st.session_state.pop("_acc_pn_init", None)
                st.session_state["_acessos_msg"] = "Painéis salvos. Os itens desativados saíram do menu de todos."
                st.rerun()


def _secao_transferencia(quem):
    """Clientes do Mercado Interno que pagam por transferência (todo cliente é boleto por padrão). Só o administrador padrão."""
    st.subheader("💱 Clientes por Transferência")
    st.caption("Todo cliente do Mercado Interno é boleto por padrão. Aqui ficam só os que pagam por transferência: eles saem do "
               "relatório Boleto Não Gerado e ganham a fatia \"Transferência\" em Distribuição por Banco.")
    lista = clientes_transferencia.carregar()

    df = carregar_lista_clientes()
    nomes = {}
    if df is not None and not df.empty:
        for cod, nome in zip(df["COD_CLIENTE"], df["CLIENTE"]):
            nomes[str(int(cod))] = f"{nome} - {int(cod)}"
    opcoes = [c for c in nomes if c not in lista]
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    escolha = c1.selectbox("Incluir cliente (busque por nome ou código)", opcoes, index=None,
                           format_func=lambda c: nomes.get(c, c), placeholder="Digite o nome ou o código do cliente",
                           key="acc_transf_busca")
    if c2.button("Incluir", key="acc_transf_incluir", type="primary", width="stretch", disabled=escolha is None):
        nome_cli = nomes[escolha].rsplit(" - ", 1)[0]
        clientes_transferencia.incluir(escolha, nome_cli, quem)
        st.session_state["_acessos_msg"] = f"{nome_cli} incluído em Clientes por Transferência."
        st.session_state.pop("acc_transf_busca", None)
        st.rerun()

    st.markdown(f"**{len(lista)} cliente(s)**")
    if not lista:
        st.info("Nenhum cliente cadastrado: todos são tratados como boleto.")
    for cod, info in sorted(lista.items(), key=lambda kv: kv[1].get("nome", "")):
        a, b, c = st.columns([5, 3, 1], vertical_alignment="center")
        a.markdown(f"**{info.get('nome') or '—'}**  ·  {cod}")
        b.caption(f"{info.get('incluido_por', '')} · {info.get('em', '')}")
        if c.button("✕", key=f"acc_transf_rm|{cod}", help="Remover da lista (volta a ser boleto)"):
            clientes_transferencia.remover(cod, quem)
            st.session_state["_acessos_msg"] = f"{info.get('nome') or cod} removido (volta a ser boleto)."
            st.rerun()


def _secao_opcoes(quem):
    """Opções do relatório (só o administrador padrão). Hoje: ocultar o PDD do Contas a Receber MI."""
    st.subheader("⚙️ Opções do relatório")
    atual = pdd.ocultar_pdd()
    novo = st.toggle(f"Ocultar PDD do Contas a Receber MI (vencido há mais de {pdd.DIAS_PDD} dias)", value=atual,
                     key="acc_opc_ocultar_pdd")
    st.caption("Ligado: os títulos PDD saem do Contas a Receber MI inteiro (cards, rosca, aging, tabelas, Excel, relatório e "
               "Visão Geral Comercial) e o Saldo em Aberto cai pelo mesmo valor. Vale para todos os usuários. "
               "Desligado: tudo como antes.")
    if novo != atual:
        pdd.definir_ocultar_pdd(novo, quem)
        st.session_state["_acessos_msg"] = "PDD oculto do Contas a Receber MI." if novo else "PDD volta a aparecer no Contas a Receber MI."
        st.rerun()


def render(estrutura, cartoes, areas, quem, admins_fixos=(), admin_padrao=False):
    st.title("🔐 Acessos")
    dados = permissoes.carregar()
    fixos = {permissoes.normalizar_usuario(u) for u in admins_fixos}
    dados["grupos"][ADMIN]["membros"] = sorted(set(dados["grupos"][ADMIN]["membros"]) | fixos)
    catalogo = _catalogo(estrutura, cartoes, areas)

    if msg := st.session_state.pop("_acessos_msg", None):
        st.success(msg)

    nomes = [ADMIN] + sorted(n for n in dados["grupos"] if n != ADMIN)
    g = st.session_state.get("_acessos_grupo")
    if g not in nomes:
        g = nomes[0] if len(nomes) == 1 else nomes[1]
    st.session_state["_acessos_grupo"] = g
    # Os toggles de um grupo somem do estado quando ele deixa a tela; ao trocar de grupo o rascunho recomeça do salvo.
    if st.session_state.get("_acc_init") != g:
        _carregar_rascunho(g, dados, catalogo)
        st.session_state["_acc_init"] = g

    secao_paineis = bool(admin_padrao) and st.session_state.get("_acessos_secao") == "paineis"
    secao_transf = bool(admin_padrao) and st.session_state.get("_acessos_secao") == "transferencia"
    secao_opc = bool(admin_padrao) and st.session_state.get("_acessos_secao") == "opcoes"
    c_esq, c_dir = st.columns([1, 3], gap="large")

    with c_esq:
        st.caption("GRUPOS")
        for n in nomes:
            qtd = len(dados["grupos"][n]["membros"])
            if st.button(f"{n}  ·  {qtd}", key=f"acc_g|{n}", width="stretch",
                         type="primary" if n == g and not secao_paineis and not secao_transf and not secao_opc else "secondary"):
                st.session_state["_acessos_grupo"] = n
                st.session_state["_acessos_secao"] = None
                st.session_state.pop("_acc_pn_init", None)
                st.rerun()
        with st.form("acc_novo_grupo", clear_on_submit=True):
            novo = st.text_input("Novo grupo", placeholder="Ex.: Comercial", label_visibility="collapsed")
            if st.form_submit_button("➕ Novo grupo", width="stretch"):
                novo = novo.strip()
                if not permissoes.nome_grupo_valido(novo):
                    st.error("Use de 2 a 40 caracteres.")
                elif novo.lower() in {n.lower() for n in dados["grupos"]}:
                    st.error("Já existe um grupo com esse nome.")
                else:
                    dados["grupos"][novo] = {"paineis": [], "relatorios": [], "membros": []}
                    permissoes.salvar(dados, quem)
                    st.session_state["_acessos_grupo"] = novo
                    st.rerun()
        st.caption("Quem não está em nenhum grupo não acessa nada.")
        if admin_padrao:
            st.caption("SOMENTE ADMINISTRADOR PADRÃO")
            if st.button("🔒 Painéis", key="acc_secao_paineis", width="stretch",
                         type="primary" if secao_paineis else "secondary"):
                st.session_state["_acessos_secao"] = "paineis"
                st.session_state.pop("_acc_pn_init", None)
                st.rerun()
            if st.button("💱 Clientes por Transferência", key="acc_secao_transf", width="stretch",
                         type="primary" if secao_transf else "secondary"):
                st.session_state["_acessos_secao"] = "transferencia"
                st.rerun()
            if st.button("⚙️ Opções do relatório", key="acc_secao_opc", width="stretch",
                         type="primary" if secao_opc else "secondary"):
                st.session_state["_acessos_secao"] = "opcoes"
                st.rerun()

    with c_dir:
        if secao_paineis:
            _secao_paineis(dados, catalogo, quem)
            return
        if secao_transf:
            _secao_transferencia(quem)
            return
        if secao_opc:
            _secao_opcoes(quem)
            return
        eh_admin_grupo = g == ADMIN
        rasc = _rascunho(g, catalogo)
        salvo = dados["grupos"][g]
        sujo = (rasc["membros"] != sorted(salvo["membros"]) or
                (not eh_admin_grupo and (rasc["paineis"] != sorted(salvo["paineis"]) or
                                         rasc["relatorios"] != sorted(salvo["relatorios"]))))

        st.subheader(g)
        if eh_admin_grupo:
            st.caption(f"{len(rasc['membros'])} usuário(s) · acesso total a todos os painéis e relatórios")
        else:
            partes = []
            for nome_painel, campos in catalogo:
                n = sum(1 for _, ch, _, _ in campos if ch in _sel(g))
                if n:
                    partes.append(f"{nome_painel} ({n}/{len(campos)})")
            st.caption(f"{len(rasc['membros'])} usuário(s) · "
                       + ("vê " + ", ".join(partes) if partes else "nenhum painel liberado ainda"))

        st.caption("1 · QUEM PARTICIPA")
        membros = st.session_state[f"acc_mem|{g}"]
        nomes_ad = _nomes(membros)
        if membros:
            st.markdown(
                "<style>[class*='st-key-acc_membros'] button { background:#1f6fd1; border-color:#1f6fd1; min-height:2rem; padding:0 .7rem; }"
                "[class*='st-key-acc_membros'] button p { color:#fff; font-size:.85rem; }"
                "[class*='st-key-acc_membros'] button:hover { background:#2f82e6; border-color:#2f82e6; }</style>",
                unsafe_allow_html=True,
            )
            fixos_grupo = [u for u in membros if eh_admin_grupo and u in fixos]
            demais = [u for u in membros if u not in fixos_grupo]
            for sufixo, titulo, lista in (("fixos", "ADMINISTRADOR PADRÃO", fixos_grupo), ("outros", "OUTROS MEMBROS", demais)):
                if not lista:
                    continue
                if fixos_grupo:
                    st.caption(titulo)
                with st.container(key=f"acc_membros_{sufixo}", horizontal=True):
                    for u in lista:
                        fixo = u in fixos_grupo
                        rotulo = f"({u}) {nomes_ad[u]}" if u in nomes_ad else u
                        st.button(("🔒 " if fixo else "✕ ") + rotulo, key=f"acc_rm|{g}|{u}", width="content",
                                  on_click=_remover_membro, args=(g, u), disabled=fixo,
                                  help="Administrador padrão do sistema, não pode ser removido" if fixo else "Remover do grupo")
        else:
            st.caption("Ninguém ainda. Adicione abaixo.")

        chave_busca = f"acc_busca|{g}"
        termo = st.text_input("Buscar usuário", key=chave_busca, label_visibility="collapsed",
                              placeholder="Buscar no AD por nome ou login (mín. 3 letras)")
        termo_limpo = termo.strip()
        if len(termo_limpo) >= 3:
            achados = [r for r in _buscar(termo_limpo) if r[0] not in membros]
            if achados:
                ca, cb = st.columns([4, 1])
                escolhido = ca.selectbox("Resultado", achados, format_func=lambda r: f"({r[0]}) {r[1]}",
                                         label_visibility="collapsed", key=f"acc_res|{g}")
                cb.button("Adicionar", key=f"acc_ad|{g}", width="stretch", type="primary",
                          on_click=_adicionar_membro, args=(g, escolhido[0], chave_busca, escolhido[1]))
            else:
                st.caption("Nenhum usuário novo encontrado no AD para essa busca.")
                manual = permissoes.normalizar_usuario(termo_limpo)
                if permissoes.usuario_valido(manual) and manual not in membros:
                    st.button(f"Adicionar \"{manual}\" mesmo assim", key=f"acc_man|{g}",
                              on_click=_adicionar_membro, args=(g, manual, chave_busca))
        if eh_admin_grupo:
            st.caption("🔒 Administradores padrão do sistema (definidos no código) não podem ser removidos.")

        if not eh_admin_grupo:
            st.caption("2 · O QUE O GRUPO PODE VER")
            # Sem quebra de linha nos nomes (toggles, títulos dos painéis e prévia): a coluna da esquerda leva mais largura.
            st.markdown(
                "<style>[class*='st-key-acc_pn_tog'] label p, [class*='st-key-acc_pn_tog'] summary p,"
                "[class*='st-key-acc_pn_prev'] p, [class*='st-key-acc_pn_prev'] li{white-space:nowrap !important}"
                "[class*='st-key-acc_pn_prev'] li{margin-left:0}</style>",
                unsafe_allow_html=True,
            )
            col_tog, col_prev = st.columns([5, 3], gap="large")
            with col_tog.container(key="acc_pn_tog"):
                for nome_painel, campos in catalogo:
                    chaves = [ch for _, ch, _, _ in campos]
                    n = sum(1 for ch in chaves if ch in _sel(g))
                    chave_painel = f"acc_p|{g}|{nome_painel}"
                    st.session_state[chave_painel] = n == len(chaves)
                    with st.expander(f"{nome_painel}   ·   {n}/{len(chaves)}", expanded=n > 0):
                        st.toggle("Todos", key=chave_painel,
                                  on_change=_marcar_painel, args=(g, campos, chave_painel))
                        area_atual = None
                        for _, chave, rotulo, area in campos:
                            if area and area != area_atual:
                                st.caption(area)
                                area_atual = area
                            st.session_state[_k(g, chave)] = chave in _sel(g)
                            st.toggle(rotulo, key=_k(g, chave), on_change=_alternar, args=(g, chave))
            with col_prev:
                _previa_menu(g, catalogo, {str(x) for x in dados.get("desativados", [])})

        if sujo:
            with st.container(border=True):
                t, d, s = st.columns([3, 1, 1])
                t.markdown("**Você tem alterações não salvas**")
                if d.button("Descartar", key="acc_desc", width="stretch"):
                    st.session_state.pop("_acc_init", None)
                    st.rerun()
                if s.button("Salvar", key="acc_salvar", type="primary", width="stretch"):
                    salvo["membros"] = rasc["membros"]
                    if not eh_admin_grupo:
                        salvo["paineis"], salvo["relatorios"] = rasc["paineis"], rasc["relatorios"]
                    permissoes.salvar(dados, quem)
                    st.session_state["_acessos_msg"] = f"Grupo {g} salvo."
                    st.rerun()

        if not eh_admin_grupo:
            chave_conf = f"acc_confirma|{g}"
            if not st.session_state.get(chave_conf):
                if st.button("🗑️ Excluir grupo", key="acc_excluir_ini"):
                    st.session_state[chave_conf] = True
                    st.rerun()
            else:
                st.warning(f"Excluir o grupo {g}? Os membros perdem o acesso dado por ele.")
                c1, c2, _ = st.columns([1, 1, 3])
                if c1.button("Confirmar exclusão", key="acc_excluir", type="primary", width="stretch"):
                    dados["grupos"].pop(g, None)
                    permissoes.salvar(dados, quem)
                    st.session_state.pop(chave_conf, None)
                    st.session_state.pop("_acessos_grupo", None)
                    st.session_state.pop("_acc_init", None)
                    st.session_state["_acessos_msg"] = f"Grupo {g} excluído."
                    st.rerun()
                if c2.button("Cancelar", key="acc_excluir_cancela", width="stretch"):
                    st.session_state.pop(chave_conf, None)
                    st.rerun()
