"""
views/resumo_pendencias.py
==========================
Painel "Resumo Pendências": acompanhamento por QUANTIDADE (só o cartão Esperado e Recebido mostra também valores em reais) das pendências em aberto:
  - Descontos Contratuais Pendentes (mesma regra do card do Contas a Receber MI);
  - Boletos Não Gerados (mesma regra do relatório; pronto para gerar x bloqueado por desconto);
  - Notas Pendentes de Validação (bloqueantes e validação manual, de todos os clientes do Mercado Interno);
  - Esperado e Recebido no banco DO DIA, em quantidade de títulos;
e, embaixo, o gráfico das notas pendentes de validação (uma barra por nota; o NF abre o controle de venda no SyncProcess).
Só aparece no menu de quem está no grupo fixo "Resumo Pendências" (tela Acessos).
"""

import base64
import datetime
from html import escape

import pandas as pd
import streamlit as st

from services.data_service import (carregar_controles_abertos_mi, carregar_grupo_credito_geral, carregar_grupo_credito_saldo_agente,
                                   carregar_lista_clientes, carregar_recebido_mensal_mi, carregar_recebimento_hoje_mi)
from utils.pendencias import ESTADO_ROTULO, colunas_documentos, notas_pendentes_todas, url_controle_venda
from views.contas_receber import _nomes_curtos, formatar_moeda
from views.relatorio_boleto_nao_gerado import _status_boleto
from views.relatorio_desconto_financeiro_pendente import resumo_descontos_pendentes

_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_AMARELO, _AZUL, _VERMELHO, _VERDE, _CINZA = "#F59E0B", "#378ADD", "#E24B4A", "#22c55e", "#6b7280"

_CSS = """<style>
.rp-grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:4px 0 14px}
.rp-t{font-size:1.05rem;font-weight:600;color:#fafafa;margin:0 0 8px 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-card{background:#1e1e2e;border-radius:12px;border-top:4px solid;box-sizing:border-box;padding:12px 16px;height:196px;
 display:flex;flex-direction:column;overflow:hidden}
.rp-top{display:flex;align-items:baseline;justify-content:space-between;font-size:11px;color:#8892a4}
.rp-top b{font-size:28px;color:#fff;line-height:1.1}.rp-top b i{font-style:normal;font-size:11px;font-weight:400;margin-left:4px}
.rp-ln{height:1px;background:#2a2a3a;margin:8px 0}
.rp-nm{font-size:19px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-sb{font-size:13px;margin-top:2px}
.rpk-janela{height:56px;overflow:hidden}
.rpk-item{height:56px;display:flex;flex-direction:column;justify-content:center}
.rpk-nome{font-size:19px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rpk-sub{font-size:13px}
.rpk-ponto{width:6px;height:6px;border-radius:50%;background:#4b5563;display:inline-block;margin:0 2px}
@media (prefers-reduced-motion:reduce){.rp-card [class*=rpk],.rp-card [class$=l],.rpk-ponto{animation:none !important}}
.rp-mt{font-size:11px;color:#8892a4}
.rp-vl{font-size:15px;font-weight:700;color:#fff}
.rp-barra{height:8px;border-radius:4px;background:rgba(128,128,128,0.18);overflow:hidden;margin:6px 0 4px}
.rp-barra div{height:100%}
.rp-lista{background:#1e1e2e;border-radius:12px;border-top:4px solid #E24B4A;padding:14px 18px}
.rp-q{display:grid;gap:8px;align-items:center;font-size:13px}
.rp-qh{font-size:11px;color:#8892a4;text-align:center;line-height:1.2;padding-bottom:6px;border-bottom:1px solid #2a2a3a;align-items:end}
.rp-q a{color:#fff;font-weight:600;text-decoration:none;white-space:nowrap}.rp-q a:hover{text-decoration:underline;color:#6db3f5}
.rp-cad{vertical-align:-2px}.rp-cadc{display:flex;align-items:center;justify-content:center}
.rp-cli{color:#aab2c5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-c{height:24px;border-radius:5px;font-size:11px;display:flex;align-items:center;justify-content:center;font-weight:600}
.rp-c-VENCIDO{background:rgba(226,75,74,.28);color:#f3a3a2}.rp-c-VALIDANDO{background:rgba(55,138,221,.25);color:#8ec2f5}
.rp-c-NAO_ANEXADO,.rp-c-PENDENTE{background:rgba(156,163,175,.22);color:#d1d5db}
.rp-c-OK{background:rgba(34,197,94,.16);color:#6fd69a}.rp-c-ND{color:#6b7280;font-weight:400}
.rp-qr{padding:5px 0;border-bottom:1px solid #26263a}.rp-pz{text-align:right;color:#8892a4;white-space:nowrap}
@media (max-width:760px){.rp-cli,.rp-pz{display:none}}
</style>"""


