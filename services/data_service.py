"""
Camada de dados da DEMONSTRAÇÃO: as mesmas funções do painel real (mesmos nomes, argumentos e colunas), mas devolvendo
dados 100% inventados (dados_ficticios*.py), sem banco de dados. Assim o `app.py` e todas as telas copiados do painel real
rodam sem nenhuma alteração.

Para a demo acompanhar uma função nova do painel real: crie a função aqui com o mesmo nome e devolva um DataFrame com as
mesmas colunas da consulta (o gerador fica em dados_ficticios_novos.py).
"""

from __future__ import annotations

import datetime
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import dados_ficticios_novos as nv
from dados_ficticios import gerar, _CLIENTES
from dados_ficticios_extra import gerar_extra

DATA_CORTE_CONTAS_APAGAR = date(2026, 1, 1)
SEGUNDOS_RECARGA = 600


def _data(texto) -> pd.Timestamp:
    """Aceita DD/MM/AAAA, AAAA-MM-DD, date ou Timestamp."""
    if isinstance(texto, (pd.Timestamp, datetime.date)):
        return pd.Timestamp(texto)
    return pd.Timestamp(pd.to_datetime(str(texto), dayfirst="/" in str(texto)))


@st.cache_resource(show_spinner=False)
def _base() -> dict:
    return gerar()


@st.cache_resource(show_spinner=False)
def _extra() -> dict:
    return gerar_extra()


def atualizar_se_antigo(carregador, chave: str, max_segundos: int = SEGUNDOS_RECARGA) -> bool:
    """Na demo não há nada a recarregar do banco."""
    return False


# ── Contas a Receber ───────────────────────────────────────────────────────────
_COLUNAS_CR = [
    "SEMANA", "ANO", "SITUACAO", "MERCADO", "CLASSIFICACAO", "COD_CLIENTE", "CLIENTE", "TIPO_PESSOA", "PAIS", "UF", "ENTRADA",
    "VENCIMENTO", "PRORROGADO", "DIAS", "PARCELA", "TIPO_DOC", "NF", "CONTAINER", "VALOR_FATURADO", "TIPO_REGRA", "PERC_REGRA",
    "DESC_APLIC_NF", "PERC_APLIC_NF", "LIQUIDO_FIN", "DESC_APLIC_FIN", "PERC_APLIC_FIN", "ACRESCIMOS", "DEVOLUCAO",
    "SALDO_EM_ABERTO", "MOEDA", "VLR_PARCELA_MOEDA", "COTACAO", "SALDO_MOEDA", "COMPLEMENTO", "ACAO", "CENTRO_CUSTO",
    "NOSSO_NUMERO", "LINHA_DIGITAVEL", "BANCO_NOME", "SITUACAO_BOLETO", "VENDEDOR", "EMAIL_CLIENTE", "FAIXA_DIAS",
]


def _base_hoje() -> pd.Timestamp:
    return pd.Timestamp(date.today())


def _contas_receber() -> pd.DataFrame:
    cr = _base()["contas_receber"].copy()
    rng = np.random.RandomState(nv.SEMENTE + 20)
    # alguns títulos do Mercado Interno vencidos há mais de 90 dias, para a demo mostrar o PDD
    vencidos_mi = cr.index[(cr["SITUACAO"] == "VENCIDO") & (cr["MERCADO"] == "MI")]
    for i in rng.choice(vencidos_mi, size=min(6, len(vencidos_mi)), replace=False):
        dias = -int(rng.randint(95, 210))
        venc = _base_hoje() + pd.Timedelta(days=dias)
        cr.loc[i, ["DIAS", "VENCIMENTO", "PRORROGADO", "ENTRADA", "FAIXA_DIAS"]] = [dias, venc, venc, venc - pd.Timedelta(days=60), "Vencido 30+ dias"]
        cr.loc[i, ["SEMANA", "ANO"]] = [int(venc.isocalendar()[1]), int(venc.year)]
    cr["PARCELA"] = cr["PARCELA"].astype(int).map(lambda n: f"{n:03d}")
    cr["NF"] = pd.to_numeric(cr["NF"]).astype("int64")
    cr["PRORROGADO"] = cr["PRORROGADO"].fillna(cr["VENCIMENTO"])          # no banco o prorrogado sempre tem valor
    cr["ACAO"] = cr["COD_ACAO"].astype(str) + " - " + cr["NOME_ACAO"].astype(str)
    cr["CENTRO_CUSTO"] = "Comercial 100,00%"
    cr["ACRESCIMOS"], cr["DEVOLUCAO"] = 0.0, 0.0
    cr["PERC_APLIC_NF"] = np.where(cr["DESC_APLIC_NF"].notna(), cr["PERC_REGRA"], None)
    cr["PERC_APLIC_FIN"] = np.where(cr["DESC_APLIC_FIN"].notna(), cr["PERC_REGRA"], None)
    gerado = cr["SITUACAO_BOLETO"].eq("BOLETO GERADO")
    cr["NOSSO_NUMERO"] = [f"{rng.randint(10**9, 10**10 - 1, dtype=np.int64)}" if g else None for g in gerado]
    cr["LINHA_DIGITAVEL"] = [f"3419{rng.randint(10**9, 10**10 - 1, dtype=np.int64)}{rng.randint(10**9, 10**10 - 1, dtype=np.int64)}" if g else None for g in gerado]
    return cr[_COLUNAS_CR].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def carregar_contas_receber() -> pd.DataFrame:
    return _contas_receber()


