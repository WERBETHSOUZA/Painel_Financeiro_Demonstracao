"""
Dados 100% fictícios das telas mais novas do painel: recebimentos (baixas no banco, PMR), vendas por vendedor,
adiantamentos, descontos, fretes, aprovação com classificação Produtor/Fornecedor e histórico de pagamentos.
Nomes, valores, bancos e datas são inventados (semente fixa: sempre iguais). Os formatos (colunas) são os mesmos das
consultas do painel real, para as telas rodarem sem nenhuma adaptação.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

SEMENTE = 20261110
HOJE = pd.Timestamp(date.today())

_CLIENTES_MI = [
    (1001, "HORIZONTE ALIMENTOS MATRIZ", "SP"), (1002, "HORIZONTE DISTRIBUIDORA", "MG"),
    (1003, "HORIZONTE LOGISTICA", "PR"), (1101, "NORTE VERDE COMERCIO", "PE"), (1102, "NORTE VERDE ATACADO", "CE"),
    (1103, "NORTE VERDE VAREJO", "PB"), (1104, "NORTE VERDE PRODUTOS", "BA"), (1201, "ESTRELA DO SUL COMERCIAL", "SC"),
    (1202, "ESTRELA DO SUL INDUSTRIA", "RS"), (1301, "PLANALTO AGRO GOIAS", "GO"),
    (1302, "PLANALTO AGRO MATO GROSSO", "MT"), (1303, "PLANALTO AGRO SUL", "MS"),
    (1401, "LITORAL SUPERMERCADOS", "RJ"), (1402, "LITORAL DISTRIBUICAO", "ES"),
]
_CLIENTES_ME = [(2001, "ATLANTIC FRESH IMPORTS LLC"), (2002, "NORDIC GROCERY TRADING"), (2003, "EURO MARKET HANDELS GMBH")]
BANCOS = [("BANCO ALFA CC 11111-1", 0.80), ("BANCO ALFA CAUCIONADA CC 22222-2", 0.10),
          ("BANCO BETA CC 33333-3", 0.07), ("BANCO GAMA CC 44444-4", 0.03)]
_VENDEDORES = ["MARCOS", "RENATA", "CAMILA", "THIAGO", "LUCIANA"]
_ORGS = [(6, "ORGANIZACAO ALFA"), (7, "ORGANIZACAO BETA")]


def _dias_uteis(inicio: pd.Timestamp, fim: pd.Timestamp):
    return [d for d in pd.date_range(inicio, fim, freq="D") if d.weekday() < 5]


# ── Recebimentos (baixas no banco) ──────────────────────────────────────────────
def baixas() -> pd.DataFrame:
    """Uma linha por baixa (dia, título, parcela) de dois anos e meio até hoje: o que entrou no banco."""
    rng = np.random.RandomState(SEMENTE)
    inicio = pd.Timestamp(HOJE.year - 2, 1, 1)
    linhas, nf = [], 41000
    pesos = np.array([p for _, p in BANCOS])
    for dia in _dias_uteis(inicio, HOJE):
        sazon = 1.0 + 0.22 * np.sin(dia.month / 12 * 2 * np.pi)
        n = rng.poisson(6.3 * sazon * (0.45 if dia == HOJE else 1.0))
        for _ in range(n):
            cod, nome, uf = _CLIENTES_MI[rng.randint(len(_CLIENTES_MI))]
            nf += rng.randint(1, 6)
            valor = float(np.round(np.exp(rng.normal(10.55, 0.75)), 2))
            u = rng.rand()
            if u < 0.62:
                desvio = 0                                  # pagou no vencimento
            elif u < 0.88:
                desvio = 1                                  # dia seguinte (crédito D+1)
            elif u < 0.95:
                desvio = rng.randint(2, 31)                 # atraso
            else:
                desvio = -rng.randint(1, 16)                # antecipado
            venc = dia - pd.Timedelta(days=int(desvio))
            prazo = int(rng.choice([30, 45, 60, 75, 90], p=[0.35, 0.3, 0.2, 0.1, 0.05]))
            linhas.append({
                "DIA": dia, "DOC": str(nf), "AGN": cod, "CLIENTE": nome,
                "BANCO": BANCOS[rng.choice(len(BANCOS), p=pesos)][0], "PARC": f"{rng.randint(1, 4):03d}",
                "VALOR_PAGO": valor, "VENCIMENTO": venc, "EMISSAO": venc - pd.Timedelta(days=prazo),
            })
    return pd.DataFrame(linhas)


def recebimento_hoje() -> dict:
    """Bloco "Hoje" do Contas a Receber MI: esperado, baixado e em aberto para o crédito do dia (vazio em fim de semana)."""
    hoje = HOJE.date()
    if hoje.weekday() >= 5:
        return {}
    venc = [hoje - timedelta(days=1)] if hoje.weekday() != 0 else [hoje - timedelta(days=3), hoje - timedelta(days=2),
                                                                       hoje - timedelta(days=1)]
    esperado = 748_320.40
    baixa = 701_940.10
    return {"data": hoje, "vencimentos": venc, "parcelas": 9, "abertas": 2, "esperado": esperado, "aberto": esperado - baixa,
            "baixa_esperado": baixa, "antecipado": 118_400.00, "nd": 0.0, "adiantamento": 0.0}


def recebimentos_por_banco(inicio: pd.Timestamp, fim: pd.Timestamp, orgs: tuple) -> pd.DataFrame:
    """Relatório Recebimento por Banco: as baixas (MI) e algumas do Mercado Externo, no período e nas organizações pedidas."""
    b = baixas()
    b = b[(b["DIA"] >= inicio) & (b["DIA"] <= fim)].copy()
    rng = np.random.RandomState(SEMENTE + 1)
    org = rng.choice([o for o, _ in _ORGS], size=len(b), p=[0.88, 0.12])
    mi = pd.DataFrame({
        "DATA BAIXA": b["DIA"].values, "COD_BANCO": [str(40000 + BANCOS.index(next(x for x in BANCOS if x[0] == n)))
                                                    for n in b["BANCO"]], "BANCO": b["BANCO"].values,
        "DOCUMENTO": b["DOC"].values, "COD. AGENTE": b["AGN"].values, "NOME AGENTE": b["CLIENTE"].values,
        "MERCADO": "MI", "PARCELA": b["PARC"].values, "VALOR BAIXA": b["VALOR_PAGO"].values,
        "NUM. LANCTO": 3_000_000 + np.arange(len(b)), "ORGANIZACAO": [dict(_ORGS)[o] for o in org],
        "COD. FILIAL": 1, "COD. ACAO": 196, "ACAO": "196 - BAIXA CREC",
    })
    mi["_ORG"] = org
    me_n = max(int(len(b) * 0.06), 0)
    if me_n:
        pick = rng.choice(len(b), size=me_n, replace=False)
        me = mi.iloc[pick].copy()
        me["MERCADO"] = "ME"
        cli = [_CLIENTES_ME[i % 3] for i in range(me_n)]
        me["COD. AGENTE"] = [c for c, _ in cli]
        me["NOME AGENTE"] = [n for _, n in cli]
        me["BANCO"] = "BANCO GAMA CC 44444-4"
        me["VALOR BAIXA"] = (me["VALOR BAIXA"] * 0.7).round(2)
        mi = pd.concat([mi, me], ignore_index=True)
    mi = mi[mi["_ORG"].isin(list(orgs))].drop(columns="_ORG")
    return mi.sort_values(["DATA BAIXA", "BANCO", "DOCUMENTO"]).reset_index(drop=True)


# ── Vendas por vendedor (Visão Geral Comercial) ────────────────────────────────
def vendas_dia_vendedor() -> pd.DataFrame:
    rng = np.random.RandomState(SEMENTE + 2)
    inicio = pd.Timestamp(HOJE.year - 2, 1, 1)
    linhas = []
    peso_v = np.array([0.32, 0.26, 0.2, 0.13, 0.09])
    for dia in _dias_uteis(inicio, HOJE):
        sazon = 1.0 + 0.3 * np.sin((dia.month + 1) / 12 * 2 * np.pi)
        cresc = 0.8 + 0.4 * ((dia - inicio).days / max((HOJE - inicio).days, 1))
        for v, p in zip(_VENDEDORES, peso_v):
            if rng.rand() < 0.12:
                continue
            q = rng.randint(1, 6)
            valor = float(np.round(1.1e6 * p * sazon * cresc * rng.uniform(0.35, 1.7) * (0.45 if dia == HOJE else 1), 2))
            linhas.append({"DIA": dia, "VENDEDOR": v, "QTD_NOTAS": int(q), "VALOR_TOTAL_FATURADO": valor})
    return pd.DataFrame(linhas)


def notas_vendidas(data_ini: str) -> pd.DataFrame:
    """Uma linha por nota (a partir de data_ini, AAAA-MM-DD), dividindo o faturado do dia de cada vendedor."""
    rng = np.random.RandomState(SEMENTE + 3)
    v = vendas_dia_vendedor()
    v = v[v["DIA"] >= pd.Timestamp(data_ini)]
    linhas, nota = [], 90_000
    for r in v.itertuples(index=False):
        partes = rng.dirichlet(np.ones(int(r.QTD_NOTAS))) * r.VALOR_TOTAL_FATURADO
        for parte in partes:
            cod, nome, uf = _CLIENTES_MI[rng.randint(len(_CLIENTES_MI))]
            nota += int(rng.randint(1, 4))
            linhas.append({"EMISSAO": r.DIA, "NOTA": nota, "COD_CLIENTE": cod, "CLIENTE": nome, "UF": uf,
                           "VALOR_TOTAL": float(np.round(parte, 2)), "VENDEDOR": r.VENDEDOR})
    return pd.DataFrame(linhas, columns=["EMISSAO", "NOTA", "COD_CLIENTE", "CLIENTE", "UF", "VALOR_TOTAL", "VENDEDOR"])


# ── Adiantamentos ───────────────────────────────────────────────────────────────
def adiantamentos():
    rng = np.random.RandomState(SEMENTE + 4)
    agentes = [(1001, "HORIZONTE ALIMENTOS MATRIZ"), (1104, "NORTE VERDE PRODUTOS"), (1302, "PLANALTO AGRO MATO GROSSO"),
               (2001, "ATLANTIC FRESH IMPORTS LLC"), (2002, "NORDIC GROCERY TRADING"),
               (3001, "AGROPECUARIA VALE VERDE"), (3002, "TRANSPORTES RAPIDO SUL"), (3003, "FERTILIZANTES BOA SAFRA"),
               (3004, "SEMENTES E INSUMOS CAMPO BELO"), (3005, "LOGISTICA COSTA AZUL")]
    linhas = []
    for cod, nome in agentes:
        natureza = "RECEBIDO" if cod < 3000 else "EFETUADO"
        for _ in range(int(rng.randint(2, 6))):
            valor = float(np.round(rng.uniform(8e3, 2.4e5), 2))
            em_aberto = rng.rand() < 0.65
            org, nome_org = _ORGS[int(rng.rand() < 0.15)]
            linhas.append({
                "ORG_IN_CODIGO": org, "ORGANIZACAO": nome_org, "FIL_IN_CODIGO": int(rng.randint(1, 4)), "AGN_IN_CODIGO": cod,
                "AGENTE": nome, "NATUREZA": natureza, "MOV_ST_DOCUMENTO": f"AD{rng.randint(10000, 99999)}",
                "MOV_DT_DATADOCTO": HOJE - pd.Timedelta(days=int(rng.randint(3, 240))), "MOV_RE_VALOR": valor,
                "SALDO": float(np.round(valor * (rng.uniform(0.2, 1.0) if em_aberto else 0.0), 2)),
                "RATEIO_CENTRO_CUSTO": f"{rng.choice(['Operações', 'Comercial', 'Logística'])} 100,00%",
                "SITUACAO": "EM ABERTO" if em_aberto else "BAIXADO",
                "COMPLEMENTO": f"Adiantamento referente ao pedido {rng.randint(1000, 9999)}",
            })
    geral = pd.DataFrame(linhas)
    total = (geral.groupby(["ORG_IN_CODIGO", "ORGANIZACAO", "FIL_IN_CODIGO", "AGN_IN_CODIGO", "AGENTE", "NATUREZA"], as_index=False)
             .agg(TOTAL_ADIANTADO_AGENTE=("MOV_RE_VALOR", "sum"), TOTAL_EM_ABERTO_AGENTE=("SALDO", "sum")))
    total.columns = ["COD_ORGANIZACAO", "ORGANIZACAO", "COD_FILIAL", "COD_AGENTE", "AGENTE", "NATUREZA",
                     "TOTAL_ADIANTADO_AGENTE", "TOTAL_EM_ABERTO_AGENTE"]
    total.insert(3, "FILIAL", [f"Filial {int(c)}" for c in total["COD_FILIAL"]])
    total = total[["COD_ORGANIZACAO", "ORGANIZACAO", "COD_FILIAL", "FILIAL", "COD_AGENTE", "AGENTE", "NATUREZA",
                   "TOTAL_ADIANTADO_AGENTE", "TOTAL_EM_ABERTO_AGENTE"]]
    saldo = (geral.groupby(["AGN_IN_CODIGO", "NATUREZA"], as_index=False)["SALDO"].sum())
    return geral, total, saldo


# ── Descontos e fretes ──────────────────────────────────────────────────────────
def descontos_operacionais(inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    rng = np.random.RandomState(SEMENTE + 5)
    classes = ["DESCONTO CONTRATUAL", "DESCONTO FINANCEIRO", "DESCONTO PONTUALIDADE", "ABATIMENTO COMERCIAL"]
    linhas = []
    dias = _dias_uteis(HOJE - pd.Timedelta(days=400), HOJE)
    for dia in dias:
        for _ in range(int(rng.poisson(1.2))):
            cod, nome, _ = _CLIENTES_MI[rng.randint(len(_CLIENTES_MI))] if rng.rand() < 0.93 else (*_CLIENTES_ME[rng.randint(3)], "")
            me = cod >= 2000
            linhas.append({
                "COD. AGENTE": cod, "NOME AGENTE": nome, "PARCELA": f"{rng.randint(1, 4):03d}", "DATA": dia,
                "DOCUMENTO": str(40000 + rng.randint(0, 9000)), "PA_ST_SIGLA": "USA" if me else "BRA",
                "MERCADO": "ME" if me else "MI", "VALOR MOVIMENTO": float(np.round(rng.uniform(120, 9800), 2)),
                "CLASSE LANCAMENTO (DESCONTO)": str(rng.choice(classes)),
                "DATA INCLUSAO": dia + pd.Timedelta(days=int(rng.randint(0, 3))),
                "USUARIO INCLUSAO": str(rng.choice(["ana.souza", "bruno.lima", "carla.mendes"])),
                "COMPLEMENTO": f"Desconto referente à NF {40000 + rng.randint(0, 9000)}",
                "TIPO": str(rng.choice(["CONTRATUAL", "OPERACIONAL", "CONCEDIDOS"], p=[0.5, 0.3, 0.2])),
            })
    df = pd.DataFrame(linhas)
    return df[(df["DATA"] >= inicio) & (df["DATA"] <= fim)].reset_index(drop=True)


def fretes_mot(inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    rng = np.random.RandomState(SEMENTE + 6)
    favorecidos = ["42501 - TRANSPORTADORA FILIAL LTDA", "678 - SIDERURGICA EXEMPLO S/A"]
    linhas, ap = [], 912000
    for dia in _dias_uteis(HOJE - pd.Timedelta(days=300), HOJE + pd.Timedelta(days=60)):
        for _ in range(int(rng.poisson(0.9))):
            ap += int(rng.randint(1, 5))
            valor = float(np.round(rng.uniform(4e3, 9e4), 2))
            baixado = dia < HOJE - pd.Timedelta(days=int(rng.randint(2, 20)))
            linhas.append({
                "ORG": int(rng.choice([6, 42500])), "TIPO_DOCTO": str(rng.choice(["NF", "CTE", "FAT"])), "AP": ap,
                "DOCTO": str(rng.randint(10000, 99999)), "FAVORECIDO": str(rng.choice(favorecidos)), "VALOR": valor,
                "SALDO": 0.0 if baixado else valor,
                "STATUS": "BAIXADO" if baixado else ("VENCIDO" if dia < HOJE else "NO PRAZO"), "PRORROGADO": dia,
                "ACAO": "Frete sobre compras", "RATEIO_CLASSES": "Frete 100,00%",
                "RATEIO_CENTRO_CUSTO": "Logística 100,00%", "RATEIO_PROJETO": "Safra 2026 100,00%",
                "SOLICITANTE": str(rng.choice(["MARCOS", "RENATA", "THIAGO"])),
            })
    df = pd.DataFrame(linhas)
    return df[(df["PRORROGADO"] >= inicio) & (df["PRORROGADO"] <= fim)].reset_index(drop=True)


def classes_desconto(nfs: tuple, clientes: tuple) -> pd.DataFrame:
    """Classes contábeis dos descontos já lançados nas NFs pedidas (uma linha por NF e classe)."""
    rng = np.random.RandomState(SEMENTE + 7)
    linhas = []
    for nf, cli in zip(nfs, clientes):
        linhas.append({"TIPO": "NF", "COD_CLIENTE": str(cli), "NF": str(nf), "PARCELA": "001", "REDUZIDO": 41101,
                       "DESCRICAO": "DESCONTOS CONCEDIDOS", "VALOR": int(rng.randint(500, 9000))})
    return pd.DataFrame(linhas, columns=["TIPO", "COD_CLIENTE", "NF", "PARCELA", "REDUZIDO", "DESCRICAO", "VALOR"])


# ── Aprovação (com classificação Produtor/Fornecedor) ───────────────────────────
def aprovacoes() -> pd.DataFrame:
    """APs em aprovação, no formato da consulta real. A classificação vale para a AP inteira: a AP de produtor tem a
    compra da fruta (ação de produtor) e o INSS Funrural, e as duas linhas saem como Produtor."""
    rng = np.random.RandomState(SEMENTE + 8)
    fornecedores = ["AGROPECUARIA VALE VERDE", "TRANSPORTES RAPIDO SUL", "EMBALAGENS PLANALTO", "SERVICOS GERAIS HORIZONTE",
                    "MANUTENCAO INDUSTRIAL NORTE", "FERTILIZANTES BOA SAFRA", "LOGISTICA COSTA AZUL", "COMBUSTIVEIS PRIMAVERA",
                    "SEMENTES E INSUMOS CAMPO BELO", "ENERGIA E UTILIDADES BRASIL", "TECNOLOGIA E SISTEMAS ORION"]
    produtores = ["SITIO BOA VISTA - JOSE A. SANTOS", "FAZENDA SAO JOAO - MARIA L. PEREIRA", "SITIO DOIS IRMAOS - CARLOS R. LIMA",
                  "FAZENDA ESPERANCA - ANTONIO B. COSTA", "SITIO RECANTO - LUCIA M. ALVES", "CHACARA PRIMAVERA - PAULO H. DIAS"]
    aprovadores = ["Ana.Souza", "Bruno.Lima", "Carla.Mendes", "Diego.Prado", "Elisa.Ramos"]
    filiais = [(1, "FILIAL MATRIZ"), (2, "FILIAL NORTE"), (3, "FILIAL SUL"), (4, "FILIAL CENTRO")]
    ini_mes = HOJE.replace(day=1)
    linhas, ap = [], 810000
    for i in range(190):
        ap += int(rng.randint(1, 6))
        cod_f, filial = filiais[int(rng.randint(len(filiais)))]
        produtor = rng.rand() < 0.27
        prorr = ini_mes + pd.Timedelta(days=int(rng.randint(0, 75)))
        emissao = prorr - pd.Timedelta(days=int(rng.randint(10, 60)))
        faixa = " | ".join(rng.choice(aprovadores, size=int(rng.randint(1, 4)), replace=False))
        valor = float(np.round(rng.uniform(2.5e3, 1.2e5) if not produtor else rng.uniform(1.5e4, 9.5e4), 2))
        favorecido = f"{3000 + i} - {rng.choice(produtores if produtor else fornecedores)}"
        base = {"COD_ORG": 6, "ORG": "ORGANIZACAO ALFA", "COD_FILIAL": cod_f, "FILIAL": filial, "AP": ap,
                "STATUS": "Em Aprovação", "APROVADORES": faixa, "TP DOC": "NF MAT" if not produtor else "NF PROD",
                "DOC": str(rng.randint(10000, 99999)), "PARC": "001", "FAVORECIDO": favorecido,
                "CLASSIFICACAO": "Produtor" if produtor else "Fornecedor", "EMISSAO": emissao, "ENTRADA": emissao + pd.Timedelta(days=2),
                "PRORROGADO": prorr, "FORMA_PAGTO": str(rng.choice(["Transferência", "Boleto", "PIX"])),
                "COMPLEMENTO": f"Referente ao pedido {rng.randint(1000, 9999)}", "QTD_ANEXOS": int(rng.randint(0, 4))}
        base["STATUS_ANEXO"] = "Anexado" if base["QTD_ANEXOS"] else "Sem Anexo"
        base["ANX_ST_NOME"] = f"nota_{rng.randint(100, 999)}.pdf" if base["QTD_ANEXOS"] else None
        if produtor:   # compra da fruta + INSS Funrural (mesma AP, mesma classificação)
            inss = float(np.round(valor * 0.016, 2))
            linhas.append({**base, "SALDO": valor - inss, "VALOR": valor - inss})
            linhas.append({**base, "SALDO": inss, "VALOR": inss})
        else:
            linhas.append({**base, "SALDO": valor, "VALOR": valor})
    return pd.DataFrame(linhas)


# ── Histórico de pagamentos (perfil de pagamento, Faturamento Cliente/Grupo) ────
def historico_pagamentos(agentes: tuple, externo: bool) -> pd.DataFrame:
    rng = np.random.RandomState(SEMENTE + 9)
    linhas = []
    for agn in agentes:
        rg = np.random.RandomState(SEMENTE + int(agn))
        perfil = rg.choice(["bom", "regular", "mau"], p=[0.55, 0.3, 0.15])
        for k in range(int(rg.randint(30, 70))):
            emissao = HOJE - pd.Timedelta(days=int(rg.randint(20, 1000)))
            prazo = int(rg.choice([30, 45, 60, 90]))
            venc = emissao + pd.Timedelta(days=prazo)
            atraso = {"bom": int(rg.choice([-3, 0, 0, 1, 1, 2])), "regular": int(rg.choice([0, 3, 7, 12, 20])),
                      "mau": int(rg.choice([10, 25, 40, 70, 120]))}[perfil]
            pago = venc + pd.Timedelta(days=atraso)
            aberto = pago > HOJE
            valor = float(np.round(np.exp(rg.normal(11.2, 0.7)), 2))
            linha = {"AGN": int(agn), "DOC": str(30000 + rg.randint(0, 40000)), "PARC": f"{rg.randint(1, 4):03d}",
                     "EMISSAO": emissao, "VENCTO": venc, "PRORROGADO": venc, "VALOR_PARCELA": valor,
                     "SALDO": valor if aberto else 0.0, "DT_PRIM_PAG": pd.NaT if aberto else pago,
                     "DT_ULT_PAG": pd.NaT if aberto else pago, "VALOR_PAGO": 0.0 if aberto else valor}
            if externo:
                cot = 5.4
                linha.update({"MOEDA": "USD", "VALOR_MOEDA": round(valor / cot, 2)})
            else:
                linha.update({"DESCONTO": 0.0, "BAIXA_ADIANT": 0.0})
            linhas.append(linha)
    cols = (["AGN", "DOC", "PARC", "EMISSAO", "VENCTO", "PRORROGADO", "MOEDA", "VALOR_MOEDA", "VALOR_PARCELA", "SALDO",
             "DT_PRIM_PAG", "DT_ULT_PAG", "VALOR_PAGO"] if externo else
            ["AGN", "DOC", "PARC", "EMISSAO", "VENCTO", "PRORROGADO", "VALOR_PARCELA", "SALDO", "DT_PRIM_PAG", "DT_ULT_PAG",
             "VALOR_PAGO", "DESCONTO", "BAIXA_ADIANT"])
    return pd.DataFrame(linhas, columns=cols)
