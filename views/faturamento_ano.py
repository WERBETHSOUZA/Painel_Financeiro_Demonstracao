"""
views/faturamento_ano.py
=========================
Faturamento por ano de emissão (a partir da consulta de Total Faturado por Cliente),
usado na Situação Cliente (um cliente) e no Grupo de Crédito (soma dos agentes do grupo).
"""

from datetime import date

import pandas as pd

from views.contas_receber_painel import _COR_MI, _abrev, _bloco


def dados_faturamento_ano(df_faturado, codigos: list) -> list:
    """Faturamento por ano de emissão (todo o histórico) de um ou mais clientes (códigos),
    somado, do mais recente para o mais antigo: [(ano, valor)]. Vazio quando não há dados."""
    if df_faturado is None or df_faturado.empty or not {"COD_CLIENTE", "ANO", "VALOR_TOTAL_FATURADO"}.issubset(df_faturado.columns):
        return []
    f = df_faturado[df_faturado["COD_CLIENTE"].astype(str).isin([str(c) for c in codigos])]
    por_ano = (
        f.assign(ANO=pd.to_numeric(f["ANO"], errors="coerce"))
        .dropna(subset=["ANO"])
        .groupby("ANO")["VALOR_TOTAL_FATURADO"].sum()
        .sort_index(ascending=False)
    )
    return [(int(ano), float(valor)) for ano, valor in por_ano.items()]


def nota_faturamento(escopo: str = "card Total Faturado") -> str:
    return f"{date.today().year} até {date.today():%d/%m}. O total é o mesmo do {escopo}."


_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def dados_faturamento_mes(df_mensal, codigos: list) -> list:
    """Últimos 12 meses (cronológico), somando os clientes: [(ano, mes, valor, variacao, parcial)].
    variacao = % sobre o mesmo mês do ano anterior (None no mês em andamento, que é parcial,
    ou quando não havia faturado no mês de comparação). Vazio quando não há dados."""
    if df_mensal is None or df_mensal.empty or not {"COD_CLIENTE", "ANO", "MES", "VALOR_TOTAL_FATURADO"}.issubset(df_mensal.columns):
        return []
    f = df_mensal[df_mensal["COD_CLIENTE"].astype(str).isin([str(c) for c in codigos])].copy()
    if f.empty:
        return []
    for col in ("ANO", "MES", "VALOR_TOTAL_FATURADO"):
        f[col] = pd.to_numeric(f[col], errors="coerce")
    f = f.dropna(subset=["ANO", "MES"])
    valores = {(int(a), int(m)): float(v) for (a, m), v in f.groupby(["ANO", "MES"])["VALOR_TOTAL_FATURADO"].sum().items()}
    hoje = date.today()
    base = hoje.year * 12 + hoje.month - 1
    meses = []
    for i in range(11, -1, -1):
        ano, mes = divmod(base - i, 12)
        mes += 1
        valor = valores.get((ano, mes), 0.0)
        anterior = valores.get((ano - 1, mes))
        parcial = (ano, mes) == (hoje.year, hoje.month)
        var = None if parcial or not anterior or not valor else (valor / anterior - 1) * 100
        meses.append((ano, mes, valor, var, parcial))
    return meses if any(v for _, _, v, _, _ in meses) else []


def pontos_faturamento(por_ano: list, max_anos: int = 8) -> list:
    """Últimos anos em ordem cronológica: [(ano, valor)]."""
    return sorted(por_ano)[-max_anos:]