_ALT, _SEG = 56, 4   # altura de um cliente no ticker (px) e segundos por cliente


def _ticker(chave: str, itens: list, cor: str) -> str:
    """Passa de cliente em cliente sozinho (nome e subtexto; pausa com o mouse em cima), só com CSS. `itens` = [(nome, subtexto,
    cor do subtexto ou None)]. Com um cliente só, não anima."""
    def linha(i):
        return (f'<div class="rpk-item" title="{escape(i[0], quote=True)}"><span class="rpk-nome">{escape(i[0])}</span>'
                f'<span class="rpk-sub" style="color:{i[2] or cor}">{i[1]}</span></div>')
    if len(itens) == 1:
        return f'<div class="rpk-janela">{linha(itens[0])}</div>'
    n = len(itens)
    quadros = "".join(f"{k * 100 / n:.3f}%,{k * 100 / n + 82 / n:.3f}%{{transform:translateY(-{_ALT * k}px)}}" for k in range(n))
    quadros += f"100%{{transform:translateY(-{_ALT * n}px)}}"
    pontos, anim = "", ""
    for k in range(n):
        a, b = k * 100 / n, (k + 1) * 100 / n
        ini = f"0%,{a - 0.01:.3f}%{{background:#4b5563}}" if k else ""
        fim = f"{b:.3f}%,100%{{background:#4b5563}}" if k < n - 1 else ""
        anim += (f"@keyframes {chave}d{k}{{{ini}{a:.3f}%,{b - 0.01:.3f}%{{background:{cor}}}{fim}}}"
                 f".{chave}d{k}{{animation:{chave}d{k} {_SEG * n}s infinite}}")
        pontos += f'<span class="rpk-ponto {chave}d{k}"></span>'
    return (f"<style>@keyframes {chave}{{{quadros}}}{anim}.{chave}l{{animation:{chave} {_SEG * n}s infinite}}"
            f".rp-card:hover .{chave}l,.rp-card:hover .rpk-ponto{{animation-play-state:paused}}</style>"
            f'<div class="rpk-janela"><div class="{chave}l">{"".join(linha(i) for i in itens + itens[:1])}</div></div>'
            f'<div style="text-align:center;margin:0 0 4px">{pontos}</div>')


def _card(titulo: str, rotulo: str, numero, unidade: str, cor: str, destaque: str, sub: str, rodape: str,
          itens: list = None, chave: str = "rpk") -> str:
    """Cartão no padrão do Descontos Contratuais Pendentes: rótulo e quantidade em cima, cliente(s) no meio (com `itens`, passa de
    um em um sozinho), rodapé fixo."""
    meio = (_ticker(chave, itens, cor) if itens
            else f'<div class="rp-nm">{destaque}</div><div class="rp-sb" style="color:{cor}">{sub}</div>')
    return (f'<div><div class="rp-t" title="{escape(titulo)}">{escape(titulo)}</div>'
            f'<div class="rp-card" style="border-color:{cor}"><div class="rp-top"><span>{escape(rotulo)}</span>'
            f'<b>{numero}<i style="color:{cor}">{escape(unidade)}</i></b></div><div class="rp-ln"></div>'
            f'{meio}'
            f'<div style="flex:1"></div><div class="rp-ln"></div><div class="rp-mt">{rodape}</div></div></div>')


def _indisponivel(titulo: str) -> str:
    return _card(titulo, "Indisponível", "—", "", _CINZA, "—", "&nbsp;", "não foi possível consultar agora")


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


