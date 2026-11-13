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

import datetime
from html import escape

import pandas as pd
import streamlit as st

from services.data_service import carregar_lista_clientes, carregar_recebido_mensal_mi, carregar_recebimento_hoje_mi
from utils.pendencias import notas_pendentes_todas, url_controle_venda
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
.rp-linha{display:grid;grid-template-columns:78px minmax(0,1.2fr) minmax(0,2fr) 52px 86px;gap:12px;align-items:center;font-size:13px;padding:4px 0}
.rp-linha a{color:#fff;font-weight:600;text-decoration:none;white-space:nowrap}.rp-linha a:hover{text-decoration:underline;color:#6db3f5}
.rp-cli{color:#aab2c5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp-bar{height:12px;border-radius:3px;background:rgba(128,128,128,0.15);overflow:hidden}
.rp-linha em{font-style:normal;color:#8892a4;text-align:right;white-space:nowrap}
@media (max-width:640px){.rp-linha{grid-template-columns:70px minmax(0,1fr) 46px}.rp-cli,.rp-linha em:last-child{display:none}}
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


def _grafico_notas(notas, filtro: str) -> str:
    nomes = _nomes_clientes()
    d = notas if filtro == "Todas" else notas[notas["TIPO"] == ("BLOQUEANTE" if filtro == "Bloqueantes" else "MANUAL")]
    cabeca = ('<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
              '<span style="color:#e0e0e0;font-size:14px;font-weight:600">Notas pendentes de validação · todos os clientes</span>'
              '<span style="font-size:11px;color:#8892a4"><span style="color:#ff6b6b">●</span> bloqueante &nbsp;'
              '<span style="color:#6db3f5">●</span> validação manual</span></div>')
    if d.empty:
        return f'<div class="rp-lista">{cabeca}<span style="color:#8892a4;font-size:13px">Nenhuma nota neste filtro.</span></div>'
    maximo = max(int(d["QTD_DOCS"].max()), 1)
    linhas = ""
    for i, r in enumerate(d.itertuples(index=False)):
        cor = _VERMELHO if r.TIPO == "BLOQUEANTE" else _AZUL
        cli = nomes.get(str(int(float(r.COD_CLIENTE))), f"Cliente {r.COD_CLIENTE}")
        prazo = r.PRAZO.strftime("%d/%m/%Y") if pd.notna(r.PRAZO) else "—"
        url = url_controle_venda(r.CONTROLE)
        dica = escape(f"{'Bloqueante' if r.TIPO == 'BLOQUEANTE' else 'Validação manual'} · {cli} · {r.CONTROLE} · "
                      + " · ".join(r.DOCUMENTOS), quote=True)
        nf = (f'<a href="{url}" target="_blank" rel="noopener noreferrer" title="{dica}">NF {escape(r.NF)}</a>' if url
              else f'<span style="color:#fff;font-weight:600" title="{dica}">NF {escape(r.NF)}</span>')
        linhas += (f'<div class="rp-linha">{nf}<span class="rp-cli" title="{escape(cli, quote=True)}">{escape(cli)}</span>'
                   f'<div class="rp-bar"><div class="an-wipe" style="animation-delay:{min(i, 14) * 45}ms;'
                   f'width:{r.QTD_DOCS / maximo * 100:.1f}%;height:100%;background:{cor}"></div></div>'
                   f'<em>{r.QTD_DOCS} doc.</em><em>{prazo}</em></div>')
    rodape = (f'<div style="height:1px;background:#2a2a3a;margin:8px 0 6px"></div><span style="color:#8892a4;font-size:11px">'
              f'{len(d)} nota(s) · clique na NF para abrir o controle de venda no SyncProcess · passe o mouse para ver os documentos</span>')
    return (f'<div class="rp-lista">{cabeca}<div style="max-height:380px;overflow-y:auto;scrollbar-width:thin;'
            f'scrollbar-color:#3a3a4a #1e1e2e">{linhas}</div>{rodape}</div>')


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
