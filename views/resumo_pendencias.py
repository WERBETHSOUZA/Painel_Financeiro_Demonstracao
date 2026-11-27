"""
views/resumo_pendencias.py
==========================
Painel "Resumo Pendências": acompanhamento por QUANTIDADE (só o cartão Esperado e Recebido mostra também valores em reais) das pendências em aberto:
  - Descontos Contratuais Pendentes (mesma regra do card do Contas a Receber MI);
  - Boletos a Gerar (mesma regra do relatório; pronto para gerar x bloqueado por desconto);
  - Notas Pendentes de Validação (bloqueantes e validação manual, de todos os clientes do Mercado Interno);
  - Esperado e Recebido no banco DO DIA, em quantidade de títulos;
e, embaixo, o gráfico das notas pendentes de validação (uma barra por nota; o NF abre o controle de venda no SyncProcess).
Só aparece no menu de quem está no grupo fixo "Resumo Pendências" (tela Acessos).
"""

import base64
import calendar
import datetime
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from html import escape

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from utils.exporters import exportar_excel_abas_recebimentos

from services.data_service import (carregar_controles_abertos_mi, carregar_grupo_credito_geral, carregar_grupo_credito_saldo_agente,
                                   carregar_lista_clientes, carregar_notas_pendentes_validacao, carregar_recebido_periodo_mi,
                                   carregar_pedidos_em_validacao, carregar_recebimento_hoje_mi, carregar_tratativas_pendentes)
from utils.pendencias import _GRAVIDADE, ESTADO_ROTULO, rotulo_estado, _ha_dias, _quando, colunas_documentos, dica_documento, notas_pendentes_todas, url_busca_controles, url_controle_venda
from views.contas_receber import formatar_moeda
from views.relatorio_boleto_nao_gerado import _status_boleto
from views.relatorio_desconto_financeiro_pendente import resumo_descontos_pendentes

_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_AMARELO, _AZUL, _VERMELHO, _VERDE, _CINZA = "#F59E0B", "#378ADD", "#E24B4A", "#22c55e", "#6b7280"

_CSS = """<style>
.rp-grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:4px 0 14px}
.rp-t{font-size:1.05rem;font-weight:600;color:#fafafa;margin:0 0 8px 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-card{background:#1e1e2e;border-radius:12px;border-top:4px solid;box-sizing:border-box;padding:9px 16px;height:212px;
 display:flex;flex-direction:column;overflow:hidden}
.rp-top{display:flex;align-items:baseline;gap:8px;white-space:nowrap;overflow:hidden}
.rp-top b{font-size:40px;line-height:1}.rp-top .rp-un{font-size:14px;font-weight:700;color:#fff}
.rp-ds{font-size:12px;color:#8892a4;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-ln{height:1px;background:#2a2a3a;margin:5px 0}
.rp-nm{font-size:19px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-sb{font-size:13px;margin-top:2px}
.rpk-janela{height:50px;overflow:hidden;position:relative}.rpk-fade .rpk-item{position:absolute;inset:0}
.rpk-item{height:50px;display:flex;flex-direction:column;justify-content:center}
.rpk-nome{font-size:17px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rpk-sub{font-size:13px}
.rpk-ponto{width:6px;height:6px;border-radius:50%;background:#4b5563;display:inline-block;margin:0 2px}
@media (prefers-reduced-motion:reduce){.rp-card [class*=rpk],.rp-card [class$=l],.rpk-ponto{animation:none !important}.rpk-fade .rpk-item{opacity:1 !important}.rpk-fade .rpk-item:not(:first-child){display:none !important}}
.rp-mt{font-size:11px;color:#8892a4}
.rp-vl{font-size:15px;font-weight:700;color:#fff}
.rp-barra{height:8px;border-radius:4px;background:rgba(128,128,128,0.18);overflow:hidden;margin:6px 0 4px}
.rp-barra div{height:100%}
.rp-lista{background:#1e1e2e;border-radius:12px;border-top:4px solid #E24B4A;padding:10px 18px}
.rp-q{display:grid;gap:8px;align-items:center;font-size:16px}
.rp-qh{font-size:12.5px;color:#8892a4;text-align:center;line-height:1.15;padding-bottom:6px;border-bottom:1px solid #2a2a3a;align-items:end}
.rp-q a{color:#fff;font-weight:600;text-decoration:none;white-space:nowrap}.rp-q a:hover{text-decoration:underline;color:#6db3f5}
.rp-cad{vertical-align:-2px}.rp-cadc{display:flex;align-items:center;justify-content:center}
.rp-ua{font-size:14.5px;text-align:center;line-height:1.4;color:#d1d5db;white-space:nowrap;font-weight:500}
.rp-tag{display:inline-block;margin-top:2px;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600;background:rgba(245,158,11,.22);color:#f5c070}
.rp-cli{color:#aab2c5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-c{height:29px;border-radius:5px;font-size:13.5px;display:flex;align-items:center;justify-content:center;font-weight:600}
@keyframes rp-pisca{0%,100%{opacity:1}50%{opacity:.3}}@keyframes rp-contorno{0%,100%{box-shadow:inset 0 0 0 1.5px #E24B4A}50%{box-shadow:inset 0 0 0 1.5px rgba(226,75,74,0)}}@keyframes rp-anel{0%{box-shadow:0 0 0 0 rgba(226,75,74,.7)}70%,100%{box-shadow:0 0 0 8px rgba(226,75,74,0)}}.rp-cad-blq{border-radius:50%;animation:rp-anel 1.4s ease-out infinite}.rp-c-INVALIDO{background:rgba(226,75,74,.28);color:#f3a3a2}.rp-c-blq{box-shadow:inset 0 0 0 1.5px #E24B4A;animation:rp-contorno 1.2s ease-in-out infinite}.rp-c-VALIDANDO{background:rgba(55,138,221,.25);color:#8ec2f5}
.rp-c-NAO_ANEXADO,.rp-c-PENDENTE{background:rgba(156,163,175,.22);color:#d1d5db}
.rp-c-OK{background:rgba(34,197,94,.16);color:#6fd69a}.rp-c-ND{color:#6b7280;font-weight:400}
.rp-qr .rp-pz{font-size:14px}.rp-qr{padding:4px 0;border-bottom:1px solid #26263a}.rp-pz{text-align:right;color:#8892a4;white-space:nowrap}
</style>"""


_CSS_RQ = ('<style>.rp-rq{display:grid;gap:8px;align-items:center;font-size:14px}.rp-rcl{color:#aab2c5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
           '.rp-rq a{color:#fff;font-weight:600;text-decoration:none}.rp-rq a:hover{text-decoration:underline;color:#6db3f5}</style>')   # linhas de tabela dos dois cards lado a lado


_ALT, _SEG = 56, 4   # altura de um cliente no ticker (px) e segundos por cliente


def _ticker(chave: str, itens: list, cor: str) -> str:
    """Passa de cliente em cliente sozinho (nome e subtexto; pausa com o mouse em cima), só com CSS. `itens` = [(nome, subtexto,
    cor do subtexto ou None)]. Com um cliente só, não anima."""
    def linha(i, cls=""):
        return (f'<div class="rpk-item{cls}" title="{escape(i[0], quote=True)}"><span class="rpk-nome">{escape(i[0])}</span>'
                f'<span class="rpk-sub" style="color:{i[2] or cor}">{i[1]}</span></div>')
    if len(itens) == 1:
        return f'<div class="rpk-janela">{linha(itens[0])}</div>'
    n = len(itens)
    fatia = 100 / n                       # parte do ciclo em que cada cliente fica na tela
    fade = fatia * 0.12                   # um nome some por completo antes de o próximo aparecer (sem os dois sobrepostos)
    ef = "S" if st.session_state.get("_rp_entradas", 0) % 2 else "F"   # todos os cartões iguais; troca de efeito a cada entrada no painel
    ini = "opacity:0;transform:translateY(14px)" if ef == "S" else "opacity:0"
    fim = "opacity:0;transform:translateY(-14px)" if ef == "S" else "opacity:0"
    nome = f"{chave}{ef}"
    quadros = (f"@keyframes {nome}{{0%{{{ini}}}{fade:.3f}%,{fatia - fade:.3f}%{{opacity:1;transform:none}}{fatia:.3f}%,100%{{{fim}}}}}"
               f".{nome}{{animation:{nome} {_SEG * n}s linear infinite}}")
    classes = [nome] * n
    atrasos = "".join(f".{chave}d{k}{{animation-delay:{k * _SEG}s}}" for k in range(n))
    return (f"<style>{quadros}{atrasos}.rp-card:hover .rpk-fade .rpk-item{{animation-play-state:paused}}.rpk-fade .rpk-item{{opacity:0}}</style>"
            f'<div class="rpk-janela rpk-fade">'
            + "".join(linha(it, f" {classes[k]} {chave}d{k}") for k, it in enumerate(itens)) + "</div>")


def _card(titulo: str, rotulo: str, numero, unidade: str, cor: str, destaque: str, sub: str, rodape: str,
          itens: list = None, chave: str = "rpk") -> str:
    """Cartão no padrão do Descontos Contratuais Pendentes: rótulo e quantidade em cima, cliente(s) no meio (com `itens`, passa de
    um em um sozinho), rodapé fixo."""
    meio = (_ticker(chave, itens, cor) if itens
            else f'<div class="rp-nm">{destaque}</div><div class="rp-sb" style="color:{cor}">{sub}</div>')
    return (f'<div><div class="rp-t" title="{escape(titulo)}">{escape(titulo)}</div>'
            f'<div class="rp-card" style="border-color:{cor}"><div class="rp-top"><b style="color:{cor}">{numero}</b>'
            f'<span class="rp-un">{escape(unidade)}</span></div><div class="rp-ds">{escape(rotulo)}</div><div class="rp-ln"></div>'
            f'{meio}'
            f'<div style="flex:1"></div><div class="rp-ln"></div><div class="rp-mt">{rodape}</div></div></div>')