def _card_descontos(df_cr: pd.DataFrame) -> str:
    titulo = "Descontos Contratuais Pendentes"
    desc = resumo_descontos_pendentes(df_cr)
    if desc is None:
        return _indisponivel(titulo)
    pend, erros = desc["pendentes"], desc["erros"]
    cor = "#ef4444" if erros else _AMARELO if pend else _VERDE
    if not pend:
        return _card(titulo, "Pendentes", 0, "título(s)", cor, "Tudo aplicado", "&nbsp;", "nenhum desconto a lançar")
    clientes = desc["por_cliente"][:10]
    itens = [(c, f"{q:02d} {_plural(q, 'título', 'títulos')}", None) for c, q in zip(_nomes_curtos([x[0] for x in clientes]), [x[1] for x in clientes])]
    rodape = f'{desc["clientes"]} cliente(s)' + (f' · <span style="color:#ef4444">{erros} com erro</span>' if erros else "")
    return _card(titulo, "Pendentes", pend, "título(s)", cor, "", "", rodape, itens=itens, chave="rpkd")


def _card_boletos(df_cr: pd.DataFrame) -> str:
    titulo = "Boletos Não Gerados"
    obrig = {"MERCADO", "SITUACAO_BOLETO", "SITUACAO", "TIPO_REGRA", "DESC_APLIC_NF", "DESC_APLIC_FIN", "COD_CLIENTE", "CLIENTE"}
    if df_cr is None or df_cr.empty or not obrig.issubset(df_cr.columns):
        return _indisponivel(titulo)
    from services import clientes_transferencia
    base = df_cr[(df_cr["MERCADO"] == "MI") & (df_cr["SITUACAO_BOLETO"] != "BOLETO GERADO")
                 & (df_cr["SITUACAO"].isin(["A VENCER", "VENCIDO"]))].copy()
    if "TIPO_PESSOA" in base.columns:                       # pessoa física não precisa de boleto
        base = base[base["TIPO_PESSOA"] != "F"]
    transf = clientes_transferencia.carregar()              # quem paga por transferência não recebe boleto
    if transf:
        base = base[~base["COD_CLIENTE"].astype(str).isin(transf)]
    if base.empty:
        return _card(titulo, "Sem boleto", 0, "título(s)", _VERDE, "Tudo com boleto", "&nbsp;", "nenhum título sem boleto")
    base["_ST"] = base.apply(_status_boleto, axis=1)
    livres = base[base["_ST"] == "LIBERADO"]
    bloq = int((base["_ST"] != "LIBERADO").sum())
    vencidos = int((livres["SITUACAO"] == "VENCIDO").sum())
    if livres.empty:
        return _card(titulo, "Sem boleto", 0, "título(s)", _AZUL, "Nenhum liberado", "&nbsp;",
                     f"{bloq} bloqueado(s) por desconto pendente")
    top = livres.groupby("CLIENTE").size().sort_values(ascending=False).head(10)
    itens = [(c, f"{int(q):02d} {_plural(int(q), 'título', 'títulos')}", None) for c, q in zip(_nomes_curtos([str(i) for i in top.index]), top.values)]
    rodape = (f'{livres["COD_CLIENTE"].nunique()} cliente(s) · {vencidos} vencido(s)'
              + (f' · {bloq} bloqueado(s)' if bloq else ""))
    return _card(titulo, "Prontos para gerar", len(livres), "título(s)", _AZUL, "", "", rodape, itens=itens, chave="rpkb")


def _nomes_clientes() -> dict:
    try:
        lista = carregar_lista_clientes()
        return {str(int(c)): str(n) for c, n in zip(lista["COD_CLIENTE"], lista["CLIENTE"]) if pd.notna(c)}
    except Exception:
        return {}