@st.cache_data(show_spinner=False)
def carregar_contas_receber_com_pagos(data_de: date, data_ate: date) -> pd.DataFrame:
    """Em aberto + pagos do Mercado Interno com vencimento no período (colunas do CR + dados da baixa)."""
    cr = _contas_receber()
    cr = cr[cr["MERCADO"] == "MI"].copy()
    ini, fim = pd.Timestamp(data_de), pd.Timestamp(data_ate)
    abertos = cr[(cr["VENCIMENTO"] >= ini) & (cr["VENCIMENTO"] <= fim)].copy()
    for c in ("DATA_PAGAMENTO", "VALOR_PAGO", "DESCONTO", "BAIXA_ADIANT"):
        abertos[c] = pd.NaT if c == "DATA_PAGAMENTO" else 0.0
    abertos["VALOR_PARCELA"] = abertos["SALDO_EM_ABERTO"]
    b = nv.baixas()
    b = b[(b["VENCIMENTO"] >= ini) & (b["VENCIMENTO"] <= fim)]
    if len(b) > 450:
        b = b.sample(450, random_state=7)
    modelo = cr.sample(len(b), replace=True, random_state=11).reset_index(drop=True) if len(b) else cr.head(0)
    pagos = modelo.copy()
    if len(b):
        b = b.reset_index(drop=True)
        pagos["COD_CLIENTE"], pagos["CLIENTE"] = b["AGN"].values, b["CLIENTE"].values
        pagos["NF"], pagos["PARCELA"] = pd.to_numeric(b["DOC"]).astype("int64").values, b["PARC"].values
        pagos["ENTRADA"], pagos["VENCIMENTO"], pagos["PRORROGADO"] = b["EMISSAO"].values, b["VENCIMENTO"].values, b["VENCIMENTO"].values
        pagos["SALDO_EM_ABERTO"], pagos["DIAS"], pagos["SITUACAO"] = 0.0, np.nan, "PAGO"
        pagos["DATA_PAGAMENTO"], pagos["VALOR_PAGO"] = b["DIA"].values, b["VALOR_PAGO"].values
        pagos["DESCONTO"], pagos["BAIXA_ADIANT"], pagos["VALOR_PARCELA"] = 0.0, 0.0, b["VALOR_PAGO"].values
        pagos["BANCO_NOME"] = "Santander"
    return pd.concat([abertos, pagos], ignore_index=True)


@st.cache_data(show_spinner=False)
def carregar_variacao_cambial_me() -> pd.DataFrame:
    cr = _contas_receber()
    return cr[cr["MERCADO"] == "ME"].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def carregar_historico_pagamentos_mi(agentes: tuple) -> pd.DataFrame:
    return nv.historico_pagamentos(tuple(agentes), externo=False)


@st.cache_data(show_spinner=False)
def carregar_historico_pagamentos_me(agentes: tuple) -> pd.DataFrame:
    return nv.historico_pagamentos(tuple(agentes), externo=True)


