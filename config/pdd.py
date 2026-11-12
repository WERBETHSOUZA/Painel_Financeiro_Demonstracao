"""
config/pdd.py
=============
Regra de PDD (Mercado Interno): título vencido há mais de DIAS_PDD dias, contados a partir do VENCIMENTO, é
classificado como PDD. O PDD sai do "Vencido" e da Inadimplência, mas continua dentro do Saldo Total em Aberto.
Acima de DIAS_PDD_PERDA dias o título segue como PDD (não some do painel); a quantidade acima desse limite
aparece no card de PDD.

Para mudar os limites, basta trocar os números abaixo (commit, push, git pull e reinício do Streamlit).
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

# Opção do Admin: "ocultar PDD". Fica em config/opcoes.json (fora do Git, como o permissoes.json: no servidor é separado).
ARQUIVO_OPCOES = Path(__file__).resolve().parent / "opcoes.json"

DIAS_PDD = 90          # acima disso, o vencido vira PDD
DIAS_PDD_PERDA = 200   # acima disso, o PDD é destacado como "perda provável" (continua visível)

COR_PDD = "#8b5cf6"        # roxo do PDD nos cards e tabelas
COR_PDD_TEXTO = "#c4b5fd"  # roxo claro para texto sobre fundo escuro


def dias_atraso(df: pd.DataFrame) -> pd.Series:
    """Dias de atraso desde o vencimento (coluna DIAS da consulta, que é negativa quando vencido)."""
    if "DIAS" not in df.columns:
        return pd.Series(float("nan"), index=df.index)
    return pd.to_numeric(df["DIAS"], errors="coerce").abs()


def ocultar_pdd() -> bool:
    """True quando o administrador ligou "Ocultar PDD" (Admin > Acessos > Opções do relatório)."""
    try:
        return bool(json.loads(ARQUIVO_OPCOES.read_text(encoding="utf-8")).get("ocultar_pdd", False))
    except (FileNotFoundError, ValueError, OSError):
        return False


def definir_ocultar_pdd(ligado: bool, quem: str) -> None:
    try:
        dados = json.loads(ARQUIVO_OPCOES.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        dados = {}
    dados.update({"ocultar_pdd": bool(ligado), "atualizado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
                  "atualizado_por": quem})
    tmp = ARQUIVO_OPCOES.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ARQUIVO_OPCOES)


def classificar_vencidos(df: pd.DataFrame) -> pd.DataFrame:
    """Devolve uma cópia com a coluna CLASSIF_VENCIDO: "VENCIDO" ou "PDD" nos títulos vencidos e "" nos demais.
    Com "Ocultar PDD" ligado no Admin, os títulos PDD saem do resultado (e portanto de tudo que o painel mostra)."""
    out = df.copy()
    out["CLASSIF_VENCIDO"] = ""
    if "SITUACAO" not in out.columns:
        return out
    vencido = out["SITUACAO"].eq("VENCIDO")
    out.loc[vencido, "CLASSIF_VENCIDO"] = "VENCIDO"
    out.loc[vencido & (dias_atraso(out) > DIAS_PDD), "CLASSIF_VENCIDO"] = "PDD"
    if ocultar_pdd():
        out = out[out["CLASSIF_VENCIDO"] != "PDD"]
    return out


def qtd_acima_perda(df_pdd: pd.DataFrame) -> int:
    """Quantos títulos de PDD passam do limite de perda provável."""
    return int((dias_atraso(df_pdd) > DIAS_PDD_PERDA).sum())
