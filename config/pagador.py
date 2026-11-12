"""
config/pagador.py
=================
Classificação do pagamento (Mercado Interno) e perfil do cliente/grupo como pagador, a partir do histórico de baixas
(QUERY_HISTORICO_PAGAMENTOS_MI.sql).

Cada parcela paga é comparada com o crédito esperado: vencimento (o vigente, prorrogado) + 1 dia útil, a mesma regra do
"Recebimento de hoje". O perfil usa o atraso médio ponderado pelo valor pago.

Para mudar os limites, basta trocar os números abaixo (commit, push, git pull e reinício do Streamlit).
"""

import numpy as np
import pandas as pd

MESES_CARD = None        # janela do card "Perfil de pagamento": None = todo o histórico (12 = últimos 12 meses)
MIN_PARCELAS = 5         # menos parcelas pagas que isso na janela: "Sem histórico"

# Ótimo pagador: mais de LIMITE_OTIMO_PCT % do valor pago no prazo (ou antecipado) E atraso médio de até LIMITE_OTIMO_ATRASO dia(s).
LIMITE_OTIMO_PCT = 90
LIMITE_OTIMO_ATRASO = 1

# Atraso médio ponderado (dias): até LIMITE_BOM = Bom pagador; até LIMITE_REGULAR = Regular;
# até LIMITE_ATENCAO = Atenção; acima disso = Mau pagador.
LIMITE_BOM = 5
LIMITE_REGULAR = 15
LIMITE_ATENCAO = 30

# (limite superior de dias de atraso, rótulo) das faixas de pagamento em atraso
FAIXAS_ATRASO = [(5, "Atraso até 5 dias"), (15, "Atraso 6 a 15 dias"), (30, "Atraso 16 a 30 dias"),
                 (60, "Atraso 31 a 60 dias"), (float("inf"), "Atraso acima de 60 dias")]
ORDEM_FAIXAS = ["Pago antecipado", "Pago no prazo"] + [r for _, r in FAIXAS_ATRASO]
ROTULO_SEM_DATA = "Quitado sem data (desconto/adiantamento)"
ROTULO_ABERTO_VENCIDO = "Em aberto - vencido"
ROTULO_ABERTO_A_VENCER = "Em aberto - a vencer"

# cor (borda/texto) de cada perfil e de cada faixa
COR_PERFIL = {"Ótimo pagador": "#378ADD", "Bom pagador": "#22c55e", "Regular": "#EF9F27", "Atenção": "#f97316", "Mau pagador": "#E24B4A",
              "Sem histórico": "#8892a4"}
# cor de FUNDO (versão escura da cor do perfil) do card e do banner: o perfil se destaca pelo fundo, com o texto em branco
FUNDO_PERFIL = {"Ótimo pagador": "#16263d", "Bom pagador": "#162b1d", "Regular": "#2d2616", "Atenção": "#2f2015",
                "Mau pagador": "#2b1818", "Sem histórico": "#1e1e2e"}
COR_FAIXA = {"Pago antecipado": "#378ADD", "Pago no prazo": "#1BADA6", "Atraso até 5 dias": "#EF9F27",
             "Atraso 6 a 15 dias": "#f97316", "Atraso 16 a 30 dias": "#E24B4A", "Atraso 31 a 60 dias": "#c0392b",
             "Atraso acima de 60 dias": "#8e1b1b", ROTULO_SEM_DATA: "#8892a4",
             ROTULO_ABERTO_VENCIDO: "#E24B4A", ROTULO_ABERTO_A_VENCER: "#22c55e"}


def _pascoa(ano: int) -> pd.Timestamp:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return pd.Timestamp(year=ano, month=mes, day=dia + 1)


def feriados_bancarios(ano_ini: int = 2010, ano_fim: int = 2035) -> list:
    """Dias sem expediente bancário no Brasil: feriados nacionais (1/1, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 25/12; 20/11 a partir de
    2024), mais 24/12 e 31/12 (sem expediente bancário) e os móveis ligados à Páscoa (Carnaval segunda e terça, Sexta-feira Santa e Corpus Christi). Não inclui feriados
    estaduais ou municipais."""
    datas = []
    for ano in range(ano_ini, ano_fim + 1):
        fixos = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 24), (12, 25), (12, 31)] + ([(11, 20)] if ano >= 2024 else [])
        datas += [pd.Timestamp(year=ano, month=m, day=d) for m, d in fixos]
        pascoa = _pascoa(ano)
        datas += [pascoa - pd.Timedelta(days=48), pascoa - pd.Timedelta(days=47),
                  pascoa - pd.Timedelta(days=2), pascoa + pd.Timedelta(days=60)]
    return sorted(datas)


_FERIADOS = np.array([d.to_datetime64() for d in feriados_bancarios()], dtype="datetime64[D]")


def credito_esperado(vencimento: pd.Series) -> pd.Series:
    """Vencimento + 1 dia; se cair em fim de semana ou feriado bancário, vai para o próximo dia útil."""
    d = pd.to_datetime(vencimento) + pd.Timedelta(days=1)
    valido = d.notna()
    saida = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns]")
    if valido.any():
        dias = d[valido].values.astype("datetime64[D]")
        saida[valido] = np.busday_offset(dias, 0, roll="forward", holidays=_FERIADOS).astype("datetime64[ns]")
    return saida