@st.cache_data(show_spinner=False)
def carregar_notas_pendentes_validacao():
    """Pendências das notas bloqueadas ou em validação manual (uma linha por documento que bloqueia), inventadas: o cliente 1102 tem 3
    notas bloqueantes, o 1104 tem 2 em validação manual e o 1302 tem 2 bloqueantes e 3 em validação manual. Cada nota traz os
    documentos que bloqueiam (CNH, nota fiscal com canhoto, carta de temperatura e, às vezes, aceite do pedido) em estados diferentes:
    vencido (2), validando (1), não anexado (0) ou regularizado (3)."""
    hoje = pd.Timestamp(date.today())
    rng = np.random.RandomState(nv.SEMENTE + 40)
    docs = [("CNH", "CNH do motorista"), ("NFCANHOTO", "Nota fiscal com canhoto"), ("CARTATEMP", "Carta de temperatura"),
            ("ACEITEPED", "Aceite do Pedido de Venda")]
    linhas, nf = [], 61200
    for cod, tipo, n in [(1102, "bloq", 3), (1104, "manual", 2), (1302, "bloq", 2), (1302, "manual", 3), (1104, "avencer", 2), (1302, "avencer", 1)]:
        for _ in range(n):
            nf += int(rng.randint(3, 30))
            controle = f"CTV-2026-{nf + 3000:06d}"
            qtd = int(rng.randint(2, 4)) + (1 if rng.rand() < 0.25 else 0)
            idx = list(rng.choice(len(docs), size=min(qtd, len(docs)), replace=False))
            prazo = hoje + pd.Timedelta(days=int(rng.randint(-4, -1)) if tipo == "bloq" else int(rng.randint(1, 8)))
            for k, i in enumerate(idx):
                codigo, nome = docs[i]
                doc_status = None                       # sem documento anexado
                anexado = validado = pd.NaT
                if tipo == "avencer":
                    status, bloqueia, motivo = 0, 0, f"Documento obrigatório {nome} ainda não foi anexado ao checklist."
                elif k == 0 and tipo == "bloq":
                    # prazo vencido e bloqueando: o documento pode estar inválido ou ainda em validação (anexado, aguardando revisão)
                    status, bloqueia, motivo = 2, 1, f"Documento {nome} aguardando conclusão da validação OCR/revisão. Prazo documental vencido."
                    doc_status = 2 if rng.rand() < 0.5 else 0
                    anexado = prazo + pd.Timedelta(hours=int(rng.randint(-60, 72)))      # às vezes antes, às vezes depois do prazo
                elif k == 0:
                    status, bloqueia, motivo = 1, 0, f"Documento {nome} aguardando conclusão da validação OCR/revisão."
                    doc_status = 0
                    anexado = hoje - pd.Timedelta(hours=int(rng.randint(2, 70)))
                elif rng.rand() < 0.5:
                    status, bloqueia, motivo = 3, 0, f"Documento {nome} validado."
                else:
                    status, bloqueia, motivo = 0, 0, f"Documento obrigatório {nome} ainda não foi anexado ao checklist."
                linhas.append({"COD_CLIENTE": cod, "CONTROLE": controle, "NF": str(nf), "STATUS": status, "BLOQUEIA": bloqueia,
                               "PRAZO": prazo, "EMISSAO": prazo - pd.Timedelta(days=7), "MOTIVO": motivo, "DOC_CODIGO": codigo, "DOCUMENTO": nome, "DOC_STATUS": doc_status,
                               "ANEXADO_EM": anexado, "VALIDADO_EM": validado, "NOTA_BLOQ": int(tipo == "bloq"), "NOTA_MANUAL": int(tipo == "manual"), "NOTA_AVENCER": int(tipo == "avencer")})
            # o Pedido de venda (não bloqueia) aparece como Válido, gerado automaticamente
            linhas.append({"COD_CLIENTE": cod, "CONTROLE": controle, "NF": str(nf), "STATUS": 3, "BLOQUEIA": 0, "PRAZO": pd.NaT, "EMISSAO": prazo - pd.Timedelta(days=7),
                           "MOTIVO": "Pedido de venda gerado automaticamente pelo MEGA/SyncProcess", "DOC_CODIGO": "PEDVENDA",
                           "DOCUMENTO": "Pedido de venda", "DOC_STATUS": 1,
                           "ANEXADO_EM": hoje - pd.Timedelta(days=int(rng.randint(3, 9))), "VALIDADO_EM": hoje - pd.Timedelta(days=int(rng.randint(2, 8))), "NOTA_BLOQ": int(tipo == "bloq"), "NOTA_MANUAL": int(tipo == "manual"),
                       "NOTA_AVENCER": int(tipo == "avencer")})
    # Aceite da carga (regra obrigatória que não bloqueia): em várias notas aparece sem anexo, em validação ou válido
    rng_c = np.random.RandomState(nv.SEMENTE + 42)
    extras = []
    for (cod, controle, nf_), g in pd.DataFrame(linhas).groupby(["COD_CLIENTE", "CONTROLE", "NF"], sort=False):
        sorteio = rng_c.rand()
        if sorteio < 0.2:
            continue                                         # a nota ainda não tem essa regra
        status, doc_status = (0, None) if sorteio < 0.55 else (1, 0) if sorteio < 0.8 else (3, 1)
        extras.append({"COD_CLIENTE": cod, "CONTROLE": controle, "NF": nf_, "STATUS": status, "BLOQUEIA": 0, "PRAZO": g["PRAZO"].max(),
                       "EMISSAO": g["EMISSAO"].max(), "MOTIVO": "Evidência do aceite da carga", "DOC_CODIGO": "ACEITECARGA",
                       "DOCUMENTO": "Evidencia do aceite da carga", "DOC_STATUS": doc_status,
                       "ANEXADO_EM": (hoje - pd.Timedelta(hours=int(rng_c.randint(2, 60)))) if status else pd.NaT, "VALIDADO_EM": pd.NaT,
                       "NOTA_BLOQ": int(g["NOTA_BLOQ"].max()), "NOTA_MANUAL": int(g["NOTA_MANUAL"].max()), "NOTA_AVENCER": int(g["NOTA_AVENCER"].max())})
    df = pd.DataFrame(linhas + extras)
    df["COD_CLIENTE"] = df["COD_CLIENTE"].astype("Int64")
    return df


@st.cache_data(show_spinner=False)
def carregar_controles_abertos_mi():
    """Controles de venda abertos (COD_CLIENTE, CONTROLE, NF), inventados: os clientes bloqueados 1101 e 1103 têm controles abertos;
    os demais também, para o painel mostrar só quem está bloqueado."""
    rng = np.random.RandomState(nv.SEMENTE + 41)
    linhas, nf = [], 61500
    for cod, n in [(1101, 5), (1103, 2), (1102, 2), (1104, 1), (1302, 3)]:
        for _ in range(n):
            nf += int(rng.randint(3, 25))
            linhas.append({"COD_CLIENTE": cod, "CONTROLE": f"CTV-2026-{nf + 3000:06d}", "NF": str(nf)})
    df = pd.DataFrame(linhas)
    df["COD_CLIENTE"] = df["COD_CLIENTE"].astype("Int64")
    return df


@st.cache_data(show_spinner=False)
def carregar_pedidos_em_validacao():
    """Pedidos ainda sem nota com o pedido de compra do cliente ou o aceite do pedido pendente/inválido (COD_CLIENTE, CONTROLE, PEDIDO,
    DOC_CODIGO, DOCUMENTO, STATUS, DOC_STATUS, MOTIVO, GERADA), inventados."""
    hoje = pd.Timestamp(date.today())
    ped = "Documento obrigatório Pedido de Compra - Cliente ainda não foi anexado ao checklist."
    itens = [(1104, "PEDCOMPRA", "Pedido de Compra - Cliente", 1, 0, ped, 16),      # anexado, em validação: aparece
             (1302, "PEDCOMPRA", "Pedido de Compra - Cliente", 0, None, ped, 0),    # sem anexo: não aparece (nada a validar)
             (1103, "PEDCOMPRA", "Pedido de Compra - Cliente", 1, 0, ped, 9)]
    linhas = []
    for i, (cod, dc, nome, st_, ds, mot, dias) in enumerate(itens):
        linhas.append({"COD_CLIENTE": cod, "CONTROLE": f"CTV-2026-{4100 + i * 37:06d}", "PEDIDO": 21000 + i * 211, "DOC_CODIGO": dc, "DOCUMENTO": nome,
                       "STATUS": st_, "DOC_STATUS": ds, "MOTIVO": mot, "GERADA": hoje - pd.Timedelta(days=dias)})
    df = pd.DataFrame(linhas)
    df["COD_CLIENTE"] = df["COD_CLIENTE"].astype("Int64")
    return df