def _card_notas(notas) -> str:
    titulo = "Notas Pendentes de Validação"
    if notas is None:
        return _indisponivel(titulo)
    if notas.empty:
        return _card(titulo, "Pendentes", 0, "nota(s)", _VERDE, "Nenhuma pendência", "&nbsp;", "todas as notas validadas")
    bloq = notas[notas["TIPO"] == "BLOQUEANTE"]
    man = len(notas) - len(bloq)
    clientes = notas["COD_CLIENTE"].nunique()
    cor = _VERMELHO if len(bloq) else _AZUL
    por = (notas.assign(B=(notas["TIPO"] == "BLOQUEANTE").astype(int), M=(notas["TIPO"] != "BLOQUEANTE").astype(int))
           .groupby("COD_CLIENTE")[["B", "M"]].sum().sort_values(["B", "M"], ascending=False).head(10))
    nomes = _nomes_clientes()
    cheios = [nomes.get(str(int(float(c))), f"Cliente {c}") for c in por.index]
    itens = []
    for curto, (nb, nm) in zip(_nomes_curtos(cheios), por[["B", "M"]].itertuples(index=False)):
        if nb:
            sub = f"{nb} {_plural(nb, 'bloqueante', 'bloqueantes')}" + (f" · {nm} manual" if nm else "")
            itens.append((curto, sub, _VERMELHO))
        else:
            itens.append((curto, f"{nm} em validação manual", _AZUL))
    return _card(titulo, "Pendentes", len(notas), "nota(s)", cor, "", "",
                 f"{len(bloq)} bloqueante(s) · {man} manual(is) · {clientes} cliente(s)", itens=itens, chave="rpkn")


def _card_esperado_recebido(df_cr: pd.DataFrame) -> str:
    """Quantidade de títulos DO DIA: recebido = baixas que entraram no banco hoje (mesma regra do Resumo do Contas a Receber MI,
    pela data da baixa); esperado = recebido + parcelas que ainda estão em aberto para o crédito de hoje (vencimento + 1 dia
    útil, a mesma conta do bloco "Hoje" do Contas a Receber MI). Fim de semana: sem parcela esperada, só o que entrar."""
    titulo = "Esperado e Recebido no banco"
    hoje = datetime.date.today()
    try:
        rec = carregar_recebido_mensal_mi(hoje.year)
        if rec is None:
            return _indisponivel(titulo)
        d = rec[rec["DIA"].dt.date == hoje]
        recebido = d[["DOC", "AGN", "PARC"]].drop_duplicates().shape[0]
        info = carregar_recebimento_hoje_mi() or {}
        faltam = int(info.get("abertas", 0) or 0)
        valor_rec = float(pd.to_numeric(d["VALOR_PAGO"], errors="coerce").sum())
        valor_esp = valor_rec + max(float(info.get("aberto", 0) or 0), 0.0)
    except Exception:
        return _indisponivel(titulo)
    esperado = recebido + faltam
    pct = min(recebido / esperado * 100, 100.0) if esperado else 0.0
    pct_txt = f"{pct:.2f}".replace(".", ",")
    rodape = f"faltam {faltam} título(s) · {formatar_moeda(max(valor_esp - valor_rec, 0.0))} · só entrada no banco" if info else "sem crédito previsto hoje · só entrada no banco"
    return (f'<div><div class="rp-t" title="{titulo}">{titulo}</div><div class="rp-card" style="border-color:{_VERDE}">'
            f'<div class="rp-top"><span>Hoje, {hoje:%d/%m/%Y}</span><b>{pct_txt}<i style="color:{_VERDE}">%</i></b></div><div class="rp-ln"></div>'
            f'<div class="rp-mt">Esperado · {esperado} título(s)</div><div class="rp-vl">{formatar_moeda(valor_esp)}</div>'
            f'<div class="rp-barra"><div style="width:{pct:.1f}%;background:{_VERDE}"></div></div>'
            f'<div class="rp-mt">Recebido no banco · {recebido} título(s)</div><div class="rp-vl" style="color:{_VERDE}">{formatar_moeda(valor_rec)}</div>'
            f'<div style="flex:1"></div><div class="rp-ln"></div><div class="rp-mt">{rodape}</div>'
            f'</div></div>')