def _html_area(pontos: list, titulo: str, total: float, sub: str, ultimo_parcial: bool, com_botao: bool = False) -> str:
    """Faixa de largura total (altura de um card): total à esquerda e gráfico de área à direita.
    pontos: [(rotulo, valor, extra_html_ou_None)] em ordem cronológica; o último ponto é tracejado
    e mais claro quando é parcial. `extra` (ex.: variação) aparece acima do rótulo do período."""
    n = len(pontos)
    maximo = max((v for _, v, _ in pontos), default=0) or 1.0
    com_extra = any(e for _, _, e in pontos)
    topo, base = 24, (62 if com_extra else 78)   # % da altura do gráfico
    xs = [(i + 0.5) / n * 100 for i in range(n)]
    ys = [base - v / maximo * (base - topo) for _, v, _ in pontos]
    total_txt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Sem <svg> (o Streamlit remove): grade, área e linha são <div> recortados com clip-path,
    # em % do próprio quadro, então acompanham qualquer largura de tela.
    def pct(v):
        return f"{v:.2f}%"

    def faixa(pares, cor, espessura=1.4):
        """Linha de espessura constante (em % da altura) ligando os pontos."""
        cima = [f"{pct(x)} {pct(y - espessura)}" for x, y in pares]
        baixo = [f"{pct(x)} {pct(y + espessura)}" for x, y in reversed(pares)]
        return (f'<div style="position:absolute;inset:0;background:{cor};'
                f'clip-path:polygon({",".join(cima + baixo)})"></div>')

    grade = "".join(
        f'<div style="position:absolute;left:0;right:0;top:{y}%;border-top:1px solid rgba(128,128,128,0.25)"></div>'
        for y in (topo, (topo + base) / 2, base)
    )
    area = linha = ""
    if n >= 2:
        borda = [f"{pct(x)} {pct(y)}" for x, y in zip(xs, ys)]
        area = (f'<div style="position:absolute;inset:0;background:rgba(46,134,171,0.22);'
                f'clip-path:polygon({pct(xs[0])} {base}%,{",".join(borda)},{pct(xs[-1])} {base}%)"></div>')
        pares = list(zip(xs, ys))
        corpo = pares[:-1] if ultimo_parcial else pares
        if len(corpo) >= 2:
            linha += faixa(corpo, "#2E86AB")
        if ultimo_parcial:
            linha += faixa(pares[-2:], "#7FB8D1")

    marcas = ""
    for i, ((rotulo, valor, extra), x, y) in enumerate(zip(pontos, xs, ys)):
        cor = "#7FB8D1" if ultimo_parcial and i == n - 1 else "#2E86AB"
        marcas += (
            f'<span style="position:absolute;left:{x:.2f}%;top:{y:.2f}%;width:9px;height:9px;border-radius:50%;'
            f'background:{cor};transform:translate(-50%,-50%)"></span>'
            f'<span style="position:absolute;left:{x:.2f}%;top:calc({y:.2f}% - 17px);transform:translateX(-50%);'
            f'font-size:12px;font-weight:600;white-space:nowrap">{_abrev(valor, False) if valor else ""}</span>'
            f'<span style="position:absolute;left:{x:.2f}%;bottom:0;transform:translateX(-50%);'
            f'font-size:12px;opacity:.7;white-space:nowrap">{rotulo}</span>'
        )
        if extra:
            marcas += (f'<span style="position:absolute;left:{x:.2f}%;bottom:16px;transform:translateX(-50%);'
                       f'font-size:11px;white-space:nowrap">{extra}</span>')

    return (
        '<div style="background:#1e1e2e;border-left:4px solid #2E86AB;border-radius:8px;padding:12px 18px;'
        'display:flex;gap:24px;align-items:center;min-height:112px;box-sizing:border-box;color:#e0e0e0">'
        '<div style="min-width:200px;max-width:240px">'
        f'<div style="font-size:13px;color:#aaaaaa;margin-bottom:4px">{titulo}</div>'
        f'<div style="font-size:22px;font-weight:600;color:#ffffff;white-space:nowrap;line-height:1.2">{total_txt}</div>'
        f'<div style="font-size:11px;opacity:.65;margin-top:4px">{sub}</div></div>'
        # com o botão Por ano | Por mês no canto superior direito, o gráfico termina antes dele
        f'<div class="an-area" style="position:relative;flex:1;height:100px;margin-right:{112 if com_botao else 0}px">'
        f'{grade}{area}{linha}{marcas}</div></div>'
    )