@st.cache_data(show_spinner=False)
def carregar_tratativas_pendentes():
    """Reclamações de clientes em andamento, cada uma na sua etapa (COD_CLIENTE, CONTROLE, NF, REGISTRO, PROCEDE, QUALIDADE_CONCLUIDA, TIPO, NF_DEVOLUCAO,
    VALOR, TOTAL_NF, APROVACAO, DEFINIDA, APROVADA, RECLAMACAO), inventadas."""
    hoje = pd.Timestamp(date.today()).replace(hour=10, minute=30)
    d = pd.Timedelta
    nt = pd.NaT
    def linha(cod, ctrl, nf, reg, proc, qual, tipo, valor, aprov, defin, aprovada, rec):
        return {"COD_CLIENTE": cod, "CONTROLE": ctrl, "NF": nf, "REGISTRO": hoje - d(days=reg), "PROCEDE": proc,
                "QUALIDADE_CONCLUIDA": nt if qual is None else hoje - d(days=qual), "TIPO": tipo, "NF_DEVOLUCAO": None, "VALOR": valor,
                "TOTAL_NF": round((valor or 3000.0) * 1.8 + 1000, 2), "APROVACAO": aprov, "DEFINIDA": nt if defin is None else hoje - d(days=defin),
                "APROVADA": nt if aprovada is None else hoje - d(days=aprovada), "RECLAMACAO": rec}
    df = pd.DataFrame([
        linha(1001, "CTV-2026-000762", "48001", 27, 1, 27, 3, 9900.0, 681, 26, None, 221),
        linha(1001, "CTV-2026-003322", "48007", 13, 1, 12, 3, 7238.0, 861, 7, None, 243),
        linha(1105, "CTV-2026-003347", "48020", 8, 1, 1, 2, 2200.0, 901, 0, None, 281),
        linha(1103, "CTV-2026-003354", "48031", 7, 1, 5, None, None, None, None, None, 283),
        linha(1104, "CTV-2026-003360", "48044", 3, 1, 1, None, None, None, None, None, 284),
        linha(1103, "CTV-2026-002521", "59147", 20, None, None, None, None, None, None, None, 201),
        linha(1104, "CTV-2026-003324", "60348", 11, 1, 11, 3, 5400.0, 821, 10, 6, 261),
        linha(1103, "CTV-2026-002266", "58611", 18, 1, 17, 2, 648.0, 581, 14, 9, 182),
        linha(1104, "CTV-2026-002084", "58849", 25, 1, 24, 2, 4730.0, 661, 20, 18, 181),
        linha(1105, "CTV-2026-003401", "48090", 9, 0, 8, None, None, None, None, None, 290)])
    df["COD_CLIENTE"] = df["COD_CLIENTE"].astype("Int64")
    return df


@st.cache_data(show_spinner=False)
def carregar_pendencias_bloqueantes():
    """Notas com pendência por cliente (COD_CLIENTE, QTD_BLOQUEANTES, PRAZO_BLOQUEIO, QTD_MANUAL, PRAZO_MANUAL), calculadas das
    mesmas notas fictícias do gráfico, para o card e o gráfico sempre baterem."""
    d = carregar_notas_pendentes_validacao()
    notas = d.groupby(["COD_CLIENTE", "CONTROLE", "NF"], as_index=False).agg(
        bloq=("NOTA_BLOQ", "max"), manual=("NOTA_MANUAL", "max"))
    saida = []
    for cod, g in notas.groupby("COD_CLIENTE"):
        linhas = d[d["COD_CLIENTE"] == cod]
        bl = linhas[linhas["BLOQUEIA"] == 1]["PRAZO"].min()
        ma = linhas[(linhas["STATUS"] == 1) & (linhas["NOTA_BLOQ"] == 0)]["PRAZO"].min()
        saida.append({"COD_CLIENTE": cod, "QTD_BLOQUEANTES": int((g["bloq"] == 1).sum()), "PRAZO_BLOQUEIO": bl,
                      "QTD_MANUAL": int(((g["bloq"] == 0) & (g["manual"] == 1)).sum()), "PRAZO_MANUAL": ma})
    out = pd.DataFrame(saida)
    out["COD_CLIENTE"] = out["COD_CLIENTE"].astype("Int64")
    return out


@st.cache_data(show_spinner=False)
def carregar_regra_desconto_cliente(codigo: int):
    cr = _base()["contas_receber"]
    x = cr[(cr["COD_CLIENTE"] == int(codigo)) & cr["TIPO_REGRA"].notna()]
    if x.empty:
        return None
    return x.iloc[0]["TIPO_REGRA"], float(str(x.iloc[0]["PERC_REGRA"]).replace("%", ""))


@st.cache_data(show_spinner=False)
def carregar_classes_desconto(nfs: tuple, clientes: tuple) -> pd.DataFrame:
    return nv.classes_desconto(tuple(nfs), tuple(clientes))


# ── Recebimentos ───────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def carregar_recebimento_hoje_mi() -> dict:
    return nv.recebimento_hoje()