def _cadeado(cor: str, aberto: bool, rotulo: str) -> str:
    """Cadeado como <img> com SVG em data URI (o st.html do Streamlit remove <svg> embutido na página)."""
    if aberto:
        corpo = (f'<rect x="3" y="7" width="10" height="7" rx="1.5" fill="none" stroke="{cor}" stroke-width="1.5"/>'
                 f'<path d="M5 7V5a3 3 0 0 1 5.6-1.5" fill="none" stroke="{cor}" stroke-width="1.6"/>')
    else:
        corpo = (f'<rect x="3" y="7" width="10" height="7" rx="1.5" fill="{cor}"/>'
                 f'<path d="M5 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="{cor}" stroke-width="1.6"/>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="14" height="14">{corpo}</svg>'
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img class="rp-cad" src="{uri}" width="14" height="14" alt="{rotulo}" title="{rotulo}">'


_CADEADO_FECHADO = _cadeado("#E24B4A", False, "Crédito bloqueado")
_CADEADO_ABERTO = _cadeado("#22c55e", True, "Crédito liberado")


def _credito_por_cliente() -> dict:
    """Situação de crédito de cada cliente (a mesma do card Situação Documental: a do grupo dele no Grupo de Crédito):
    {código do agente: True se bloqueado, False se liberado}. Cliente sem situação conhecida fica de fora (sem cadeado)."""
    try:
        geral, agentes = carregar_grupo_credito_geral(), carregar_grupo_credito_saldo_agente()
        if geral is None or agentes is None or geral.empty or agentes.empty:
            return {}
        sit = {g: str(v or "").upper() for g, v in zip(geral["GRUPO_CODIGO"], geral["SITUACAO_CLIENTE"])}
        saida = {}
        for grupo, agente in zip(agentes["COD_GRUPO"], agentes["COD_AGENTE"]):
            t = sit.get(grupo, "")
            if any(x in t for x in ("BLOQ", "INADIMPL", "SUSPENS")):
                saida[str(int(float(agente)))] = True
            elif any(x in t for x in ("ATIVO", "OK", "LIBERADO", "NORMAL")):
                saida[str(int(float(agente)))] = False
        return saida
    except Exception:
        return {}


def _para_desbloquear(notas) -> pd.DataFrame | None:
    """Clientes para analisar o desbloqueio: o grupo dele está bloqueado no Grupo de Crédito (bloqueado, cadastro bloqueado,
    inadimplente ou suspenso), ele tem controle de venda ABERTO e NENHUM cliente do grupo tem pendência em documento que bloqueia
    ou em validação (esses ficam no quadro de notas). Colunas: COD, NOME, SITUACAO, CONTROLES (lista de (controle, NF)), ordenado
    por mais controles abertos. None se faltar alguma consulta."""
    try:
        geral, agentes = carregar_grupo_credito_geral(), carregar_grupo_credito_saldo_agente()
        ctrl = carregar_controles_abertos_mi()
        if geral is None or agentes is None or ctrl is None:
            return None
        sit = {g: str(v or "").strip() for g, v in zip(geral["GRUPO_CODIGO"], geral["SITUACAO_CLIENTE"])}
        if "PAIS" in agentes.columns:                                   # a gestão documental só existe no Mercado Interno
            agentes = agentes[agentes["PAIS"].astype(str).str.upper() == "BRA"]
        grupo_de = {str(int(float(c))): g for c, g in zip(agentes["COD_AGENTE"], agentes["COD_GRUPO"])}
        grupos_com_nota = {grupo_de[str(int(float(c)))] for c in notas["COD_CLIENTE"] if str(int(float(c))) in grupo_de} if not notas.empty else set()
        por_cliente = {}
        for c, controle, nf in zip(ctrl["COD_CLIENTE"], ctrl["CONTROLE"], ctrl["NF"]):
            por_cliente.setdefault(str(int(float(c))), []).append((str(controle), "" if pd.isna(nf) else str(nf)))
        linhas = []
        for cod, nome in zip(agentes["COD_AGENTE"], agentes["NOME_AGENTE"]):
            cod = str(int(float(cod)))
            grupo = grupo_de.get(cod)
            t = sit.get(grupo, "")
            if not any(x in t.upper() for x in ("BLOQ", "INADIMPL", "SUSPENS")) or grupo in grupos_com_nota or cod not in por_cliente:
                continue
            linhas.append({"COD": cod, "NOME": str(nome), "SITUACAO": t, "CONTROLES": sorted(por_cliente[cod], key=lambda x: x[1], reverse=True)})
        out = pd.DataFrame(linhas, columns=["COD", "NOME", "SITUACAO", "CONTROLES"]).drop_duplicates("COD")
        if out.empty:
            return out
        out["_n"] = out["CONTROLES"].map(len)
        return out.sort_values(["_n", "NOME"], ascending=[False, True]).drop(columns="_n").reset_index(drop=True)
    except Exception:
        return None


def _html_para_desbloquear(df) -> str:
    cabeca = ('<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
              '<span style="color:#e0e0e0;font-size:14px;font-weight:600">Para desbloquear · bloqueados no crédito, sem pendência documental</span>'
              f'<span style="font-size:11px;color:#8892a4">{0 if df is None else len(df)} cliente(s) · com controle de venda aberto</span></div>')
    if df is None:
        return f'<div class="rp-lista">{cabeca}<span style="color:#8892a4;font-size:13px">Não foi possível consultar agora.</span></div>'
    if df.empty:
        return f'<div class="rp-lista">{cabeca}<span style="color:#8892a4;font-size:13px">Nenhum cliente nesta situação.</span></div>'
    grade = "grid-template-columns:22px minmax(0,1.6fr) 80px minmax(0,1.4fr) 140px 70px"
    topo = (f'<div class="rp-q rp-qh" style="{grade}"><span></span><span style="text-align:left">Cliente</span><span class="rp-pz" style="text-align:left">Código</span>'
            '<span style="text-align:left">Controles abertos (NF)</span><span style="text-align:left">Situação do crédito</span><span class="rp-pz">Controles</span></div>')
    linhas = ""
    for r in df.itertuples(index=False):
        links = ""
        for controle, nf in r.CONTROLES[:3]:
            url = url_controle_venda(controle)
            rot = escape(f"NF {nf}" if nf else controle)
            links += (f'<a href="{url}" target="_blank" rel="noopener noreferrer" title="{escape(controle, quote=True)}" '
                      f'style="color:#fff;font-weight:600;text-decoration:none;margin-right:10px">{rot}</a>') if url else f'<span style="margin-right:10px">{rot}</span>'
        if len(r.CONTROLES) > 3:
            links += f'<span style="color:#8892a4">+{len(r.CONTROLES) - 3}</span>'
        linhas += (f'<div class="rp-q rp-qr" style="{grade}"><span class="rp-cadc">{_CADEADO_FECHADO}</span>'
                   f'<span class="rp-cli" title="{escape(r.NOME, quote=True)}">{escape(r.NOME)}</span>'
                   f'<span class="rp-pz" style="text-align:left">{escape(r.COD)}</span><span style="white-space:nowrap;overflow:hidden">{links}</span>'
                   f'<span style="color:#f3a3a2;font-size:12px">{escape(r.SITUACAO.capitalize())}</span><span class="rp-pz">{len(r.CONTROLES)}</span></div>')
    rodape = ('<div style="font-size:11px;color:#8892a4;margin-top:10px;line-height:1.6">Sai da lista quando o grupo for liberado no Grupo de Crédito, '
              'quando o controle fechar ou quando surgir pendência em documento que bloqueia (aí vai para o quadro de notas). Clique na NF para '
              'abrir o controle de venda no SyncProcess. Lista de análise: o bloqueio pode ser de crédito (limite, inadimplência), não só documental.</div>')
    return (f'<div class="rp-lista" style="border-top-color:#F59E0B">{cabeca}{topo}<div style="max-height:320px;overflow-y:auto;'
            f'scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div>{rodape}</div>')


def _grafico_notas(notas, filtro: str) -> str:
    """Quadro das notas pendentes: uma linha por nota e uma coluna por documento que bloqueia (vermelho = vencido, azul = validando,
    âmbar = não anexado, verde = OK, traço = a regra não vale para a nota). Aparece só a coluna do documento que tem alguma nota."""
    nomes = _nomes_clientes()
    credito = _credito_por_cliente()
    d = notas if filtro == "Todas" else notas[notas["TIPO"] == ("BLOQUEANTE" if filtro == "Bloqueantes" else "MANUAL")]
    cabeca = ('<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
              '<span style="color:#e0e0e0;font-size:14px;font-weight:600">Notas pendentes de validação · todos os clientes</span>'
              f'<span style="font-size:11px;color:#8892a4">{len(d)} nota(s) · só documentos que bloqueiam</span></div>')
    if d.empty:
        return f'<div class="rp-lista">{cabeca}<span style="color:#8892a4;font-size:13px">Nenhuma nota neste filtro.</span></div>'
    cols = colunas_documentos(d)
    grade = f"grid-template-columns:70px 22px minmax(0,1.25fr) repeat({len(cols)},minmax(0,1fr)) 92px"
    topo = (f'<div class="rp-q rp-qh" style="{grade}"><span style="text-align:left">NF</span><span class="rp-cadc"></span><span class="rp-cli" style="text-align:left">Cliente</span>'
            + "".join(f'<span title="{escape(nome, quote=True)}">{escape(nome)}</span>' for _, nome, _ in cols)
            + '<span class="rp-pz">Prazo</span></div>')
    linhas = ""
    for r in d.itertuples(index=False):
        cli = nomes.get(str(int(float(r.COD_CLIENTE))), f"Cliente {r.COD_CLIENTE}")
        prazo = r.PRAZO.strftime("%d/%m/%Y") if pd.notna(r.PRAZO) else "—"
        bloqueado = credito.get(str(int(float(r.COD_CLIENTE))))
        cad = "" if bloqueado is None else (_CADEADO_FECHADO if bloqueado else _CADEADO_ABERTO)
        url = url_controle_venda(r.CONTROLE)
        dica = escape(f"{cli} · {r.CONTROLE}", quote=True)
        nf = (f'<a href="{url}" target="_blank" rel="noopener noreferrer" title="{dica}">NF {escape(r.NF)}</a>' if url
              else f'<span style="color:#fff;font-weight:600" title="{dica}">NF {escape(r.NF)}</span>')
        celulas = ""
        for c, nome, _ in cols:
            e_ = r.ESTADOS.get(c)
            if e_ is None:
                celulas += f'<div class="rp-c rp-c-ND" title="{escape(nome, quote=True)}: não se aplica">—</div>'
            else:
                celulas += f'<div class="rp-c rp-c-{e_}" title="{escape(nome, quote=True)}">{ESTADO_ROTULO[e_]}</div>'
        linhas += (f'<div class="rp-q rp-qr" style="{grade}">{nf}<span class="rp-cadc">{cad}</span><span class="rp-cli" title="{escape(cli, quote=True)}">{escape(cli)}</span>'
                   f'{celulas}<span class="rp-pz">{prazo}</span></div>')
    legenda = ('<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:#8892a4;margin-top:10px">'
               '<span><span style="color:#E24B4A">●</span> inválido (prazo vencido, bloqueia)</span><span><span style="color:#378ADD">●</span> em validação</span>'
               '<span><span style="color:#9ca3af">●</span> pendente (sem documento)</span><span><span style="color:#22c55e">●</span> válido</span>'
               '<span>— a regra não vale para a nota</span><span>' + _CADEADO_FECHADO + ' crédito bloqueado · ' + _CADEADO_ABERTO + ' crédito liberado</span><span>clique na NF para abrir o controle de venda no SyncProcess</span></div>')
    return (f'<div class="rp-lista">{cabeca}{topo}<div style="max-height:420px;overflow-y:auto;scrollbar-width:thin;'
            f'scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div>{legenda}</div>')


def render(df_cr: pd.DataFrame) -> None:
    c_tit, c_at = st.columns([8, 1], vertical_alignment="center")
    with c_tit:
        st.title("Resumo Pendências")
        st.caption("Mercado Interno · quantidades (só o Esperado e Recebido mostra valores em R$) · atualiza a cada 5 minutos")
    with c_at:
        if st.button("🔄 Atualizar", key="rp_atualizar", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Montando o resumo..."):
        notas = notas_pendentes_todas()
        cards = [_card_descontos(df_cr), _card_boletos(df_cr), _card_notas(notas), _card_esperado_recebido(df_cr)]
    st.html(_CSS + '<div class="rp-grade">' + "".join(cards) + "</div>")

    if notas is None:
        st.info("Não foi possível consultar as notas pendentes de validação agora.")
        return
    filtro = st.segmented_control("Notas", ["Todas", "Bloqueantes", "Validação manual"], default="Todas",
                                  key="rp_filtro", label_visibility="collapsed") or "Todas"
    st.html(_CSS + _grafico_notas(notas, filtro))
    st.html(_CSS + _html_para_desbloquear(_para_desbloquear(notas)))     # card fixo abaixo do quadro, sem botão