def _indisponivel(titulo: str) -> str:
    return _card(titulo, "Indisponível", "—", "", _CINZA, "—", "&nbsp;", "não foi possível consultar agora")


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


def _nomes_cheios(nomes: list) -> list:
    """Nome completo do cliente para o ticker, em minúsculas com a inicial maiúscula ("ACME COMERCIO DE FRUTAS LTDA" -> "Acme Comercio De Frutas Ltda");
    o que não couber na largura do card termina em reticências (o nome inteiro aparece ao passar o mouse)."""
    ligacao = {"de", "da", "do", "das", "dos", "e"}
    def palavra(p: str) -> str:
        if p.lower() in ligacao:
            return p.lower()
        return p.upper() if len(p) <= 2 else p.capitalize()
    return [" ".join(palavra(p) for p in str(n).replace(",", " ").split()) or "-" for n in nomes]


def _card_descontos(df_cr: pd.DataFrame) -> str:
    titulo = "Descontos Contratuais Pendentes"
    desc = resumo_descontos_pendentes(df_cr)
    st.session_state["_rp_xls_desc"] = bool(desc and desc["pendentes"])      # o atalho de Excel do card só aparece quando há o que baixar
    if desc is None:
        return _indisponivel(titulo)
    pend, erros = desc["pendentes"], desc["erros"]
    cor = "#ef4444" if erros else _AMARELO if pend else _VERDE
    if not pend:
        return _card(titulo, "Pendentes de desconto", 0, "título(s)", cor, "Tudo aplicado", "&nbsp;", "nenhum desconto a lançar")
    clientes = desc["por_cliente"][:10]
    itens = [(c, f"{q:02d} {_plural(q, 'título', 'títulos')}", None) for c, q in zip(_nomes_cheios([x[0] for x in clientes]), [x[1] for x in clientes])]
    rodape = f'{desc["clientes"]} cliente(s)' + (f' · <span style="color:#ef4444">{erros} com erro</span>' if erros else "")
    return _card(titulo, "Pendentes de desconto", pend, "título(s)", cor, "", "", rodape, itens=itens, chave="rpkd")


def _card_boletos(df_cr: pd.DataFrame) -> str:
    titulo = "Boletos a Gerar"
    st.session_state["_rp_xls_bol"] = False
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
    st.session_state["_rp_xls_bol"] = True
    top = livres.groupby("CLIENTE").size().sort_values(ascending=False).head(10)
    itens = [(c, f"{int(q):02d} {_plural(int(q), 'título', 'títulos')}", None) for c, q in zip(_nomes_cheios([str(i) for i in top.index]), top.values)]
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
        return _card(titulo, "Pendentes de validação", 0, "nota(s)", _VERDE, "Nenhuma pendência", "&nbsp;", "todas as notas validadas")
    notas = notas[~notas["TIPO"].isin(["A_VENCER", "PEDIDO"])]      # o card conta só bloqueante e validação manual de NOTAS; a vencer e pedidos ficam no quadro
    if notas.empty:
        return _card(titulo, "Pendentes de validação", 0, "nota(s)", _VERDE, "Nenhuma pendência", "&nbsp;", "todas as notas validadas")
    bloq = notas[notas["TIPO"] == "BLOQUEANTE"]
    man = len(notas) - len(bloq)
    clientes = notas["COD_CLIENTE"].nunique()
    cor = _VERMELHO if len(bloq) else _AZUL
    por = (notas.assign(B=(notas["TIPO"] == "BLOQUEANTE").astype(int), M=(notas["TIPO"] != "BLOQUEANTE").astype(int))
           .groupby("COD_CLIENTE")[["B", "M"]].sum().sort_values(["B", "M"], ascending=False).head(10))
    nomes = _nomes_clientes()
    cheios = [nomes.get(str(int(float(c))), f"Cliente {c}") for c in por.index]
    itens = []
    for curto, (nb, nm) in zip(_nomes_cheios(cheios), por[["B", "M"]].itertuples(index=False)):
        if nb:
            sub = f"{nb} {_plural(nb, 'bloqueante', 'bloqueantes')}" + (f" · {nm} manual" if nm else "")
            itens.append((curto, sub, _VERMELHO))
        else:
            itens.append((curto, f"{nm} em validação manual", _AZUL))
    return _card(titulo, "Pendentes de validação", len(notas), "nota(s)", cor, "", "",
                 f"{len(bloq)} bloqueante(s) · {man} manual(is) · {clientes} cliente(s)", itens=itens, chave="rpkn")


def _card_esperado_recebido(df_cr: pd.DataFrame, ocultar: bool = False) -> str:
    """Quantidade de títulos DO DIA: recebido = baixas que entraram no banco hoje (mesma regra do Resumo do Contas a Receber MI,
    pela data da baixa); esperado = recebido + parcelas que ainda estão em aberto para o crédito de hoje (vencimento + 1 dia
    útil, a mesma conta do bloco "Hoje" do Contas a Receber MI). Fim de semana: sem parcela esperada, só o que entrar."""
    titulo = "Esperado e Recebido no banco"
    hoje = datetime.date.today()
    try:
        # só o dia de hoje (consulta de 1 dia, ~0,1 s): trazer o ano inteiro só para pegar o dia levava ~4 s e dá o mesmo resultado
        d = carregar_recebido_periodo_mi(hoje, hoje)
        if d is None or d.empty:
            d = pd.DataFrame(columns=["DOC", "AGN", "PARC", "VALOR_PAGO"])
        recebido = d[["DOC", "AGN", "PARC"]].drop_duplicates().shape[0]
        info = carregar_recebimento_hoje_mi() or {}
        faltam = int(info.get("abertas", 0) or 0)
        valor_rec = float(pd.to_numeric(d["VALOR_PAGO"], errors="coerce").sum())
        valor_esp = valor_rec + max(float(info.get("aberto", 0) or 0), 0.0)
    except Exception:
        return _indisponivel(titulo)
    esperado = recebido + faltam
    moeda = (lambda v: "R$ ••••••") if ocultar else formatar_moeda        # Ocultar esconde só os valores em R$ (títulos e % continuam)
    pct = min(recebido / esperado * 100, 100.0) if esperado else 0.0
    pct_txt = f"{pct:.2f}".replace(".", ",")
    rodape = f"faltam {faltam} título(s) · {moeda(max(valor_esp - valor_rec, 0.0))} · só entrada no banco" if info else "sem crédito previsto hoje · só entrada no banco"
    return (f'<div><div class="rp-t" title="{titulo}">{titulo}</div><div class="rp-card" style="border-color:{_VERDE}">'
            f'<div class="rp-top"><b style="color:{_VERDE}">{pct_txt}%</b><span class="rp-un">recebido</span></div><div class="rp-ds">do esperado hoje · {hoje:%d/%m/%Y}</div><div class="rp-ln"></div>'
            f'<div class="rp-mt">Esperado · {esperado} título(s)</div><div class="rp-vl">{moeda(valor_esp)}</div>'
            f'<div class="rp-barra"><div style="width:{pct:.1f}%;background:{_VERDE}"></div></div>'
            f'<div class="rp-mt">Recebido no banco · {recebido} título(s)</div><div class="rp-vl" style="color:{_VERDE}">{moeda(valor_rec)}</div>'
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
    return f'<img class="rp-cad{"" if aberto else " rp-cad-blq"}" src="{uri}" width="14" height="14" alt="{rotulo}" title="{rotulo}">'


def _sirene(cor: str = "#E24B4A", tam: int = 34) -> str:
    """Sirene de alerta (só contorno, no mesmo traço do cadeado) como <img> com SVG em data URI (o st.html remove <svg> embutido)."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="{tam}" height="{tam}" fill="none" stroke="{cor}" stroke-linecap="round" '
           f'stroke-linejoin="round"><rect x="2.5" y="11.5" width="11" height="2.5" rx="1" stroke-width="1.4"/><path d="M4.5 11.5V8a3.5 3.5 0 0 1 7 0v3.5" '
           f'stroke-width="1.5"/><path d="M8 1v2M2.6 3.2l1.3 1.3M13.4 3.2l-1.3 1.3" stroke-width="1.4"/></svg>')
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img src="{uri}" width="{tam}" height="{tam}" alt="Alerta" style="display:block">'


_SIRENE = _sirene(tam=26)


def _relogio_alerta(cor: str = "#f5c070") -> str:
    """Relógio com ponto de exclamação (anexo depois do prazo), como <img> com SVG em data URI (o st.html remove <svg> embutido)."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="{cor}" '
           f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.99 12.34A9 9 0 1 0 12.4 20.97"/>'
           f'<path d="M12 7v5l2 2"/><path d="M19 16v3"/><path d="M19 22v.01"/></svg>')
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img src="{uri}" width="15" height="15" alt="" style="vertical-align:-3px;margin-right:5px">'


_RELOGIO_ALERTA = _relogio_alerta()
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


def _norm(txt) -> str:
    """Texto para pesquisa: sem acento, sem maiúscula, sem espaço sobrando."""
    return "".join(c for c in unicodedata.normalize("NFKD", str(txt or "")) if not unicodedata.combining(c)).casefold().strip()