def _rotulo_faixa(dias: float) -> str:
    for limite, rotulo in FAIXAS_ATRASO:
        if dias <= limite:
            return rotulo
    return FAIXAS_ATRASO[-1][1]


def classificar_parcelas(df: pd.DataFrame, hoje: pd.Timestamp | None = None) -> pd.DataFrame:
    """Devolve uma cópia com CREDITO_ESPERADO, DIAS_ATRASO (dias do pagamento após o crédito esperado; negativo ou zero =
    no prazo; vazio se não pago) e CLASSIFICACAO."""
    hoje = pd.Timestamp.today().normalize() if hoje is None else pd.Timestamp(hoje).normalize()
    out = df.copy()
    for c in ("EMISSAO", "VENCTO", "PRORROGADO", "DT_PRIM_PAG", "DT_ULT_PAG"):
        out[c] = pd.to_datetime(out[c], errors="coerce")
    for c in ("VALOR_PARCELA", "SALDO", "VALOR_PAGO", "DESCONTO", "BAIXA_ADIANT"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    out["CREDITO_ESPERADO"] = credito_esperado(out["PRORROGADO"])
    aberto = out["SALDO"].abs() > 0.005
    pago = (~aberto) & out["DT_ULT_PAG"].notna()
    out["DIAS_ATRASO"] = np.where(pago, (out["DT_ULT_PAG"] - out["CREDITO_ESPERADO"]).dt.days, np.nan)

    classe = pd.Series(ROTULO_SEM_DATA, index=out.index, dtype=object)
    classe[aberto & (out["PRORROGADO"] < hoje)] = ROTULO_ABERTO_VENCIDO
    classe[aberto & ~(out["PRORROGADO"] < hoje)] = ROTULO_ABERTO_A_VENCER
    p = pago
    classe[p] = [_rotulo_faixa(d) if d > 0 else "Pago no prazo" for d in out.loc[p, "DIAS_ATRASO"]]
    classe[p & (out["DT_ULT_PAG"] < out["PRORROGADO"])] = "Pago antecipado"
    out["CLASSIFICACAO"] = classe
    return out


def pagas_na_janela(df: pd.DataFrame, meses: int | None, hoje: pd.Timestamp | None = None) -> pd.DataFrame:
    """Parcelas pagas (com data) cujo pagamento caiu nos últimos `meses` meses (None = todo o histórico)."""
    hoje = pd.Timestamp.today().normalize() if hoje is None else pd.Timestamp(hoje).normalize()
    p = df[df["DIAS_ATRASO"].notna()]
    if meses:
        p = p[p["DT_ULT_PAG"] >= hoje - pd.DateOffset(months=meses)]
    return p


def resumir(df_classificado: pd.DataFrame, meses: int | None, hoje: pd.Timestamp | None = None) -> dict:
    """Métricas do pagador na janela: parcelas, valor pago, % do valor no prazo, atraso médio ponderado, pior atraso,
    parcelas com mais de 15 dias de atraso e o perfil."""
    p = pagas_na_janela(df_classificado, meses, hoje)
    if p.empty:
        return {"parcelas": 0, "valor": 0.0, "pct_prazo": 0.0, "atraso_medio": 0.0, "pior_atraso": 0, "acima_15": 0,
                "perfil": "Sem histórico"}
    peso = p["VALOR_PAGO"].where(p["VALOR_PAGO"] > 0, p["VALOR_PARCELA"])
    if peso.sum() <= 0:
        peso = pd.Series(1.0, index=p.index)
    atraso = p["DIAS_ATRASO"].clip(lower=0)
    medio = float(np.average(atraso, weights=peso))
    res = {
        "parcelas": int(len(p)), "valor": float(peso.sum()),
        "pct_prazo": float(peso[p["DIAS_ATRASO"] <= 0].sum() / peso.sum() * 100),
        "atraso_medio": medio, "pior_atraso": int(max(p["DIAS_ATRASO"].max(), 0)),
        "acima_15": int((p["DIAS_ATRASO"] > 15).sum()),
    }
    res["perfil"] = perfil(res)
    return res


def perfil(resumo: dict) -> str:
    if resumo["parcelas"] < MIN_PARCELAS:
        return "Sem histórico"
    m = resumo["atraso_medio"]
    if resumo.get("pct_prazo", 0) > LIMITE_OTIMO_PCT and m <= LIMITE_OTIMO_ATRASO:
        return "Ótimo pagador"
    if m <= LIMITE_BOM:
        return "Bom pagador"
    if m <= LIMITE_REGULAR:
        return "Regular"
    if m <= LIMITE_ATENCAO:
        return "Atenção"
    return "Mau pagador"


def faixas(df_classificado: pd.DataFrame, meses: int | None, hoje: pd.Timestamp | None = None) -> list:
    """[(rótulo, quantidade de parcelas)] das faixas de pagamento, na ordem de ORDEM_FAIXAS, na janela."""
    p = pagas_na_janela(df_classificado, meses, hoje)
    cont = p["CLASSIFICACAO"].value_counts()
    return [(r, int(cont.get(r, 0))) for r in ORDEM_FAIXAS]