def html_grafico_faturamento(por_ano: list, total: float, max_anos: int = 8, com_botao: bool = False) -> str:
    """Total Faturado por ano: o ano em andamento é tracejado e marcado como parcial."""
    pts = pontos_faturamento(por_ano, max_anos)
    parcial = pts[-1][0] == date.today().year
    pontos = [(f"{ano}*" if parcial and i == len(pts) - 1 else str(ano), valor, None)
              for i, (ano, valor) in enumerate(pts)]
    sub = f"por ano desde {pts[0][0]}" + (f" · {date.today().year} parcial" if parcial else "")
    return _html_area(pontos, "Total Faturado", total, sub, parcial, com_botao)


def html_grafico_faturamento_mes(meses: list, com_botao: bool = False) -> str:
    """Mesmo gráfico de área, com os últimos 12 meses e a variação sobre o mesmo mês do ano anterior."""
    pontos = []
    for ano, mes, valor, var, parcial in meses:
        if not valor:
            extra = '<span style="opacity:.6">sem fat.</span>'
        elif var is None:
            extra = '<span style="opacity:.6">parcial</span>' if parcial else '<span style="opacity:.6">—</span>'
        else:
            cor = "#22c55e" if var >= 0 else "#E24B4A"
            extra = f'<b style="color:{cor}">{f"{var:+.2f}%".replace(".", ",")}</b>'
        pontos.append((_MESES[mes - 1] + ("*" if parcial else ""), valor, extra))
    ano_i, mes_i = meses[0][0], meses[0][1]
    ano_f, mes_f = meses[-1][0], meses[-1][1]
    sub = f"{_MESES[mes_i - 1]}/{str(ano_i)[2:]} a {_MESES[mes_f - 1]}/{str(ano_f)[2:]} · {_MESES[mes_f - 1]} parcial<br>% = variação sobre o mesmo mês do ano anterior"
    return _html_area(pontos, "Faturado nos últimos 12 meses", sum(m[2] for m in meses), sub, meses[-1][4], com_botao)


def dados_variacao_anual(por_ano: list):
    """Variação do faturado ano a ano. Devolve (linhas, melhor_ano, media) ou None.
    linhas: do mais recente para o mais antigo, [(ano, valor, variacao_pct_ou_None, parcial)].
    O ano em andamento é parcial e fica sem percentual (comparar com um ano fechado enganaria);
    o melhor ano e a média consideram só anos fechados (ou todos, se só existir o parcial)."""
    if not por_ano:
        return None
    ordem = sorted(por_ano)
    valores = dict(ordem)
    ano_atual = date.today().year
    linhas = []
    for ano, valor in sorted(por_ano, reverse=True):
        parcial = ano == ano_atual
        anterior = valores.get(ano - 1)
        variacao = None if parcial or not anterior else (valor / anterior - 1) * 100
        linhas.append((ano, valor, variacao, parcial))
    fechados = [(a, v) for a, v in ordem if a != ano_atual] or ordem
    melhor = max(fechados, key=lambda t: t[1])
    media = sum(v for _, v in fechados) / len(fechados)
    return linhas, melhor, media


def _pct_sinal(v: float) -> str:
    return f"{v:+.2f}%".replace(".", ",")


