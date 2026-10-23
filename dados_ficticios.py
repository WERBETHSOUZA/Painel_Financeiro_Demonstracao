"""
Dados 100% fictícios para tirar prints do painel (postagem), sem nenhum número ou nome reais.
Nomes de empresas, valores e datas são inventados e gerados com semente fixa (sempre iguais).
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

SEMENTE = 20261020
HOJE = pd.Timestamp(date.today())

# (código, nome, código do grupo, UF, país, moeda estrangeira ou None)
_CLIENTES = [
    (1001, "HORIZONTE ALIMENTOS MATRIZ", 10, "SP", "BRA", None),
    (1002, "HORIZONTE DISTRIBUIDORA", 10, "MG", "BRA", None),
    (1003, "HORIZONTE LOGISTICA", 10, "PR", "BRA", None),
    (1101, "NORTE VERDE COMERCIO", 11, "PE", "BRA", None),
    (1102, "NORTE VERDE ATACADO", 11, "CE", "BRA", None),
    (1103, "NORTE VERDE VAREJO", 11, "PB", "BRA", None),
    (1104, "NORTE VERDE PRODUTOS", 11, "BA", "BRA", None),
    (1201, "ESTRELA DO SUL COMERCIAL", 12, "SC", "BRA", None),
    (1202, "ESTRELA DO SUL INDUSTRIA", 12, "RS", "BRA", None),
    (1301, "PLANALTO AGRO GOIAS", 13, "GO", "BRA", None),
    (1302, "PLANALTO AGRO MATO GROSSO", 13, "MT", "BRA", None),
    (1303, "PLANALTO AGRO SUL", 13, "MS", "BRA", None),
    (1401, "LITORAL SUPERMERCADOS", 14, "RJ", "BRA", None),
    (1402, "LITORAL DISTRIBUICAO", 14, "ES", "BRA", None),
    (2001, "ATLANTIC FRESH IMPORTS LLC", 20, "FL", "USA", "USD"),
    (2002, "NORDIC GROCERY TRADING", 21, "LN", "GBR", "EUR+GBP"),
    (2003, "EURO MARKET HANDELS GMBH", 22, "HH", "DEU", "EUR"),
]
_GRUPOS = {
    10: "GRUPO HORIZONTE ALIMENTOS",
    11: "GRUPO NORTE VERDE",
    12: "GRUPO ESTRELA DO SUL",
    13: "GRUPO PLANALTO AGRO",
    14: "GRUPO LITORAL",
    20: "GRUPO ATLANTIC FRESH",
    21: "GRUPO NORDIC GROCERY",
    22: "GRUPO EURO MARKET",
}
# escala de faturamento por cliente (R$ por mês, ordem de grandeza)
_ESCALA = {10: 1.6e6, 11: 0.45e6, 12: 0.5e6, 13: 0.9e6, 14: 0.35e6, 20: 1.5e6, 21: 0.5e6, 22: 0.4e6}
_COTACAO = {"USD": 5.42, "EUR": 6.18, "GBP": 7.05}
_VENDEDORES = ["MARCOS", "RENATA", "CAMILA", "THIAGO", "LUCIANA"]
_CLASSIFICACOES = ["Venda de mercadoria", "Venda de mercadoria", "Venda de mercadoria", "Prestacao de servico"]


def _faixa(dias: int) -> str:
    if dias < -30:
        return "Vencido 30+ dias"
    if dias < 0:
        return "Vencido até 30 dias"
    if dias <= 30:
        return "A vencer até 30 dias"
    if dias <= 60:
        return "A vencer 31 a 60 dias"
    if dias <= 90:
        return "A vencer 61 a 90 dias"
    return "A vencer 90+ dias"


def gerar():
    """Devolve dict com: contas_receber, grupo_geral, grupo_agentes, faturado, faturado_mensal, adiantamento."""
    rng = np.random.default_rng(SEMENTE)
    colunas_cr = [
        "COD_CLIENTE", "CLIENTE", "NF", "PARCELA", "TIPO_DOC", "ENTRADA", "VENCIMENTO", "PRORROGADO",
        "DIAS", "DIAS_CALCULADO", "SITUACAO", "FAIXA_DIAS", "SALDO_EM_ABERTO", "LIQUIDO_FIN", "MOEDA",
        "COTACAO", "SALDO_MOEDA", "VLR_PARCELA_MOEDA", "MERCADO", "BANCO_NOME", "SITUACAO_BOLETO",
        "VENDEDOR", "EMAIL_CLIENTE", "CLASSIFICACAO", "COMPLEMENTO", "TIPO_REGRA", "PERC_REGRA", "UF",
        "PAIS", "TIPO_PESSOA", "COD_ACAO", "NOME_ACAO", "SEMANA", "ANO",
    ]
    linhas = []
    nf = 48000
    regra_por_cliente = {}
    for cod, nome, grupo, uf, pais, moedas in _CLIENTES:
        me = moedas is not None
        regra = [("FATURAMENTO", "6.00%"), ("FINANCEIRO", "12.30%"), (None, None)][int(rng.integers(0, 3))]
        regra_por_cliente[cod] = regra
        n_titulos = int(rng.integers(14, 30) if not me else rng.integers(12, 22))
        # clientes "mais atrasados" para o exemplo ter vencidos e inadimplência
        taxa_vencido = {1102: 0.28, 1104: 0.18, 1302: 0.12, 2002: 0.22}.get(cod, 0.04 if not me else 0.07)
        for _ in range(n_titulos):
            nf += int(rng.integers(1, 9))
            vencido = rng.random() < taxa_vencido
            dias = int(rng.integers(-75, -1)) if vencido else int(rng.choice(
                [rng.integers(0, 30), rng.integers(0, 60), rng.integers(30, 90), rng.integers(60, 130)]))
            venc = HOJE + timedelta(days=dias)
            prazo = int(rng.choice([30, 45, 60, 90]))
            entrada = venc - timedelta(days=prazo)
            moeda = "R$"
            cot = np.nan
            saldo_moeda = np.nan
            vlr_moeda = np.nan
            valor = float(np.round(rng.uniform(9e3, 4.2e5) * (_ESCALA[grupo] / 1.2e6) ** 0.5, 2))
            if me and rng.random() < 0.88:
                moeda = str(rng.choice(moedas.split("+")))
                cot = _COTACAO[moeda] + float(rng.uniform(-0.12, 0.12))
                saldo_moeda = float(np.round(valor / cot * 1.0, 2))
                vlr_moeda = saldo_moeda
                valor = float(np.round(saldo_moeda * cot, 2))
            # a vencer: a data de crédito prevista (prorrogado) coincide com o vencimento
            prorrogado = venc if dias >= 0 else pd.NaT
            if cod == 1102 and vencido and rng.random() < 0.55:
                prorrogado = HOJE - timedelta(days=int(rng.integers(3, 25)))
            linhas.append({
                "COD_CLIENTE": cod, "CLIENTE": nome, "NF": f"{nf}", "PARCELA": int(rng.integers(1, 4)),
                "TIPO_DOC": "NF", "ENTRADA": entrada, "VENCIMENTO": venc, "PRORROGADO": prorrogado,
                "DIAS": dias, "DIAS_CALCULADO": dias,
                "SITUACAO": "VENCIDO" if dias < 0 else "A VENCER", "FAIXA_DIAS": _faixa(dias),
                "SALDO_EM_ABERTO": valor, "LIQUIDO_FIN": float(np.round(valor * 1.02, 2)),
                "MOEDA": moeda, "COTACAO": cot, "SALDO_MOEDA": saldo_moeda, "VLR_PARCELA_MOEDA": vlr_moeda,
                "MERCADO": "ME" if me else "MI",
                "BANCO_NOME": str(rng.choice(["Santander", "Santander", "Caixa Econômica", "Outros"])),
                "SITUACAO_BOLETO": "BOLETO GERADO" if rng.random() < 0.72 else "-",
                "VENDEDOR": str(rng.choice(_VENDEDORES)), "EMAIL_CLIENTE": "financeiro@exemplo.com.br",
                "CLASSIFICACAO": str(rng.choice(_CLASSIFICACOES)), "COMPLEMENTO": None,
                "TIPO_REGRA": regra[0], "PERC_REGRA": regra[1], "UF": uf, "PAIS": pais, "TIPO_PESSOA": "J",
                "COD_ACAO": 162 if me else 161, "NOME_ACAO": "VENDA EXPORTACAO" if me else "VENDA INTERNA",
                "SEMANA": int(entrada.isocalendar()[1]), "ANO": int(entrada.year),
            })
    cr = pd.DataFrame(linhas, columns=colunas_cr)
    cr["PRORROGADO"] = pd.to_datetime(cr["PRORROGADO"])
    for col in ("ENTRADA", "VENCIMENTO"):
        cr[col] = pd.to_datetime(cr[col])

    # CONTAINER (só mercado externo): várias notas por container; gerador separado para não alterar os demais números
    rng3 = np.random.RandomState(SEMENTE + 11)
    cr["CONTAINER"] = None
    for cod in cr.loc[cr["MERCADO"] == "ME", "COD_CLIENTE"].unique():
        idx = cr.index[(cr["COD_CLIENTE"] == cod) & (cr["MERCADO"] == "ME")]
        i = 0
        while i < len(idx):
            n = int(rng3.randint(1, 5))
            if rng3.rand() < 0.9:      # ~10% das notas ainda sem container informado
                cr.loc[idx[i:i + n], "CONTAINER"] = f"{rng3.choice(['DEMU', 'FICU', 'TSTU'])}{rng3.randint(1000000, 9999999)}"
            i += n

    # colunas usadas só pelos relatórios de desconto/boleto (gerador separado: não altera os demais números)
    rng2 = np.random.RandomState(SEMENTE + 7)
    perc = cr["PERC_REGRA"].astype(str).str.replace("%", "", regex=False).apply(pd.to_numeric, errors="coerce") / 100
    cr["VALOR_FATURADO"] = (cr["LIQUIDO_FIN"] * 1.04).round(2)
    desc = (cr["LIQUIDO_FIN"] * perc).round(2)
    aplicado = rng2.rand(len(cr)) < 0.4
    cr["DESC_APLIC_NF"] = np.where((cr["TIPO_REGRA"] == "FATURAMENTO") & aplicado, desc, np.nan)
    cr["DESC_APLIC_FIN"] = np.where((cr["TIPO_REGRA"] == "FINANCEIRO") & aplicado, desc, np.nan)

    # ── grupos e agentes ────────────────────────────────────────────────────
    saldo_cliente = cr.groupby("COD_CLIENTE")["SALDO_EM_ABERTO"].sum()
    ag, geral = [], []
    for grupo, nome_grupo in _GRUPOS.items():
        cods = [c for c in _CLIENTES if c[2] == grupo]
        consumo_nf_grupo = consumo_pv_grupo = 0.0
        linhas_ag = []
        for cod, nome, g, uf, pais, _ in cods:
            nf_c = float(np.round(saldo_cliente.get(cod, 0.0) * rng.uniform(1.0, 1.25), 2))
            pv_c = float(np.round(nf_c * rng.uniform(0.05, 0.55), 2))
            consumo_nf_grupo += nf_c
            consumo_pv_grupo += pv_c
            linhas_ag.append((cod, nome, uf, pais, nf_c, pv_c))
        limite = float(np.round((consumo_nf_grupo + consumo_pv_grupo) * rng.uniform(1.18, 1.9), -3))
        bloqueado = grupo in (11, 21)
        for cod, nome, uf, pais, nf_c, pv_c in linhas_ag:
            ag.append({"COD_AGENTE": cod, "COD_GRUPO": grupo, "NOME_AGENTE": nome, "UF": uf, "PAIS": pais,
                       "TIPO_PESSOA": "J", "LIMITE_DO_GRUPO": limite,
                       "CONSUMIDO_EM_NF": nf_c, "CONSUMIDO_EM_PV": pv_c})
        geral.append({
            "GRUPO_CODIGO": grupo, "NOME_GRUPO": nome_grupo, "VALOR_LIMITE": limite,
            "VALOR_RECEBER_ABERTO": float(np.round(consumo_nf_grupo, 2)),
            "VALOR_PEDIDO_ABERTO": float(np.round(consumo_pv_grupo, 2)),
            "VALOR_DISPONIVEL": float(np.round(limite - consumo_nf_grupo - consumo_pv_grupo, 2)),
            "SITUACAO_CLIENTE": "BLOQUEADO" if bloqueado else "LIBERADO",
        })

    # ── faturado mensal desde 2019 → anual e últimos 24 meses ───────────────
    anual, mensal = [], []
    primeiro = pd.Timestamp(2019, 1, 1)
    meses = pd.period_range(primeiro, HOJE, freq="M")
    for cod, nome, grupo, uf, pais, moedas in _CLIENTES:
        base = _ESCALA[grupo] * float(rng.uniform(0.35, 0.8))
        valores = {}
        for i, per in enumerate(meses):
            cresc = 0.25 + i / len(meses) * 1.1
            sazon = 1.0 + 0.35 * np.sin(per.month / 12 * 2 * np.pi)
            v = base * cresc * sazon * float(rng.uniform(0.55, 1.35))
            if rng.random() < 0.07:
                v = 0.0
            if per == meses[-1]:
                v *= 0.45   # mês atual é parcial
            valores[(per.year, per.month)] = float(np.round(v, 2))
        for ano in sorted({a for a, _ in valores}):
            total = sum(v for (a, _), v in valores.items() if a == ano)
            anual.append({"COD_CLIENTE": cod, "CLIENTE": nome, "ANO": ano,
                          "MERCADO": "ME" if moedas else "MI", "VALOR_TOTAL_FATURADO": float(np.round(total, 2)),
                          "QTD_NOTAS": int(rng.integers(20, 220))})
        corte = (HOJE.year * 12 + HOJE.month - 1) - 23
        for (a, m), v in valores.items():
            if a * 12 + m - 1 >= corte:
                mensal.append({"COD_CLIENTE": cod, "ANO": a, "MES": m, "VALOR_TOTAL_FATURADO": v})

    adiantamento = pd.DataFrame([
        {"NATUREZA": "RECEBIDO", "COD_CLIENTE": 1001, "SALDO": 68250.00},
        {"NATUREZA": "RECEBIDO", "COD_CLIENTE": 1104, "SALDO": 12400.50},
        {"NATUREZA": "RECEBIDO", "COD_CLIENTE": 1302, "SALDO": 41980.00},
        {"NATUREZA": "RECEBIDO", "COD_CLIENTE": 2001, "SALDO": 215600.00},
        {"NATUREZA": "RECEBIDO", "COD_CLIENTE": 2002, "SALDO": 87310.75},
    ])
    return {
        "contas_receber": cr, "grupo_geral": pd.DataFrame(geral), "grupo_agentes": pd.DataFrame(ag),
        "faturado": pd.DataFrame(anual), "faturado_mensal": pd.DataFrame(mensal), "adiantamento": adiantamento,
    }
