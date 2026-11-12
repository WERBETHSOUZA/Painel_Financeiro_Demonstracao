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
_COLUNAS_ERRO = ["ORGANIZACAO", "COD_FILIAL", "NOME_FILIAL", "SEGMENTO", "CATEGORIA_ERRO", "AP", "DOCUMENTO", "TIPO", "COD_AGENTE",
                 "TIPO_AGENTE", "NOME_AGENTE", "DATA", "SALDO", "TIPO_ACAO", "COD_ACAO", "ACAO", "CLASSE", "CENTRO_CUSTO",
                 "SOLICITANTE", "NUM_LANCTO"]


@st.cache_data(show_spinner=False)
def carregar_aps_erro() -> pd.DataFrame:
    e = _extra()["erros"].copy()
    rng = np.random.RandomState(nv.SEMENTE + 31)
    e = e.rename(columns={"ORGANIZAÇÃO": "ORGANIZACAO", "CÓD_FILIAL": "COD_FILIAL"})
    e["ORGANIZACAO"] = 6
    e["SEGMENTO"] = rng.choice(["COMERCIAL", "INDUSTRIAL", "ADMINISTRATIVO"], size=len(e))
    e["TIPO"] = "NF"
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