def html_variacao_anual(por_ano: list) -> str:
    dados = dados_variacao_anual(por_ano)
    if dados is None:
        return _bloco("Variação anual", "R$ · faturado", _COR_MI, "",
                      '<div style="padding:30px 0">Sem faturamento no período.</div>', 0.0,
                      ocultar=False).replace("Total em reais", "Melhor ano")
    linhas, (ano_melhor, valor_melhor), _ = dados
    maximo = max(v for _, v, _, _ in linhas) or 1.0
    corpo = ""
    for ano, valor, var, parcial in linhas:
        cor_barra = "#7FB8D1" if parcial else "#2E86AB"
        if var is None:
            pc = '<span style="min-width:64px;text-align:right;opacity:.6;font-size:12px">parcial</span>' if parcial else \
                 '<span style="min-width:64px;text-align:right;opacity:.6">—</span>'
        else:
            cor = "#22c55e" if var >= 0 else "#E24B4A"
            pc = f'<span style="min-width:64px;text-align:right;font-weight:600;color:{cor}">{_pct_sinal(var)}</span>'
        corpo += (
            '<div style="display:flex;align-items:center;gap:8px;height:27px;box-sizing:border-box;font-size:13px">'
            f'<span style="width:44px">{ano}{"*" if parcial else ""}</span>'
            '<span style="flex:1;height:9px;background:rgba(128,128,128,0.18);border-radius:3px;overflow:hidden">'
            f'<i class="an-wipe" style="display:block;height:100%;width:{valor / maximo * 100:.1f}%;background:{cor_barra}"></i></span>'
            f'<span style="min-width:62px;text-align:right">{_abrev(valor, False)}</span>{pc}</div>'
        )
    lista = f'<div style="max-height:108px;overflow-y:auto;scrollbar-width:thin;padding-right:6px">{corpo}</div>'
    rodape = (
        '<div style="display:flex;justify-content:space-between;font-size:15px;font-weight:600;margin-top:8px;'
        'padding-top:7px;border-top:1px solid rgba(128,128,128,0.3)">'
        f'<span>Melhor ano</span><span>{ano_melhor} · {_abrev(valor_melhor, False)}</span></div>'
    )
    return (
        '<div style="background:rgba(128,128,128,0.08);border:1px solid rgba(128,128,128,0.25);border-radius:12px;padding:12px 14px">'
        '<div style="display:flex;justify-content:space-between;align-items:center;font-size:17px;font-weight:600;margin-bottom:8px">'
        '<span>Variação anual</span>'
        f'<span style="font-size:12px;padding:2px 9px;border-radius:4px;font-weight:500;background:{_COR_MI}22;color:{_COR_MI}">R$ · faturado</span></div>'
        f'{lista}{rodape}</div>'
    )


def html_faturamento_ano(por_ano: list, escopo: str = "card Total Faturado") -> str:
    """Quadro do faturamento por ano, resumido em mi/mil. O total é o do card Total Faturado."""
    maximo = max((v for _, v in por_ano), default=0)
    corpo = ""
    for ano, valor in por_ano:
        parcial = ano == date.today().year
        etiqueta = (
            '<span style="font-size:10px;padding:0 5px;margin-left:5px;border-radius:4px;'
            'background:#BA751733;color:#BA7517">parcial</span>' if parcial else ""
        )
        cor = "#7FB8D1" if parcial else "#2E86AB"
        corpo += (
            '<div style="display:grid;grid-template-columns:78px minmax(0,1fr) 84px;gap:8px;'
            'align-items:center;font-size:14px;padding:2px 0">'
            f'<div>{ano}{etiqueta}</div>'
            f'<div style="height:13px;border-radius:3px;overflow:hidden;background:rgba(128,128,128,0.15)">'
            f'<div class="an-wipe" style="width:{valor / maximo * 100 if maximo else 0:.2f}%;height:100%;background:{cor}"></div></div>'
            f'<div style="text-align:right;font-weight:500">{_abrev(valor, False)}</div></div>'
        )
    html = _bloco(
        "Faturamento por ano", "R$ · todo o histórico", _COR_MI,
        '<div style="height:20px"></div>', corpo, sum(v for _, v in por_ano), ocultar=False, abreviar=True,
    ).replace("Total em reais", "Total faturado")
    nota = f'<div style="font-size:11px;color:rgba(128,128,128,0.95);margin-top:6px">{nota_faturamento(escopo)}</div>'
    return html[:-len("</div>")] + nota + "</div>"   # nota dentro do quadro


def faturamento_para_imagem(por_ano: list, escopo: str = "card Total Faturado") -> dict:
    """Mesmo quadro no formato que a imagem para e-mail espera (vazio quando não há dados)."""
    if not por_ano:
        return {}
    return {
        "titulo": "Faturamento por ano",
        "linhas": [
            {"label": str(ano) + (" (parcial)" if ano == date.today().year else ""),
             "valor": valor, "texto": _abrev(valor, False)}
            for ano, valor in por_ano
        ],
        "total_texto": "R$ " + _abrev(sum(v for _, v in por_ano), False),
        "nota": nota_faturamento(escopo),
    }