def _estado_pedido(status, doc_status, motivo) -> str:
    """Estado do aceite do pedido / pedido de compra: Inválido (documento recusado), Em validação ou Pendente (sem documento)."""
    ds = pd.to_numeric(doc_status, errors="coerce")
    if pd.notna(ds):
        return {0: "VALIDANDO", 1: "OK", 2: "INVALIDO"}.get(int(ds), "VALIDANDO")
    if "invalid" in _norm(motivo):
        return "INVALIDO"
    st_ = pd.to_numeric(status, errors="coerce")
    return "VALIDANDO" if pd.notna(st_) and int(st_) == 1 else "NAO_ANEXADO"


def _pedidos_em_validacao():
    """Pedidos ainda sem nota com o pedido de compra do cliente anexado e em validação (pedido sem anexo não entra), no mesmo formato das notas (uma
    linha por pedido, TIPO = "PEDIDO", ROTULO = "PV 21834"). Os mais antigos primeiro. None se o banco não respondeu."""
    df = carregar_pedidos_em_validacao()
    if df is None:
        return None
    cols = ["COD_CLIENTE", "NF", "CONTROLE", "TIPO", "QTD_DOCS", "PRAZO", "DOCUMENTOS", "ESTADOS", "NOMES", "BLOQUEANDO", "ANEXADOS", "VALIDADOS",
            "APOS_PRAZO", "ULTIMO_ANEXO", "EMISSAO", "ROTULO", "GERADA"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    linhas = []
    for (cod, controle, pedido), g in df.groupby(["COD_CLIENTE", "CONTROLE", "PEDIDO"], dropna=False):
        estados, nomes = {}, {}
        for c, nome, st_, ds, mot in zip(g["DOC_CODIGO"], g["DOCUMENTO"], g["STATUS"], g["DOC_STATUS"], g["MOTIVO"]):
            c, e = str(c), _estado_pedido(st_, ds, mot)
            nomes[c] = str(nome)
            if _GRAVIDADE[e] >= _GRAVIDADE.get(estados.get(c), -1):
                estados[c] = e
        if "INVALIDO" in estados.values():      # pedido inválido é cancelado (não gera venda); o cliente precisa emitir outro, então não é pendência
            continue
        if all(e == "NAO_ANEXADO" for e in estados.values()):   # nada anexado ainda: não há o que validar, então não é validação manual
            continue
        linhas.append({"COD_CLIENTE": cod, "NF": "", "CONTROLE": str(controle), "TIPO": "PEDIDO", "QTD_DOCS": len(estados), "PRAZO": pd.NaT,
                       "DOCUMENTOS": list(nomes.values()), "ESTADOS": estados, "NOMES": nomes, "BLOQUEANDO": {}, "ANEXADOS": {}, "VALIDADOS": {},
                       "APOS_PRAZO": {}, "ULTIMO_ANEXO": pd.NaT, "EMISSAO": pd.NaT, "ROTULO": f"PV {int(pedido)}" if pd.notna(pedido) else "PV",
                       "GERADA": pd.to_datetime(g["GERADA"], errors="coerce").min()})
    return pd.DataFrame(linhas, columns=cols).sort_values("GERADA", na_position="last").reset_index(drop=True)


def _filtrar_busca(d: pd.DataFrame, busca: str, nomes: dict) -> pd.DataFrame:
    """Pesquisa por cliente (nome ou código), nota, pedido ou controle: todas as palavras digitadas precisam aparecer."""
    termos = [t for t in _norm(busca).split() if t]
    if not termos or d.empty:
        return d
    palheiro = [_norm(f"{nomes.get(str(int(float(c))), '')} {int(float(c))} {rot} {nf} {ctrl}")
                for c, rot, nf, ctrl in zip(d["COD_CLIENTE"], d["ROTULO"], d["NF"], d["CONTROLE"])]
    return d[[all(t in p for t in termos) for p in palheiro]]


def _para_desbloquear(notas) -> pd.DataFrame | None:
    """Clientes para analisar o desbloqueio: o grupo dele está bloqueado no Grupo de Crédito (bloqueado, cadastro bloqueado,
    inadimplente ou suspenso), ele tem controle de venda ABERTO e NENHUM cliente do grupo tem pendência em documento que bloqueia
    ou em validação (esses ficam no quadro de notas). Colunas: COD, NOME, GRUPO (código do grupo de crédito), SITUACAO, CONTROLES (lista de (controle, NF)), ordenado
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
        com_pendencia = notas[~notas["TIPO"].isin(["A_VENCER", "PEDIDO"])]       # nota a vencer (só sem anexo) e pedido sem nota ainda não bloqueiam
        grupos_com_nota = {grupo_de[str(int(float(c)))] for c in com_pendencia["COD_CLIENTE"] if str(int(float(c))) in grupo_de} if not com_pendencia.empty else set()
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
            linhas.append({"COD": cod, "NOME": str(nome), "GRUPO": "" if grupo is None else str(grupo), "SITUACAO": t, "CONTROLES": sorted(por_cliente[cod], key=lambda x: x[1], reverse=True)})
        out = pd.DataFrame(linhas, columns=["COD", "NOME", "GRUPO", "SITUACAO", "CONTROLES"]).drop_duplicates("COD")
        if out.empty:
            return out
        out["_n"] = out["CONTROLES"].map(len)
        return out.sort_values(["_n", "NOME"], ascending=[False, True]).drop(columns="_n").reset_index(drop=True)
    except Exception:
        return None


def _html_para_desbloquear(df) -> str:
    cabeca = ('<div style="margin-bottom:8px"><div style="color:#e0e0e0;font-size:14px;font-weight:600">Para desbloquear sem pendências</div>'
              '<div style="font-size:11px;color:#8892a4;margin-top:2px">Bloqueados no crédito, sem pendência documental · '
              f'{0 if df is None else len(df)} cliente(s) com controle aberto</div></div>')
    if df is None:
        return f'<div class="rp-lista" style="border-top-color:#F59E0B;height:100%;box-sizing:border-box">{cabeca}<span style="color:#8892a4;font-size:13px">Não foi possível consultar agora.</span></div>'
    if df.empty:
        return f'<div class="rp-lista" style="border-top-color:#F59E0B;height:100%;box-sizing:border-box">{cabeca}<span style="color:#8892a4;font-size:13px">Nenhum cliente nesta situação.</span></div>'
    grade = "grid-template-columns:20px minmax(0,1fr) 54px 52px 82px 46px"
    topo = (f'<div class="rp-rq rp-qh" style="{grade}"><span></span><span style="text-align:left">Cliente</span><span class="rp-pz" style="text-align:left">Código</span>'
            '<span class="rp-pz" style="text-align:left">Grupo</span><span style="text-align:left">Crédito</span><span class="rp-pz">Ctrl.</span></div>')
    linhas = ""
    for r in df.itertuples(index=False):
        linhas += (f'<div class="rp-rq rp-qr" style="{grade}"><span class="rp-cadc">{_CADEADO_FECHADO}</span>'
                   f'<span class="rp-rcl" title="Abrir os controles de venda de {escape(r.NOME, quote=True)} no SyncProcess">'
                   f'<a href="{url_busca_controles(r.NOME)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none">{escape(r.NOME)}</a></span>'
                   f'<span class="rp-pz" style="text-align:left">{escape(r.COD)}</span><span class="rp-pz" style="text-align:left">{escape(r.GRUPO)}</span>'
                   f'<span style="color:#f3a3a2;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(r.SITUACAO.capitalize())}</span>'
                   f'<span class="rp-pz">{len(r.CONTROLES)}</span></div>')
    dica = ("Sai da lista quando o grupo for liberado no Grupo de Crédito, quando o controle fechar ou quando surgir pendência em documento que bloqueia "
            "(aí vai para o quadro de notas). Clique no nome do cliente para ver os controles dele no SyncProcess. Lista de análise: o bloqueio pode ser "
            "de crédito (limite, inadimplência), não só documental.")
    rodape = (f'<div title="{escape(dica, quote=True)}" style="font-size:11px;color:#8892a4;margin-top:8px;line-height:1.5">'
              'Sai da lista quando o grupo for liberado ou o controle fechar. Passe o mouse para ver a regra completa.</div>')
    return (f'<div class="rp-lista" style="border-top-color:#F59E0B;height:100%;box-sizing:border-box">{cabeca}<div style="overflow-x:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e"><div style="min-width:400px">{topo}'
            f'<div style="max-height:156px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div></div></div>{rodape}</div>')   # largura mínima + rolagem lateral em tela pequena


def _situacao_reclamacao(r, saldo_nf, hoje: pd.Timestamp):
    """Etapa em que a reclamação está (Reclamação > Qualidade > Tratativa e Execução > Aprovação). Devolve (ordem na tabela, texto, cor, detalhe). Situações: Qualidade pendente/recusada, Tratativa pendente, Aprovação pendente, Aprovada (desconto ou devolução a aplicar) e Concluída.
    Concluída = NF com saldo zerado, em qualquer etapa (não há mais desconto nem devolução pendente na NF, ex.: a devolução já foi lançada no Mega)."""
    def dias_desde(ts):
        return max((hoje - pd.Timestamp(ts).normalize()).days, 0)

    def ha(ts):
        n = dias_desde(ts)
        return "Hoje" if n == 0 else f"Há {n} {_plural(n, 'dia', 'dias')}"

    reg = f"registrada {pd.Timestamp(r.REGISTRO):%d/%m %H:%M}" if pd.notna(r.REGISTRO) else ""
    juntar = lambda *x: " · ".join(i for i in x if i)
    if pd.notna(r.PROCEDE) and int(r.PROCEDE) == 0:
        return 4, "Qualidade recusada", "#f3a3a2", juntar(reg.capitalize())
    if saldo_nf is not None and abs(saldo_nf) < 0.005:          # NF zerada = sem desconto nem devolução pendente: concluída, em qualquer etapa
        vinc = ("Devolução vinculada" if int(r.TIPO) == 3 else "Desconto vinculado") if pd.notna(r.TIPO) else "NF sem saldo em aberto"
        return 5, "Concluída", "#6fd69a", juntar(vinc, f"aprovada {pd.Timestamp(r.APROVADA):%d/%m %H:%M}" if pd.notna(r.APROVADA) else "", reg)
    if pd.isna(r.PROCEDE) or pd.isna(r.QUALIDADE_CONCLUIDA):
        return 2, "Qualidade pendente", "#f5c070", juntar(ha(r.REGISTRO) if pd.notna(r.REGISTRO) else "", reg)
    if pd.isna(r.TIPO):
        return 1, "Tratativa pendente", "#f5c070", juntar(ha(r.QUALIDADE_CONCLUIDA), reg)
    if pd.isna(r.APROVADA):
        dias = dias_desde(r.DEFINIDA) if pd.notna(r.DEFINIDA) else 0
        return 0, "Aprovação pendente", "#f3a3a2" if dias >= 7 else "#f5c070", juntar(ha(r.DEFINIDA) if pd.notna(r.DEFINIDA) else "", reg)
    a_incluir = "Devolução a aplicar" if int(r.TIPO) == 3 else "Desconto a aplicar"          # aprovada, e a NF ainda tem saldo: falta aplicar o desconto ou a devolução
    return 3, "Aprovada", "#f5c070", juntar(a_incluir, f"aprovada {pd.Timestamp(r.APROVADA):%d/%m %H:%M}", reg)


def _html_reclamacoes_pendentes(df, cliente: str | None, nomes: dict, df_cr: pd.DataFrame | None = None, sem_valores: bool = False) -> str:
    """Tabela das reclamações de clientes no SyncProcess, com a etapa em que cada uma está numa coluna só (Situação, em duas linhas: a etapa e a data).
    Ordem: aprovação pendente (a mais antiga na frente), tratativa a definir, qualidade pendente, aprovada falta aplicar, qualidade recusada e concluídas
    (da mais recente à mais antiga); 8 linhas à vista, o resto na barra de rolagem. Saldo em Aberto = o que ainda está em aberto da NF no Contas a Receber
    (zerado = baixada = Concluída, em qualquer etapa). Colunas de valor: Valor NF (total da venda), Desconto e Saldo em Aberto; sem_valores=True: sem elas. Sem dados ou sem banco: não aparece."""
    if df is None or df.empty:
        return ""
    d = df.copy()
    d["COD"] = d["COD_CLIENTE"].map(lambda c: str(int(float(c))) if pd.notna(c) else "")
    if cliente:
        d = d[d["COD"] == str(cliente)]
        if d.empty:
            return ""
    saldo = {}                                                   # saldo em aberto por (NF, cliente) no Contas a Receber; NF que não está lá = zerada
    if df_cr is not None and not df_cr.empty and {"NF", "COD_CLIENTE", "SALDO_EM_ABERTO"} <= set(df_cr.columns):
        base = df_cr.assign(_NF=df_cr["NF"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip(),
                            _CLI=pd.to_numeric(df_cr["COD_CLIENTE"], errors="coerce").astype("Int64").astype(str))
        saldo = base.groupby(["_NF", "_CLI"])["SALDO_EM_ABERTO"].sum().to_dict()
    hoje = pd.Timestamp.today().normalize()
    itens = []
    for r in d.itertuples(index=False):
        sd = float(saldo.get((str(r.NF or "").strip(), r.COD), 0) or 0) if df_cr is not None else None
        ordem, texto, cor, detalhe = _situacao_reclamacao(r, sd, hoje)
        if ordem == 5 and pd.isna(r.APROVADA) and pd.notna(r.REGISTRO) and (hoje - pd.Timestamp(r.REGISTRO).normalize()).days > 30:
            continue                                            # concluída sem tratativa (NF zerada) e registrada há mais de 30 dias: já não interessa
        chave = {0: pd.Timestamp(r.DEFINIDA) if pd.notna(r.DEFINIDA) else hoje,                      # aprovação pendente: a mais antiga na frente
                 1: pd.Timestamp(r.QUALIDADE_CONCLUIDA) if pd.notna(r.QUALIDADE_CONCLUIDA) else hoje,
                 2: pd.Timestamp(r.REGISTRO) if pd.notna(r.REGISTRO) else hoje}.get(ordem)
        if chave is None:                                        # demais: da mais recente à mais antiga
            ref = r.APROVADA if ordem in (3, 5) else r.REGISTRO
            chave = -pd.Timestamp(ref).value if pd.notna(ref) else 0
        else:
            chave = chave.value
        itens.append((ordem, chave, r, sd, texto, cor, detalhe))
    itens.sort(key=lambda x: (x[0], x[1]))
    grade = f"grid-template-columns:54px minmax(0,1fr) 76px {'' if sem_valores else '100px 96px 108px '}48px 190px"
    topo = (f'<div class="rp-rq rp-qh" style="{grade}"><span style="text-align:left">NF venda</span>'
            '<span style="text-align:left">Cliente</span><span style="text-align:left">Tratativa</span>' + ('' if sem_valores else '<span class="rp-pz" title="Valor total da venda (controle de venda no SyncProcess)">Valor NF</span><span class="rp-pz" title="Valor fiscal autorizado do desconto ou da devolução (só existe depois que a tratativa é definida)">Desconto</span>'
            '<span class="rp-pz" title="Saldo em aberto da NF no Contas a Receber (zerado = baixada)">Saldo em Aberto</span>') + '<span class="rp-pz">Aprov.</span><span style="text-align:left">Situação</span></div>')
    linhas, n_conc = "", 0
    for ordem, _, r, sd, texto, cor, detalhe in itens:
        n_conc += ordem == 5
        url = url_controle_venda(r.CONTROLE)            # a NF abre a aba Tratativa e Execução do controle de venda no SyncProcess
        nf = escape(str(r.NF or "—"))
        nf_html = (f'<a href="{url}?tab=tratativa-pane#tratativa-pane" target="_blank" rel="noopener noreferrer" '
                   f'title="Abrir Tratativa e Execução no SyncProcess">{nf}</a>' if url else nf)
        tipo = "Devolução" if pd.notna(r.TIPO) and int(r.TIPO) == 3 else ("Desconto" if pd.notna(r.TIPO) and int(r.TIPO) == 2 else "—")
        valor = formatar_moeda(float(r.VALOR)) if pd.notna(r.VALOR) else "—"
        _tot = getattr(r, "TOTAL_NF", None)
        total_nf = formatar_moeda(float(_tot)) if _tot is not None and pd.notna(_tot) else "—"
        nome = nomes.get(r.COD, f"Cliente {r.COD}")
        saldo_html = ("—" if sd is None else f'<span style="color:#6fd69a">{formatar_moeda(0)}</span>' if abs(sd) < 0.005
                      else f'<span style="color:#f5c070">{formatar_moeda(sd)}</span>')
        sit = (f'<span style="display:flex;flex-direction:column;line-height:1.25"><span style="color:{cor};font-size:13px">{texto}</span>'
               f'<span style="color:#8892a4;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{escape(detalhe, quote=True)}">{escape(detalhe)}</span></span>')
        linhas += (f'<div class="rp-rq rp-qr" style="{grade}"><span>{nf_html}</span>'
                   f'<span class="rp-rcl" title="{escape(nome, quote=True)}">{escape(nome)}</span><span style="color:#d1d5db;font-size:13px">{tipo}</span>'
                   + (f'' if sem_valores else f'<span class="rp-pz" style="color:#aab2c5">{total_nf}</span><span class="rp-pz">{valor}</span><span class="rp-pz">{saldo_html}</span>') + f'<span class="rp-pz">#{int(r.APROVACAO) if pd.notna(r.APROVACAO) else "—"}</span>'
                   f'{sit}</div>')
    cabeca = ('<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
              '<span style="color:#e0e0e0;font-size:14px;font-weight:600">Reclamações · andamento</span>'
              f'<span style="font-size:11px;color:#8892a4">{len(itens) - n_conc} em andamento · {n_conc} concluída(s) nos últimos 30 dias</span></div>')
    return _CSS_RQ + f'<div class="rp-lista" style="border-top-color:#378ADD;height:100%;box-sizing:border-box">{cabeca}<div style="overflow-x:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e"><div style="min-width:{550 if sem_valores else 900}px">{topo}<div style="max-height:352px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div></div></div></div>'   # 8 linhas à vista; largura mínima + rolagem lateral em tela pequena


def _prazo_colorido(ts, texto: str) -> str:
    """Prazo da nota com a cor do texto (sem fundo) pela distância de hoje: vermelho = vencido ou vence hoje, laranja = falta 1 dia, amarelo = 2 a 3 dias;
    4 dias ou mais fica só a data, sem destaque (o destaque começa com 3 dias). A segunda linha pequena traz a contagem (a cor não é a única pista)."""
    if pd.isna(ts):
        return texto
    d = (pd.Timestamp(ts).normalize() - pd.Timestamp.today().normalize()).days
    if d > 3:
        return texto
    cor, nota = (("#f3a3a2", f"vencido há {-d} {_plural(-d, 'dia', 'dias')}") if d < 0 else
                 ("#f3a3a2", "vence hoje") if d == 0 else
                 ("#f5b090", "falta 1 dia") if d == 1 else
                 ("#f2d25c", f"faltam {d} dias"))
    return (f'<span style="display:inline-flex;flex-direction:column;align-items:flex-end;line-height:1.15;'
            f'color:{cor};font-weight:600">{texto}<small style="font-size:10px;font-weight:400">{nota}</small></span>')


def _grafico_notas(notas, filtro: str, cliente: str | None = None) -> str:
    """Quadro das notas pendentes: uma linha por nota e uma coluna por documento que bloqueia (vermelho = vencido, azul = validando,
    âmbar = não anexado, verde = OK, traço = a regra não vale para a nota). Aparece só a coluna do documento que tem alguma nota."""
    nomes = _nomes_clientes()
    credito = _credito_por_cliente()
    tipos = {"Bloqueantes": ["BLOQUEANTE"], "Validação manual": ["MANUAL", "PEDIDO"], "A vencer (sem anexo)": ["A_VENCER"]}.get(filtro)
    d = notas if tipos is None else notas[notas["TIPO"].isin(tipos)]
    total_aba = len(d)
    if cliente:                                           # cliente escolhido no seletor: só as notas e pedidos dele
        d = d[d["COD_CLIENTE"].map(lambda c: str(int(float(c)))) == str(cliente)]
    n_av = int((d["TIPO"] == "A_VENCER").sum())
    n_ped = int((d["TIPO"] == "PEDIDO").sum())
    n_nota = len(d) - n_ped
    cabeca = ('<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
              '<span style="color:#e0e0e0;font-size:14px;font-weight:600">Notas pendentes de validação · todos os clientes</span>'
              f'<span style="font-size:11px;color:#8892a4">{n_nota} nota(s)' + (f' ({n_av} a vencer, sem anexo)' if n_av else '')
              + (f' · {n_ped} pedido(s) ainda sem nota' if n_ped else '')
              + (f' · cliente: {len(d)} de {total_aba}' if cliente else '')
              + ' · documentos que bloqueiam e o pedido de venda</span></div>')
    if d.empty:
        return f'<div class="rp-lista">{cabeca}<span style="color:#8892a4;font-size:13px">Nenhuma nota ou pedido neste filtro.</span></div>'
    cols = colunas_documentos(d)
    grade = (f"grid-template-columns:70px 22px minmax(150px,1fr) repeat({len(cols)},minmax(104px,116px)) 124px 92px 92px;--rpn:{len(cols)}")   # cartões dos documentos estreitos: sobra espaço para o nome do cliente
    topo = (f'<div class="rp-q rp-qh" style="{grade}"><span style="text-align:left">NF / Pedido</span><span class="rp-cadc"></span><span class="rp-cli" style="text-align:left">Cliente</span>'
            + "".join(f'<span title="{escape(nome, quote=True)}">{escape(nome)}</span>' for _, nome, _ in cols)
            + '<span>Último anexo</span><span class="rp-pz">Emissão da NF</span><span class="rp-pz">Prazo</span></div>')
    linhas = ""
    for r in d.itertuples(index=False):
        cli = nomes.get(str(int(float(r.COD_CLIENTE))), f"Cliente {r.COD_CLIENTE}")
        prazo = _dt_curta(r.PRAZO)
        emissao = _dt_curta(r.EMISSAO)
        _cheia = lambda t: pd.Timestamp(t).strftime("%d/%m/%Y %H:%M")                 # data completa na dica; a célula mostra a curta
        dica_em = f' title="Emissão da NF: {_cheia(r.EMISSAO)}"' if pd.notna(r.EMISSAO) else ""
        dica_pz = (f' title="Prazo: {_cheia(r.PRAZO)}'
                   + (f" ({(pd.Timestamp(r.PRAZO) - pd.Timestamp(r.EMISSAO)).total_seconds() / 86400:.0f} dias após a emissão da NF)" if pd.notna(r.EMISSAO) else "")
                   + '"') if pd.notna(r.PRAZO) else ""
        bloqueado = credito.get(str(int(float(r.COD_CLIENTE))))
        cad = "" if bloqueado is None else (_CADEADO_FECHADO if bloqueado else _CADEADO_ABERTO)
        url = url_controle_venda(r.CONTROLE)
        dica = escape(f"{cli} · {r.CONTROLE}", quote=True)
        nf = (f'<a href="{url}" target="_blank" rel="noopener noreferrer" title="{dica}">{escape(r.ROTULO)}</a>' if url
              else f'<span style="color:#fff;font-weight:600" title="{dica}">{escape(r.ROTULO)}</span>')
        celulas = ""
        for c, nome, _ in cols:
            e_ = r.ESTADOS.get(c)
            if e_ is None:
                celulas += f'<div class="rp-c rp-c-ND" title="{escape(dica_documento(r, c, nome), quote=True)}">—</div>'
            else:
                blq = r.BLOQUEANDO.get(c, False)
                celulas += (f'<div class="rp-c rp-c-{e_}{" rp-c-blq" if blq else ""}" '
                            f'title="{escape(dica_documento(r, c, nome), quote=True)}">{rotulo_estado(e_, blq)}</div>')
        if pd.notna(r.ULTIMO_ANEXO):
            apos = bool(r.APOS_PRAZO)                       # algum documento ainda não válido entrou depois do prazo
            cor_ua = "#f5c070" if apos else "#6fd69a"        # amarelo = após o prazo, verde = no prazo
            dica_ua = (f"Último anexo: {_quando(r.ULTIMO_ANEXO)}\n{'Anexado após o prazo' if apos else 'Anexado no prazo'}"
                       + (f" ({pd.Timestamp(r.PRAZO):%d/%m %H:%M})" if pd.notna(r.PRAZO) else ""))
            ultimo = f'<span class="rp-ua" style="color:{cor_ua}" title="{escape(dica_ua, quote=True)}">{_RELOGIO_ALERTA if apos else ""}{_ha_dias(r.ULTIMO_ANEXO)}</span>'
        else:
            ger = getattr(r, "GERADA", pd.NaT)
            dica_g = f' title="Pedido gerado em {pd.Timestamp(ger):%d/%m/%Y} ({_ha_dias(ger)})"' if r.TIPO == "PEDIDO" and pd.notna(ger) else ""
            ultimo = f'<span class="rp-ua" style="color:#6b7280"{dica_g}>sem anexo</span>'
        linhas += (f'<div class="rp-q rp-qr" style="{grade}">{nf}<span class="rp-cadc">{cad}</span><span class="rp-cli" title="Abrir os controles de venda de {escape(cli, quote=True)} no SyncProcess">'
                   f'<a href="{url_busca_controles(cli)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none">{escape(cli)}</a></span>'
                   f'{celulas}{ultimo}<span class="rp-pz"{dica_em}>{emissao}</span><span class="rp-pz"{dica_pz}>{_prazo_colorido(r.PRAZO, prazo)}</span></div>')
    legenda = ('<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:#8892a4;margin-top:10px">'
               '<span><span style="color:#E24B4A">●</span> vencido (bloqueando) ou inválido</span><span><span style="color:#378ADD">●</span> em validação</span>'
               '<span><span style="color:#9ca3af">●</span> pendente (sem documento)</span><span><span style="color:#22c55e">●</span> válido</span>'
               '<span><span style="border:1.5px solid #E24B4A;border-radius:3px;display:inline-block;width:12px;height:9px;vertical-align:-1px"></span> contorno vermelho = bloqueando (prazo vencido)</span>'
               '<span>Prazo: <span style="color:#f3a3a2">vencido/hoje</span> · <span style="color:#f5b090">falta 1 dia</span> · <span style="color:#f2d25c">2 a 3 dias</span></span>'
               '<span>— a regra não vale para a nota</span><span>' + _CADEADO_FECHADO + ' crédito bloqueado · ' + _CADEADO_ABERTO + ' crédito liberado</span><span>clique na NF para abrir o controle de venda e no nome do cliente para ver os controles dele no SyncProcess</span></div>')
    larg = 70 + 22 + 150 + len(cols) * 104 + 124 + 92 + 92 + 8 * (len(cols) + 6)           # soma das colunas mínimas: abaixo disso o quadro rola de lado em vez de esmagar
    return (f'<div class="rp-lista">{cabeca}<div style="overflow-x:auto;scrollbar-width:thin;scrollbar-color:#3a3a4a #1e1e2e"><div style="min-width:{larg}px">{topo}<div style="max-height:420px;overflow-y:auto;scrollbar-width:thin;'
            f'scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div></div></div>{legenda}</div>')


def _dt_curta(ts) -> str:
    """"13/11 10:00" para datas do ano em curso (o ano é o mesmo da tela) e "13/11/2027 10:00" para as de outro ano; "—" se vazio. A data completa
    continua na dica ao passar o mouse (title da célula)."""
    if pd.isna(ts):
        return "—"
    t = pd.Timestamp(ts)
    return t.strftime("%d/%m %H:%M") if t.year == datetime.date.today().year else t.strftime("%d/%m/%Y %H:%M")


def _prazo_txt(p) -> str:
    return f"{pd.Timestamp(p):%d/%m/%Y %H:%M}" if pd.notna(p) else ""


def _excel(notas, desbloquear) -> bytes:
    """Excel do Resumo Pendências, uma aba por bloco da tela: Notas pendentes (uma coluna
    por documento, com o estado de cada um) e Para desbloquear. Só quantidades e datas (sem valores em R$)."""
    nomes, credito = _nomes_clientes(), _credito_por_cliente()
    hoje = f"{pd.Timestamp.today():%d/%m/%Y %H:%M}"

    def cliente(c):
        cod = str(int(float(c)))
        bl = credito.get(cod)
        return cod, nomes.get(cod, f"Cliente {cod}"), ("" if bl is None else ("Bloqueado" if bl else "Liberado"))

    cols_doc = colunas_documentos(notas) if notas is not None and not notas.empty else []
    linhas = []
    for r in (notas.itertuples(index=False) if notas is not None else []):
        cod, nome, cred = cliente(r.COD_CLIENTE)
        linha = {"NF / Pedido": r.ROTULO, "Controle": r.CONTROLE, "Cód. Cliente": cod, "Cliente": nome, "Crédito": cred,
                 "Situação da nota": {"BLOQUEANTE": "Bloqueante", "MANUAL": "Validação manual", "PEDIDO": "Pedido sem nota (em validação)"}.get(r.TIPO, "A vencer (sem anexo)")}
        for c, nome_doc, _ in cols_doc:
            e = r.ESTADOS.get(c)
            linha[nome_doc] = "—" if e is None else (rotulo_estado(e, True) if e == "INVALIDO" and r.BLOQUEANDO.get(c, False)
                                                     else ESTADO_ROTULO[e] + (" (bloqueando)" if r.BLOQUEANDO.get(c, False) else ""))
        for c, nome_doc, _ in cols_doc:
            linha[f"{nome_doc} · anexado em"] = _prazo_txt(r.ANEXADOS.get(c, pd.NaT))
        linha["Último anexo"] = _prazo_txt(r.ULTIMO_ANEXO)
        linha["Situação do anexo"] = "Após o prazo" if r.APOS_PRAZO else ("No prazo" if pd.notna(r.ULTIMO_ANEXO) else "")
        linha["Emissão da NF"] = _prazo_txt(r.EMISSAO)
        linha["Prazo"] = _prazo_txt(r.PRAZO)
        linhas.append(linha)
    base = ["NF / Pedido", "Controle", "Cód. Cliente", "Cliente", "Crédito", "Situação da nota"] + [n for _, n, _ in cols_doc] + [f"{n} · anexado em" for _, n, _ in cols_doc] + ["Último anexo", "Situação do anexo", "Emissão da NF", "Prazo"]
    notas_df = pd.DataFrame(linhas, columns=base)

    if desbloquear is None or desbloquear.empty:
        desb = pd.DataFrame(columns=["Cód. Cliente", "Cliente", "Situação do crédito", "Controles abertos", "NFs dos controles"])
    else:
        desb = pd.DataFrame([{"Cód. Cliente": r.COD, "Cliente": r.NOME, "Cód. Grupo de Crédito": r.GRUPO, "Situação do crédito": r.SITUACAO.capitalize(),
                              "Controles abertos": len(r.CONTROLES), "NFs dos controles": ", ".join(nf for _, nf in r.CONTROLES if nf)}
                             for r in desbloquear.itertuples(index=False)])
    return exportar_excel_abas_recebimentos([
        {"nome": "Notas pendentes", "titulo": f"Notas pendentes de validação (documentos que bloqueiam e pedido de venda) - posição em {hoje}",
         "df": notas_df, "centro": ("NF / Pedido", "Cód. Cliente", "Crédito", "Emissão da NF", "Prazo") + tuple(n for _, n, _ in cols_doc)},
        {"nome": "Para desbloquear", "titulo": f"Para desbloquear: bloqueados no crédito, com controle aberto e sem pendência documental - posição em {hoje}",
         "df": desb, "centro": ("Cód. Cliente", "Controles abertos")},
    ])


def _pre_carregar() -> None:
    """Dispara AO MESMO TEMPO as consultas independentes do painel para encher o cache: cada uma leva ~1 s e, uma depois da outra,
    somavam ~4 s; juntas levam o tempo da mais lenta. Depois disso a tela só lê o cache. Qualquer falha é ignorada (a tela então
    chama cada consulta normalmente, uma por vez)."""
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
    except Exception:
        add_script_run_ctx, ctx = None, None
    hoje = datetime.date.today()
    tarefas = [(carregar_notas_pendentes_validacao, ()), (carregar_controles_abertos_mi, ()), (carregar_grupo_credito_geral, ()),
               (carregar_grupo_credito_saldo_agente, ()), (carregar_lista_clientes, ()), (carregar_recebido_periodo_mi, (hoje, hoje)),
               (carregar_recebimento_hoje_mi, ()), (carregar_pedidos_em_validacao, ()), (carregar_tratativas_pendentes, ())]

    def rodar(f, args):
        if ctx is not None and add_script_run_ctx is not None:
            add_script_run_ctx(threading.current_thread(), ctx)       # a thread enxerga o cache e o estado da sessão
        try:
            f(*args)
        except Exception:
            pass

    try:
        with ThreadPoolExecutor(max_workers=len(tarefas)) as pool:
            for f, args in tarefas:
                pool.submit(rodar, f, args)
    except Exception:
        pass


@st.cache_data(ttl=300, show_spinner=False)
def _momento_dados() -> datetime.datetime:
    """Hora em que os dados do painel foram buscados: guardada com o mesmo prazo (5 min) das consultas e limpa junto com elas no botão Atualizar."""
    return datetime.datetime.now()


_REL_DESCONTOS = "Relatórios > 📄 Descontos Contratuais Pendentes - MI"
_REL_BOLETOS = "Relatórios > 📄 Boletos a Gerar - MI"
_CSS_ATALHOS = """<style>
.st-key-rp_cards [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:12px;row-gap:0}
.st-key-rp_cards [data-testid="stColumn"]{flex:1 1 230px !important;min-width:230px !important;width:auto !important;margin-bottom:12px}
.st-key-rp_cards [data-testid="stColumn"]:has([class*="st-key-rp_at_"]) .rp-mt{padding-right:70px;min-height:1.5rem}
.st-key-rp_cards [data-testid="stColumn"]:has([class*="st-key-rp_at_"]){position:relative}
.st-key-rp_cards [class*="st-key-rp_at_"]{position:absolute;bottom:14px;right:10px;width:auto !important;z-index:5}
.st-key-rp_cards [class*="st-key-rp_at_"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap;gap:2px;row-gap:2px}
.st-key-rp_cards [class*="st-key-rp_at_"] [data-testid="stColumn"]{flex:0 0 auto !important;min-width:0 !important}
.st-key-rp_cards [class*="st-key-rp_at_"] button{min-height:1.7rem;height:1.7rem;width:1.9rem;padding:0;border:none;background:transparent;color:#8ec2f5}
.st-key-rp_cards [class*="st-key-rp_at_"] button:hover{background:rgba(142,194,245,.14);color:#fff}
.st-key-rp_cards [class*="st-key-rp_at_"] button p{display:none}
</style>"""


def _abrir_relatorio(painel: str, estado: dict) -> None:
    """Callback do atalho do card: abre o relatório já gerado, com o filtro do card (roda antes da próxima execução do app, por isso o menu já marca o painel)."""
    st.session_state.update(estado)
    st.session_state["_painel_ativo"] = painel
    st.session_state.pop("_rel_gerou", None)


def _atalhos_card(chave: str, painel: str, estado: dict, gerar_excel, arquivo: str, tem_excel: bool) -> None:
    """Dois ícones discretos no canto inferior direito do card: abrir o relatório e baixar o Excel dele (gerado só ao clicar)."""
    visiveis = st.session_state.get("_relatorios_visiveis")
    pode_abrir = visiveis is None or painel.removeprefix("Relatórios > ") in visiveis
    if not pode_abrir:
        return
    with st.container(key=f"rp_at_{chave}"):
        colunas = st.columns(2 if tem_excel else 1, gap="small")      # sem Excel (nada pendente) é uma coluna só
        c1 = colunas[0]
        c2 = colunas[1] if tem_excel else None
        with c1:
            st.button("Abrir", icon=":material/open_in_new:", key=f"rp_abrir_{chave}", help="Abrir o relatório já gerado",
                      on_click=_abrir_relatorio, args=(painel, estado))
        if tem_excel:
            with c2:
                botao_exportar_excel(gerar_excel, arquivo, key=f"rp_xls_{chave}", label="Excel", help="Baixar o Excel do relatório")


def _desenhar_cards(cards: list, df_cr: pd.DataFrame) -> None:
    """Os quatro cartões lado a lado (quebram em linhas como a grade antiga); Descontos e Boletos ganham os atalhos de abrir/baixar o relatório."""
    from views import relatorio_boleto_nao_gerado, relatorio_desconto_financeiro_pendente
    st.html(_CSS + _CSS_ATALHOS)
    with st.container(key="rp_cards"):
        cols = st.columns(4, gap="small")
        for c, html in zip(cols, cards):
            with c:
                st.html(html)
        with cols[0]:
            _atalhos_card("desc", _REL_DESCONTOS, {"_rdf_gerou": True, "rdf_status": ["PENDENTE"]},
                          lambda: relatorio_desconto_financeiro_pendente.excel_pendentes(df_cr) or b"",
                          f"Descontos_Contratuais_Pendentes_MI_{datetime.date.today():%Y%m%d}.xlsx", st.session_state.get("_rp_xls_desc", False))
        with cols[1]:
            _atalhos_card("bol", _REL_BOLETOS, {"_rbn_gerou": True, "rbn_status": ["LIBERADO"]},
                          lambda: relatorio_boleto_nao_gerado.excel_liberados(df_cr) or b"",
                          f"Boletos a Gerar {datetime.date.today():%d-%m-%Y}.xlsx", st.session_state.get("_rp_xls_bol", False))


_COR_REGRA_INC = {"ERRO TIPO FAVORECIDO CLIENTE": ("rgba(226,75,74,.25)", "#f3a3a2"), "ERRO ACAO SEGMENTO": ("rgba(186,117,23,.25)", "#f5c070"),
                  "ERRO ACAO BAIXA EMPRESTIMO": ("rgba(74,127,181,.25)", "#8ec2f5"), "ERRO CLASSE ADIANTAMENTO": ("rgba(123,104,181,.25)", "#c3b8ee"),
                  "ERRO CLASSE 271 AGENTE NAO EMPRESTIMO": ("rgba(27,173,166,.25)", "#7fdcd7"),
                  "ERRO BAIXA ND A PAGAR": ("rgba(212,83,126,.25)", "#f2a5c0"), "ERRO BAIXA ND A RECEBER": ("rgba(143,191,63,.22)", "#c5e08f")}
_LIN_INC, _SEG_INC, _MAX_INC, _VISTAS_INC = 30, 3, 15, 3      # altura de uma linha (px), segundos por linha, máximo de lançamentos no giro e linhas à vista


def _detalhe_curto(r: dict) -> str:
    """Detalhe do erro em poucas palavras para a linha do card (o texto completo fica na dica): classe e centro de custo só pelos códigos
    (ex.: "Classe 271 · CC 352 · sem grupo"); erro de ação ou de favorecido mostra a ação."""
    from views.inconsistencias import detalhe_erro
    cats = str(r.get("CATEGORIA_ERRO", "")).upper()
    if "CLASSE" not in cats:
        return detalhe_erro(r)
    cod = lambda t: ", ".join(dict.fromkeys(re.findall(r"(?m)^\s*(\d+)\s*-", str(t or ""))))
    partes = [f"Classe {cod(r.get('CLASSE'))}".strip(), f"CC {cod(r.get('CENTRO_CUSTO'))}" if cod(r.get("CENTRO_CUSTO")) else ""]
    if "AGENTE" in cats:
        grupo = r.get("GRUPO_FINANCEIRO")
        partes.append("sem grupo" if grupo is None or pd.isna(grupo) or not str(grupo).strip() else str(grupo))
    return " · ".join(x for x in partes if x)


def _html_inconsistencias(df: pd.DataFrame, ocultar: bool, ini: datetime.date, fim: datetime.date) -> str:
    """Card de Inconsistências de Lançamentos: o total do mês em número grande à esquerda e, no meio, três lançamentos à vista; a lista sobe sozinha uma
    linha a cada 3 s (só CSS; pausa com o mouse). O botão Abrir é um botão do Streamlit posicionado por cima do canto direito do card. Sem
    inconsistência: aviso em verde."""
    base = ('.rpi{position:relative;display:flex;align-items:center;gap:18px;background:#1e1e2e;border-radius:12px;border-top:4px solid @COR@;'
            'box-sizing:border-box;padding:10px 150px 10px 18px;width:100%}.rpi-e{display:flex;align-items:baseline;gap:8px;flex:0 0 250px}'
            '.rpi-n0{font-size:40px;line-height:1;font-weight:700}.rpi-t{font-size:14px;font-weight:600;color:#e0e0e0}.rpi-s{font-size:11px;color:#8892a4}'
            '.rpi-j{flex:1;min-width:0;overflow:hidden;position:relative}'
            '.rpi-i{display:grid;grid-template-columns:112px 205px 150px 84px minmax(0,1fr) minmax(0,1fr) 78px minmax(0,1fr) 84px 100px;gap:12px;align-items:center;font-size:13px;height:@LIN@px}'
            '.rpi-h{height:18px;font-size:10px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#6b7385;border-bottom:1px solid #2a2a3a;margin-bottom:2px}'
            '.rpi-x{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
            '.rpi-et{display:inline-block;border-radius:4px;padding:2px 7px;font-size:10px;font-weight:600;white-space:nowrap}').replace("@LIN@", str(_LIN_INC))
    rotulo = "<div><div class='rpi-t'>Inconsistências</div><div class='rpi-s'>de lançamentos · mês vigente</div></div>"
    if df is None or df.empty:
        return (f"<style>{base.replace('@COR@', '#22c55e')}</style><div class='rpi'><div class='rpi-e'><b class='rpi-n0' style='color:#6fd69a'>0</b>{rotulo}</div>"
                f"<div class='rpi-j' style='color:#6fd69a;font-size:14px;font-weight:600;height:{_LIN_INC}px;line-height:{_LIN_INC}px'>"
                f"Nenhuma inconsistência de {ini:%d/%m} a {fim:%d/%m}</div></div>")
    d = df.sort_values("DATA", ascending=False).head(_MAX_INC)
    n = len(d)

    def linha(r) -> str:
        fundo, cor = _COR_REGRA_INC.get(str(r["CATEGORIA_ERRO"]).split("|")[0].strip(), ("rgba(156,163,175,.22)", "#d1d5db"))
        regra = escape(str(r["CATEGORIA_ERRO"]).replace("ERRO ", "").replace(" | ", " + "))
        saldo = "••••" if ocultar else f"{float(r['SALDO']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        origem = {"MOVIMENTO FINANCEIRO": "Mov. Financeiro", "MOV. CONTAS A PAGAR": "Mov. Contas a Pagar", "CONTAS A PAGAR": "Contas a Pagar", "CONTAS A RECEBER": "Contas a Receber"}.get(str(r.get("ORIGEM", "")), "")
        from views.inconsistencias import agente, detalhe_erro, numeracao, numero_ap
        acao = detalhe_erro(r)
        return (f'<div class="rpi-i" title="{escape(acao, quote=True)}"><span class="rpi-x" style="color:#c9d1e3;font-size:11px">{escape(origem)}</span>'
                f'<span><span class="rpi-et" style="background:{fundo};color:{cor}">{regra}</span></span>'
                f'<span class="rpi-x">{numeracao(r)}</span><span class="rpi-x">{numero_ap(r)}</span>'
                f'<span class="rpi-x" style="color:#aab0c0" title="{escape(acao, quote=True)}">{escape(_detalhe_curto(r))}</span>'
                f'<span class="rpi-x" style="color:#aab0c0" title="{escape(agente(r, "BANCO"), quote=True)}">{escape(agente(r, "BANCO"))}</span>'
                f'<span style="color:#8892a4">{pd.Timestamp(r["DATA"]):%d/%m/%Y}</span>'
                f'<span class="rpi-x" style="color:#aab0c0" title="{escape(agente(r, "FORNECEDOR"), quote=True)}">{escape(agente(r, "FORNECEDOR"))}</span>'
                f'<span style="text-align:right;color:{"#f3a3a2" if float(r["SALDO"]) < 0 else "#e0e0e0"}">{saldo}</span>'
                f'<span class="rpi-x" style="color:#8892a4">{escape(str(r["SOLICITANTE"]))}</span></div>')
    linhas = [linha(r) for r in d.to_dict("records")]
    vistas = min(n, _VISTAS_INC)
    anim = ""
    if n > _VISTAS_INC:
        linhas += linhas[:_VISTAS_INC]                  # as primeiras de novo no fim: a volta ao começo não aparece
        f = 100 / n                                     # parte do ciclo de cada linha
        m = f * 0.2                                     # 0,6 s de subida em cada 3 s
        quadros = "0%{transform:translateY(0)}"
        for k in range(n):
            quadros += f"{(k + 1) * f - m:.3f}%{{transform:translateY(-{k * _LIN_INC}px)}}{(k + 1) * f:.3f}%{{transform:translateY(-{(k + 1) * _LIN_INC}px)}}"
        anim = f"@keyframes rpis{{{quadros}}}.rpi-l{{animation:rpis {_SEG_INC * n}s ease-in-out infinite}}.rpi:hover .rpi-l{{animation-play-state:paused}}"
    return (f"<style>{base.replace('@COR@', '#E24B4A')}{anim}</style><div class='rpi'><div class='rpi-e'><b class='rpi-n0' style='color:#ef4444'>{len(df)}</b>{rotulo}</div>"
            f"<div style='flex:1;min-width:0'><div class='rpi-i rpi-h'><span>Origem</span><span>Erro</span><span>Documento</span><span>AP</span><span>Detalhe do erro</span><span>Banco</span><span>Data</span><span>Fornecedor</span><span style='text-align:right'>Valor</span><span>Solicitante</span></div><div class='rpi-j' style='height:{vistas * _LIN_INC}px'><div class='rpi-l'>{''.join(linhas)}</div></div></div></div>")


def _card_inconsistencias(ocultar: bool) -> None:
    """Card de Inconsistências abaixo dos quatro cartões, só para quem tem o painel de Inconsistências: o Abrir (dentro do card, no canto direito) leva ao painel."""
    from services.data_service import carregar_aps_erro
    hoje = datetime.date.today()
    ini, fim = hoje.replace(day=1), hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1])
    df = carregar_aps_erro(ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"))
    with st.container(key="rp_inc"):
        st.html("<style>.st-key-rp_inc{position:relative}.st-key-rp_inc .st-key-rp_inc_abrir{position:absolute;right:18px;top:50%;transform:translateY(-50%);"
                "width:auto;z-index:2}.st-key-rp_inc .st-key-rp_inc_abrir button{min-height:2rem;padding:.15rem .9rem}</style>")
        st.html(_html_inconsistencias(df, ocultar, ini, fim))
        st.button("Abrir", icon=":material/open_in_new:", key="rp_inc_abrir", help="Abrir o painel de Inconsistências de Lançamentos no mês vigente",
                  on_click=_abrir_relatorio, args=("Tesouraria > Inconsistências", {"_inc_periodo": (ini, fim)}))


def _sem_controle_repetido(notas: pd.DataFrame, pedidos) -> pd.DataFrame:
    """Um controle de venda aparece uma vez só: o controle ainda sem nota (NF vazia) que já está na lista de pedidos sai das notas,
    senão o mesmo controle vinha duas vezes ("NF nan" e "PV 21847"), enquanto o SyncProcess mostra uma validação."""
    if notas is None or notas.empty or pedidos is None or pedidos.empty:
        return notas
    sem_nf = notas["NF"].fillna("").astype(str).str.strip().str.lower().isin(["", "nan", "none", "<na>"])
    return notas[~(sem_nf & notas["CONTROLE"].astype(str).isin(set(pedidos["CONTROLE"].astype(str))))]


def contar_validacao_manual() -> int:
    """Quantidade de pendências em validação manual de documentação (a mesma da aba Validação manual: notas + pedidos sem nota).
    Usada no selo do ícone do menu; bloqueantes e a vencer não entram. Usa as consultas já em cache; 0 se o banco não respondeu."""
    try:
        pedidos = _pedidos_em_validacao()
        notas = _sem_controle_repetido(notas_pendentes_todas(), pedidos)
        n = 0 if notas is None else int((notas["TIPO"] == "MANUAL").sum())
        return n + (0 if pedidos is None else len(pedidos))
    except Exception:
        return 0


def render(df_cr: pd.DataFrame, documental: bool = False, df_grupo_agentes=None, df_grupo_geral=None) -> None:
    """documental=True é o painel Pendências Gestão Documental (Comercial): sem os quatro cartões, sem o botão Ocultar, sem a busca de cliente do quadro de
    notas ; as reclamações mostram Desconto e Saldo NF, mas o bloco Situação Grupo de Crédito (no fim) fica sem valores em R$ (a busca "Pesquisar cliente ou grupo" vale só para ele)."""
    momento = _momento_dados()
    # o botão Ocultar usa o mesmo estado do Contas a Receber (cr_ocultar): esconder valores vale para o app todo
    if "cr_ocultar" not in st.session_state:
        st.session_state["cr_ocultar"] = False
    ocultar = st.session_state["cr_ocultar"]
    c_tit, c_oc, c_xls, c_at = st.columns([6, 1.3, 1.4, 1.2], vertical_alignment="center")
    with c_tit:
        st.html("<style>@keyframes rp-anel-sirene{0%{box-shadow:0 0 0 0 rgba(226,75,74,.7)}70%,100%{box-shadow:0 0 0 12px rgba(226,75,74,0)}}"
                ".rp-sirene{display:inline-flex;border-radius:50%;padding:4px;margin-right:10px;line-height:1;"
                "animation:rp-anel-sirene 1.4s ease-out infinite}"
                ".rp-h1{display:flex;align-items:center;padding:.5rem 0 .25rem;font-size:1.9rem !important;font-weight:700;line-height:1.2;color:#fafafa;"
                "font-family:inherit;white-space:nowrap}</style>"
                f"<div class='rp-h1'><span class='rp-sirene'>{_SIRENE}</span><span style='font-size:1.9rem'>{'Pendências Gestão Documental' if documental else 'Resumo Pendências'}</span>"
                f"<span style='font-size:12px;font-weight:400;color:#6b7280;margin-left:14px;align-self:flex-end;padding-bottom:5px'>Última atualização {momento:%d/%m} às {momento:%H:%M}</span></div>"
                "<style>.st-key-btn_ocultar_rp button,.st-key-rp_atualizar button,.st-key-rp_excel button{min-height:2rem;padding:.15rem .6rem}</style>")
    with c_oc:
        if not documental:
          st.button("Ocultar" if not ocultar else "Exibir", icon=":material/visibility_off:" if not ocultar else ":material/visibility:",
                    key="btn_ocultar_rp", use_container_width=True, help="Ocultar/exibir o valor em R$ do cartão Esperado e Recebido no banco",
                    on_click=lambda: st.session_state.update(cr_ocultar=not st.session_state.get("cr_ocultar", False)))
    with c_at:
        if st.button("🔄 Atualizar", key="rp_atualizar", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Montando o resumo..."):
        _pre_carregar()
        notas = notas_pendentes_todas()
        if notas is not None:
            pedidos = _pedidos_em_validacao()                  # pedidos ainda sem nota: entram na Validação manual e em Todas
            notas = _sem_controle_repetido(notas, pedidos).assign(GERADA=pd.NaT)
            notas = notas.assign(ROTULO="NF " + notas["NF"].astype(str))
            if pedidos is not None and not pedidos.empty:
                notas = pd.concat([notas, pedidos], ignore_index=True)
        cards = [] if documental else [_card_descontos(df_cr), _card_boletos(df_cr), _card_notas(notas), _card_esperado_recebido(df_cr, ocultar)]
    if not documental:
        _desenhar_cards(cards, df_cr)
        if st.session_state.get("_inc_visivel"):
            _card_inconsistencias(ocultar)

    if notas is None:
        st.info("Não foi possível consultar as notas pendentes de validação agora.")
        return
    desbloquear = _para_desbloquear(notas)
    desbloquear = _para_desbloquear(notas)
    n_vm = int(notas["TIPO"].isin(["MANUAL", "PEDIDO"]).sum())
    c_filtro, c_busca = st.columns([1.6, 1] if not documental else [1, 0.001], vertical_alignment="center")      # filtro e busca de cliente na mesma linha
    with c_filtro:
        filtro = st.segmented_control("Notas", ["Todas", "Bloqueantes", "Validação manual", "A vencer (sem anexo)"], default="Todas",
                                      key="rp_filtro", label_visibility="collapsed",
                                      format_func=lambda o: f"Validação manual ({n_vm})" if o == "Validação manual" else o) or "Todas"
    # seletor de cliente igual ao da Situação Cliente: escolher mostra só o cliente; limpar (x) volta a mostrar todos. Vale para todas as abas.
    nomes_cli = _nomes_clientes()
    codigos = sorted({str(int(float(c))) for c in notas["COD_CLIENTE"] if pd.notna(c)}, key=lambda c: nomes_cli.get(c, c).upper())
    # a busca do seletor olha o texto de cada opção; por isso as NFs do cliente entram no texto (a lista continua mostrando "nome - código")
    nfs_cli: dict = {}
    for c_, nf_ in zip(notas["COD_CLIENTE"], notas["NF"]):
        if pd.notna(c_) and str(nf_).strip():
            nfs_cli.setdefault(str(int(float(c_))), []).append(str(nf_).strip())

    def _rotulo_cliente(c: str) -> str:
        nfs = sorted(set(nfs_cli.get(c, [])))
        return f"{nomes_cli.get(c, 'Cliente ' + c)} - {c}" + (f" · NF {', '.join(nfs[:10])}{'…' if len(nfs) > 10 else ''}" if nfs else "")

    cliente = None
    with c_busca:
      if not documental:
        cliente = st.selectbox("Cliente", codigos, index=None, key="rp_cliente", placeholder="Buscar por código, nome ou número da NF...",
                               label_visibility="collapsed", format_func=_rotulo_cliente)
    st.html(_CSS + _grafico_notas(notas, filtro, cliente))
    with c_xls:
        botao_exportar_excel(lambda: _excel(notas, desbloquear), f"Resumo_Pendencias_{datetime.date.today():%Y%m%d}.xlsx",
                             key="rp_excel", use_container_width=True, label="Excel",
                             help="Duas abas: Notas pendentes e Para desbloquear")
    # Para desbloquear e Reclamações ficam lado a lado, ABAIXO do quadro de notas (sempre à vista, sem depender das abas nem do filtro de cliente);
    # em tela estreita o Streamlit empilha
    html_recl = _html_reclamacoes_pendentes(carregar_tratativas_pendentes(), None, _nomes_clientes(), df_cr)          # as reclamações mostram Desconto e Saldo NF também no Comercial (são tratativas do Comercial e da Qualidade)
    if html_recl:
        with st.container(key="rp_par"):                     # os dois cards com a mesma altura (a coluna e o html esticam até o card mais alto)
            st.html("<style>.st-key-rp_par [data-testid='stHorizontalBlock']{align-items:stretch}"
                    ".st-key-rp_par [data-testid='stColumn']>div,.st-key-rp_par [data-testid='stColumn'] [data-testid='stElementContainer'],"
                    ".st-key-rp_par [data-testid='stColumn'] [data-testid='stHtml'],.st-key-rp_par [data-testid='stColumn'] [data-testid='stHtml']>div{height:100%}"
                    "@media (max-width:1400px){.st-key-rp_par [data-testid='stHorizontalBlock']{flex-wrap:wrap}"
                    ".st-key-rp_par [data-testid='stColumn']{min-width:100% !important}}</style>")   # tela pequena: um card embaixo do outro
            c_desb, c_recl = st.columns([3, 7], gap="small")
            c_desb.html(_CSS + _CSS_RQ + _html_para_desbloquear(desbloquear))
            c_recl.html(_CSS + html_recl)
    else:
        st.html(_CSS + _CSS_RQ + _html_para_desbloquear(desbloquear))
    if documental:
        from views import visao_geral_comercial          # bloco Situação Grupo de Crédito, o mesmo do painel Visão Geral Comercial - MI
        if df_cr is not None and not df_cr.empty and "MERCADO" in df_cr.columns:
            visao_geral_comercial._tabela_bloqueios(df_cr[df_cr["MERCADO"] == "MI"].copy(), df_grupo_agentes, df_grupo_geral, False, sem_valores=True)