@st.cache_data(show_spinner=False)
def carregar_recebido_periodo_mi(inicio: date, fim: date) -> pd.DataFrame:
    b = nv.baixas()
    b = b[(b["DIA"] >= pd.Timestamp(inicio)) & (b["DIA"] <= pd.Timestamp(fim))]
    return b[["DIA", "DOC", "AGN", "CLIENTE", "BANCO", "PARC", "VALOR_PAGO", "VENCIMENTO"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def carregar_recebido_mensal_mi(ano: int) -> pd.DataFrame:
    b = nv.baixas()
    b = b[(b["DIA"] >= pd.Timestamp(ano - 1, 1, 1)) & (b["DIA"] <= pd.Timestamp(ano, 12, 31))]
    return b[["DIA", "DOC", "AGN", "PARC", "VALOR_PAGO", "EMISSAO"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def carregar_recebido_banco_mes_mi(ano: int) -> pd.DataFrame:
    b = nv.baixas()
    b = b[(b["DIA"] >= pd.Timestamp(ano, 1, 1)) & (b["DIA"] <= pd.Timestamp(ano, 12, 31))]
    g = b.groupby([b["DIA"].dt.month.rename("MES"), "BANCO"], as_index=False)["VALOR_PAGO"].sum()
    g.columns = ["MES", "BANCO", "VALOR"]
    g["MES"] = g["MES"].astype("Int64")
    return g


@st.cache_data(show_spinner=False)
def carregar_organizacoes_recebimentos() -> pd.DataFrame:
    return pd.DataFrame(nv._ORGS, columns=["ORG", "NOME"])


@st.cache_data(show_spinner=False)
def carregar_recebimentos(data_inicio: str, data_fim: str, orgs: tuple = (6,), *args, **kwargs) -> pd.DataFrame:
    return nv.recebimentos_por_banco(_data(data_inicio), _data(data_fim), tuple(orgs))


# ── Faturamento e vendas ───────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def carregar_total_faturado_cliente(*args, **kwargs) -> pd.DataFrame:
    return _base()["faturado"].copy()


@st.cache_data(show_spinner=False)
def carregar_faturado_mensal_cliente() -> pd.DataFrame:
    m = _base()["faturado_mensal"].copy()
    uf = {c[0]: c[3] for c in _CLIENTES}
    m["UF"] = m["COD_CLIENTE"].map(uf)
    return m[["COD_CLIENTE", "UF", "ANO", "MES", "VALOR_TOTAL_FATURADO"]]


def _ultimos_meses(df: pd.DataFrame, n: int) -> pd.DataFrame:
    chave = df["ANO"] * 12 + df["MES"]
    return df[chave > chave.max() - n]


@st.cache_data(show_spinner=False)
def carregar_faturado_mensal_mi() -> pd.DataFrame:
    v = nv.vendas_dia_vendedor()
    g = v.groupby([v["DIA"].dt.year.rename("ANO"), v["DIA"].dt.month.rename("MES")], as_index=False)["VALOR_TOTAL_FATURADO"].sum()
    return _ultimos_meses(g, 13).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def carregar_faturado_mensal_vendedor_mi() -> pd.DataFrame:
    v = nv.vendas_dia_vendedor()
    g = v.groupby([v["DIA"].dt.year.rename("ANO"), v["DIA"].dt.month.rename("MES"), "VENDEDOR"], as_index=False).agg(
        QTD_NOTAS=("QTD_NOTAS", "sum"), VALOR_TOTAL_FATURADO=("VALOR_TOTAL_FATURADO", "sum"))
    return _ultimos_meses(g, 13).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def carregar_vendas_dia_vendedor_mi() -> pd.DataFrame:
    return nv.vendas_dia_vendedor()


@st.cache_data(show_spinner=False)
def carregar_notas_vendidas_mi(data_ini: str) -> pd.DataFrame:
    return nv.notas_vendidas(data_ini)


# ── Grupo de Crédito e adiantamentos ───────────────────────────────────────────
@st.cache_data(show_spinner=False)
def carregar_grupo_credito_geral() -> pd.DataFrame:
    g = _base()["grupo_geral"].copy()
    g["GRUPO_CODIGO"] = g["GRUPO_CODIGO"].astype(str)
    return g


@st.cache_data(show_spinner=False)
def carregar_grupo_credito_saldo_agente() -> pd.DataFrame:
    a = _base()["grupo_agentes"].copy()
    a["COD_GRUPO"] = a["COD_GRUPO"].astype(str)
    rng = np.random.RandomState(nv.SEMENTE + 30)
    a["CNPJ"] = [f"{rng.randint(10, 99)}.{rng.randint(100, 999)}.{rng.randint(100, 999)}/0001-{rng.randint(10, 99)}" for _ in range(len(a))]
    return a[["COD_GRUPO", "COD_AGENTE", "NOME_AGENTE", "CNPJ", "TIPO_PESSOA", "UF", "PAIS", "LIMITE_DO_GRUPO",
              "CONSUMIDO_EM_PV", "CONSUMIDO_EM_NF"]]


@st.cache_data(show_spinner=False)
def carregar_adiantamento_geral() -> pd.DataFrame:
    return nv.adiantamentos()[0]


@st.cache_data(show_spinner=False)
def carregar_adiantamento_total_agente() -> pd.DataFrame:
    return nv.adiantamentos()[1]


@st.cache_data(show_spinner=False)
def carregar_adiantamento_saldo_agente() -> pd.DataFrame:
    return nv.adiantamentos()[2]


@st.cache_data(show_spinner=False)
def carregar_lista_clientes() -> pd.DataFrame:
    return pd.DataFrame([(c[0], c[1]) for c in _CLIENTES], columns=["COD_CLIENTE", "CLIENTE"])


# ── Contas a Pagar, aprovação e relatórios ─────────────────────────────────────
_COLUNAS_ERRO = ["ORGANIZACAO", "COD_FILIAL", "NOME_FILIAL", "SEGMENTO", "ORIGEM", "CATEGORIA_ERRO", "AP", "DOCUMENTO", "TIPO", "COD_AGENTE",
                 "TIPO_AGENTE", "NOME_AGENTE", "DATA", "SALDO", "TIPO_ACAO", "COD_ACAO", "ACAO", "CLASSE", "CENTRO_CUSTO",
                 "SOLICITANTE", "NUM_LANCTO"]


@st.cache_data(show_spinner=False)
def carregar_conferencia_matriz_filial(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Conferência Matriz x Filial (conhecimentos e adiantamentos) do período, inventada: um par (efetuado e recebido) por lançamento, com pendências,
    OK e aguardando pagamento, já na ordem da tela (pendências no topo)."""
    ini, fim = pd.to_datetime(data_inicio, format="%d/%m/%Y"), pd.to_datetime(data_fim, format="%d/%m/%Y")
    dias = max((fim - ini).days, 1)
    rng = np.random.RandomState(nv.SEMENTE + 71)
    org_i, org_p, fav_p, fav_i = "AGRÍCOLA DEMONSTRAÇÃO COMÉRCIO E EXPORTAÇÃO LTDA", "TRANSPORTADORA DEMONSTRAÇÃO - CONSOLIDADORA", "TRANSPORTADORA DEMONSTRAÇÃO LTDA", "AGRÍCOLA DEMONSTRAÇÃO COMÉRCIO E EXPORTAÇÃO LTDA"
    casos = [("Conhecimento", "OK")] * 4 + [("Conhecimento", "AGUARDANDO")] * 4 + [("Conhecimento", "FALTA_BAIXA"), ("Conhecimento", "DIA_DIFERENTE"),
             ("Adiantamento", "OK"), ("Adiantamento", "OK"), ("Adiantamento", "AGUARDANDO"), ("Adiantamento", "FALTA_981"), ("Adiantamento", "DIF_CC"), ("Adiantamento", "DIF_PROJETO")]
    grupos = []
    docto, ap = 2100, 400100
    for grupo, caso in casos:
        d = ini + pd.Timedelta(days=int(rng.randint(0, dias + 1)))
        valor = round(float(rng.uniform(4000, 60000)), 2)
        docto += int(rng.randint(1, 9))
        ap += int(rng.randint(1, 30))
        cte = grupo == "Conhecimento"
        v = f"R$ {valor:.2f}".replace(".", ",")
        cl_i, cl_p = f"1721 - Fretes - Mot - 100% - {v}", f"1722 - Adiantamento de Clientes - 100% - {v}"
        cc, pj = f"73 - PRODUÇÃO DEMONSTRAÇÃO - 100% - {v}", f"520 - FRETES - MOT - 100% - {v}"
        if cte:
            cl_i, cl_p = f"1237 - Receita de Frete - 100% - {v}", f"109 - Receita de Prestação de Serviço - 100% - {v}"
            cc_p, pj_p = f"303 - OPERACIONAL DEMONSTRAÇÃO - 100% - {v}", f"74 - APOIO OPERACIONAL - 100% - {v}"
        else:
            cc_p, pj_p = cc, pj
        aberto_ef = caso in ("AGUARDANDO",)
        ef = [grupo, "Efetuado", org_i, "CONHEC" if cte else "ADIANT", ap, str(docto) if cte else "2411" + str(docto), fav_p, valor, valor if aberto_ef else 0.0,
              "EM ABERTO" if aberto_ef else "BAIXADO", None if (cte and aberto_ef) else d, "393 - RURAL - Conhecimento de frete Externo (Sem pedido)" if cte else
              "55 - GERAL - Provisão Adiantamento a Fornecedores", cl_i, cc, pj, "USUARIO.DEMO", "OK"]
        rc = None
        if caso in ("OK", "FALTA_BAIXA", "DIA_DIFERENTE", "DIF_CC", "DIF_PROJETO") or (cte and caso == "AGUARDANDO"):
            aberto_rc = caso in ("AGUARDANDO", "FALTA_BAIXA")
            dt_rc = None if aberto_rc else (d + pd.Timedelta(days=2) if caso == "DIA_DIFERENTE" else d)
            rc = [grupo, "Recebido", org_p, "CRECEBER" if cte else "AV DÉB", None, ef[5] if cte else str(515000 + docto), fav_i, valor, valor if aberto_rc else 0.0,
                  "EM ABERTO" if aberto_rc else "BAIXADO", dt_rc, "905 - COMERCIAL- Provisão Contas a Receber" if cte else "981 - GERAL - Adiantamento de Clientes (ENTRADA)",
                  cl_p, cc_p if caso != "DIF_CC" else f"54 - PACKING DEMONSTRAÇÃO - 100% - {v}", pj_p, None, "OK"]
        conf = {"OK": "OK", "AGUARDANDO": "AGUARDANDO PAGAMENTO NA MATRIZ", "FALTA_BAIXA": "FALTA BAIXAR NA FILIAL", "DIA_DIFERENTE": "BAIXA EM DIA DIFERENTE",
                "FALTA_981": "FALTA LANÇAR O 981", "DIF_CC": "DIFERENTE: CENTRO DE CUSTO", "DIF_PROJETO": "DIFERENTE: PROJETO FORA DO PADRÃO (520)"}[caso]
        if caso == "DIF_PROJETO":
            ef[14] = f"521 - OUTRO PROJETO - 100% - {v}"
            rc[14] = ef[14]
        cat = "OK" if conf == "OK" else "AGUARDANDO" if caso == "AGUARDANDO" else "PENDENCIA"
        grupos.append((cat, 0 if cte else 1, d, [ef] + ([rc] if rc else []), conf))
    ordem = {"PENDENCIA": 0, "OK": 1, "AGUARDANDO": 2}
    grupos.sort(key=lambda g: (ordem[g[0]], g[1], g[2]))
    linhas = []
    for gid, (cat, _, _, par, conf) in enumerate(grupos):
        for r in par:
            linhas.append([gid] + r[:-1] + [conf, cat])
    cols = ["GRUPO_ID", "GRUPO", "LADO", "ORG", "TIPO_DOCTO", "AP", "DOCTO", "FAVORECIDO", "VALOR", "SALDO", "STATUS", "DATA", "ACAO", "RATEIO_CLASSES",
            "RATEIO_CENTRO_CUSTO", "RATEIO_PROJETO", "SOLICITANTE", "CONFERENCIA", "CATEGORIA"]
    return pd.DataFrame(linhas, columns=cols)


@st.cache_data(show_spinner=False)
def carregar_organizacoes_conciliacao() -> pd.DataFrame:
    """Organizações do filtro da tela Pendências de Conciliação (COD_ORG, ORGANIZACAO), inventadas."""
    return pd.DataFrame({"COD_ORG": [6, 25, 42500], "ORGANIZACAO": ["AGRÍCOLA DEMONSTRAÇÃO - CONSOLIDADORA FISCAL", "TECNOLOGIA DEMONSTRAÇÃO - CONSOLIDADORA FISCAL",
                                                                   "TRANSPORTADORA DEMONSTRAÇÃO - CONSOLIDADORA"]})


@st.cache_data(show_spinner=False)
def carregar_contas_conciliacao() -> pd.DataFrame:
    """Contas por organização do filtro Conta da tela Pendências de Conciliação (COD_ORG, COD_BANCO, CONTA), inventadas."""
    linhas = [(6, 101, "BANCO ALFA - AG 0001 CC 12345-6"), (6, 102, "BANCO BETA - AG 0002 CC 23456-7"), (6, 103, "BANCO GAMA - AG 0003 CC 34567-8"),
              (25, 201, "BANCO ALFA - AG 0001 CC 45678-9"), (25, 202, "BANCO DELTA - AG 0004 CC 56789-0"), (42500, 301, "BANCO BETA - AG 0002 CC 67890-1")]
    return pd.DataFrame(linhas, columns=["COD_ORG", "COD_BANCO", "CONTA"])


@st.cache_data(show_spinner=False)
def carregar_pendencias_conciliacao(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Lançamentos do extrato ainda não conciliados (COD_ORG, ORGANIZACAO, COD_FILIAL, FILIAL, COD_BANCO, CONTA, DATA, DOCTO_BANCO, TIPO_DOCTO, HISTORICO,
    VALOR, NATUREZA, DATA_IMPORTACAO), inventados, só do período escolhido (datas DD/MM/AAAA)."""
    rng = np.random.RandomState(nv.SEMENTE + 57)
    hoje = pd.Timestamp(date.today()).normalize()
    empresas = [(6, "AGRÍCOLA DEMONSTRAÇÃO - CONSOLIDADORA FISCAL", 1, "AGRÍCOLA DEMONSTRAÇÃO MATRIZ",
                 [(101, "BANCO ALFA - AG 0001 CC 12345-6", 18), (102, "BANCO BETA - AG 0002 CC 23456-7", 9), (103, "BANCO GAMA - AG 0003 CC 34567-8", 4)]),
                (25, "TECNOLOGIA DEMONSTRAÇÃO - CONSOLIDADORA FISCAL", 1, "TECNOLOGIA DEMONSTRAÇÃO MATRIZ",
                 [(201, "BANCO ALFA - AG 0001 CC 45678-9", 26), (202, "BANCO DELTA - AG 0004 CC 56789-0", 7)]),
                (42500, "TRANSPORTADORA DEMONSTRAÇÃO - CONSOLIDADORA", 42501, "TRANSPORTADORA DEMONSTRAÇÃO LTDA",
                 [(301, "BANCO BETA - AG 0002 CC 67890-1", 11)])]
    hist = [("AV DÉB", "104", "TAR EXT EL", "D", 1.2, 30), ("AV DÉB", "108", "CAMBIO AP-298247", "D", 1000, 90000), ("AV DÉB", "105", "DB JUROS ACC/ACE", "D", 6000, 14000),
            ("PGELETR", "112", "PGTO FORNECEDORES - TRIB", "D", 40000, 600000), ("DOC D", "209", "PIX RECEBIDO DADOS CONTA", "C", 5000, 400000),
            ("COBELET", "202", "COB COMPE", "C", 1000, 20000), ("TRANSF", "213", "PIX RECEB - 056.452.434-47", "C", 300, 9000)]
    linhas = []
    for cod, org, fil, nfil, contas in empresas:
        for cb, conta, n in contas:
            for _ in range(n):
                tp, db, hs, nat, vmin, vmax = hist[rng.randint(len(hist))]
                dt = hoje - pd.Timedelta(days=int(rng.randint(0, 28)))
                imp = pd.NaT if rng.rand() < 0.12 else dt + pd.Timedelta(days=1, hours=3, minutes=int(rng.randint(40, 59)))
                linhas.append({"COD_ORG": cod, "ORGANIZACAO": org, "COD_FILIAL": fil, "FILIAL": nfil, "COD_BANCO": cb, "CONTA": conta, "DATA": dt, "DOCTO_BANCO": db,
                               "TIPO_DOCTO": tp, "HISTORICO": hs, "VALOR": round(float(rng.uniform(vmin, vmax)), 2), "NATUREZA": "Crédito" if nat == "C" else "Débito",
                               "DATA_IMPORTACAO": imp})
    df = pd.DataFrame(linhas).sort_values(["COD_ORG", "COD_BANCO", "DATA"]).reset_index(drop=True)
    ini, fim = pd.to_datetime(data_inicio, format="%d/%m/%Y"), pd.to_datetime(data_fim, format="%d/%m/%Y")
    return df[(df["DATA"] >= ini) & (df["DATA"] <= fim)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def carregar_aps_erro(data_inicio: str, data_fim: str) -> pd.DataFrame:
    e = _extra()["erros"].copy()
    ini, fim = pd.to_datetime(data_inicio, format="%d/%m/%Y"), pd.to_datetime(data_fim, format="%d/%m/%Y")
    e = e[(pd.to_datetime(e["DATA"]) >= ini) & (pd.to_datetime(e["DATA"]) <= fim)].reset_index(drop=True)
    rng = np.random.RandomState(nv.SEMENTE + 31)
    e = e.rename(columns={"ORGANIZAÇÃO": "ORGANIZACAO", "CÓD_FILIAL": "COD_FILIAL"})
    e["ORGANIZACAO"] = 6
    e["SEGMENTO"] = rng.choice(["COMERCIAL", "INDUSTRIAL", "ADMINISTRATIVO"], size=len(e))
    e["TIPO"] = "NF"
    e["ORIGEM"] = rng.choice(["CONTAS A PAGAR", "MOVIMENTO FINANCEIRO", "CONTAS A RECEBER"], size=len(e))
    e["COD_AGENTE"] = 3000 + np.arange(len(e))
    e["TIPO_AGENTE"] = "FORNECEDOR"
    e["AP"] = e["AP"].astype(float)
    return e[_COLUNAS_ERRO]


@st.cache_data(show_spinner=False)
def carregar_relatorio_approvo() -> pd.DataFrame:
    return nv.aprovacoes()


@st.cache_data(show_spinner=False)
def carregar_contas_apagar(data_corte: str = DATA_CORTE_CONTAS_APAGAR.isoformat()) -> pd.DataFrame:
    c = _extra()["contas_pagar"].copy()
    c = c.rename(columns={"NOME_ANEXO": "ANX_ST_NOME"})
    c["CATEGORIA_ERRO"] = c["CATEGORIA_ERRO"].astype(object)
    cols = ["ORG", "FILIAL", "AP", "APROVACAO", "APROVADORES", "DOCTO", "PARC", "TIPO_DOCTO", "TIPO_FAVORECIDO", "TIPO_CLASSIFICACAO",
            "FAVORECIDO", "VALOR", "SALDO", "STATUS", "DIAS", "STATUS_DIAS", "FAIXA_DIAS", "EMISSAO", "ENTRADA", "PRORROGADO",
            "FORMA_PAGTO", "PIX", "LINHA_DIGITAVEL", "COMPLEMENTO", "ACAO", "RATEIO_CLASSES", "RATEIO_CENTRO_CUSTO",
            "RATEIO_PROJETO", "CATEGORIA_ERRO", "SOLICITANTE", "STATUS_ANEXO", "QTD_ANEXOS", "ANX_ST_NOME"]
    return c[cols]


@st.cache_data(show_spinner=False)
def carregar_boletos_dda() -> pd.DataFrame:
    x = _extra()["boletos_dda"]
    rng = np.random.RandomState(nv.SEMENTE + 32)
    n = len(x)
    return pd.DataFrame({
        "BOL_IN_SEQUENCIA": np.arange(1, n + 1), "BOL_ST_NOSSONUMERO": x["NOSSO_NUMERO"].values,
        "BOL_RE_VALOR": x["VALOR"].values, "BOL_ST_SACADO": x["SACADO"].values, "BOL_ST_CNPJ": x["CNPJ"].values,
        "BOL_DT_VENCIMENTO": x["DT_VENCIMENTO"].values, "BOL_ST_NUMTITULO": x["NUM_TITULO"].values,
        "BOL_ST_DOCUMENTO": x["DOCUMENTO"].values, "BOL_ST_CODBARRAS": [f"34191{rng.randint(10**9, 10**10 - 1, dtype=np.int64)}" for _ in range(n)],
        "BOL_ST_ARQORIGEM": "DDA_DEMO.RET", "BOL_ST_MOTIVO": x["MOTIVO"].values, "BOL_IN_LOCMEGA": None,
        "AGN_IN_CODIGO": np.nan, "ORG_TAB_IN_CODIGO": np.nan, "ORG_PAD_IN_CODIGO": np.nan, "ORG_IN_CODIGO": np.nan,
        "ORG_TAU_ST_CODIGO": None, "MOV_TAB_IN_CODIGO": np.nan, "MOV_SEQ_IN_CODIGO": np.nan, "MOV_IN_NUMLANCTO": np.nan,
        "BOL_DT_OPERACAO": x["DT_VENCIMENTO"].values,
    })


@st.cache_data(show_spinner=False)
def carregar_descontos_operacionais_mi(data_inicio: str, data_fim: str) -> pd.DataFrame:
    return nv.descontos_operacionais(_data(data_inicio), _data(data_fim))


@st.cache_data(show_spinner=False)
def carregar_fretes_mot_matriz_filial(data_inicio: str, data_fim: str) -> pd.DataFrame:
    return nv.fretes_mot(_data(data_inicio), _data(data_fim))
