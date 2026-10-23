"""
utils/prazos.py
===============
Dias a vencer / dias vencido calculados a partir das datas de vencimento e prorrogado.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def calcular_dias_prazo(df: pd.DataFrame, hoje=None) -> pd.DataFrame:
    """Acrescenta DIAS_PRORROGADO e DIAS_VENCIDO ao DataFrame.

    DIAS_PRORROGADO = PRORROGADO − VENCIMENTO (extensão concedida, sempre >= 0).
    DIAS_VENCIDO    = unificado:
        · quando vencido (hoje > VENCIMENTO): hoje − VENCIMENTO (atraso em dias)
        · quando a vencer (hoje <= VENCIMENTO): PRORROGADO ou VENCIMENTO − hoje (dias restantes)
    Títulos sem saldo em aberto ficam vazios.
    """
    out = df.copy()
    hoje_ts = pd.Timestamp(hoje or date.today()).normalize()
    idx = out.index
    venc = pd.to_datetime(out["VENCIMENTO"], errors="coerce") if "VENCIMENTO" in out.columns else pd.Series(pd.NaT, index=idx)
    pror = pd.to_datetime(out["PRORROGADO"], errors="coerce") if "PRORROGADO" in out.columns else pd.Series(pd.NaT, index=idx)

    prorrogado_dias = (pror - venc).dt.days.clip(lower=0)

    overdue   = (hoje_ts - venc).dt.days.clip(lower=0)
    data_ref  = pror.where(pror.notna(), venc)
    remaining = (data_ref - hoje_ts).dt.days.clip(lower=0)
    is_late   = hoje_ts > venc
    unified   = (-overdue).where(is_late, remaining)

    if "SALDO_EM_ABERTO" in out.columns:
        sem_saldo = pd.to_numeric(out["SALDO_EM_ABERTO"], errors="coerce").fillna(0) <= 0
        prorrogado_dias = prorrogado_dias.mask(sem_saldo)
        unified = unified.mask(sem_saldo)

    out["DIAS_PRORROGADO"] = prorrogado_dias.round().astype("Int64")
    out["DIAS_VENCIDO"]    = unified.round().astype("Int64")
    return out


def nullar_zeros_dias(df: pd.DataFrame, colunas=("DIAS_PRORROGADO", "DIAS_VENCIDO")) -> pd.DataFrame:
    """Substitui 0 por NaN nas colunas de dias antes do export Excel."""
    df = df.copy()
    for col in colunas:
        if col in df.columns:
            df[col] = df[col].replace(0, pd.NA)
    return df


def formatar_dias_html(valor, cor: str, negrito: bool = False, cor_zero: str | None = None) -> str:
    """Dias em HTML colorido (vazio quando nulo).
    cor_zero: cor usada quando valor == 0; omitido = usa `cor`."""
    if valor is None or pd.isna(valor):
        return ""
    v = int(valor)
    peso = "700" if negrito else "500"
    cor_usar = (cor_zero if cor_zero is not None and v == 0 else cor)
    unidade = "dia" if v == 1 else "dias"
    return f'<span style="color:{cor_usar};font-weight:{peso}">{v} {unidade}</span>'


def formatar_dias_unificado_html(row, col_dias: str = "DIAS_VENCIDO",
                                  col_situacao: str = "SITUACAO") -> str:
    """Formata DIAS_VENCIDO com cor baseada em SITUACAO:
    · VENCIDO  → vermelho negrito (atraso)
    · A VENCER → verde (dias restantes)
    """
    val = row.get(col_dias)
    if val is None or pd.isna(val):
        return ""
    v = abs(int(val))
    sit = str(row.get(col_situacao, "")).upper()
    if sit == "VENCIDO":
        return formatar_dias_html(v, VERMELHO_DIAS, negrito=True)
    return formatar_dias_html(v, VERDE_DIAS, cor_zero=VERDE_DIAS)


VERDE_DIAS    = "#22c55e"
VERMELHO_DIAS = "#E24B4A"


def texto_dias_para_imagem(df_exibicao: pd.DataFrame, df_numerico: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    """Troca colunas de dias (HTML) por texto simples para imagem/PDF."""
    out = df_exibicao.copy()
    for col_exib, col_num in mapa.items():
        if col_exib in out.columns and col_num in df_numerico.columns:
            out[col_exib] = df_numerico.loc[out.index, col_num].apply(
                lambda v: "" if pd.isna(v) else f"{abs(int(v))} dias"
            )
    return out
