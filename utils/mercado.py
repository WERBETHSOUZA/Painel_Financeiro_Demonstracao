"""
utils/mercado.py
================
Sufixo de mercado para os títulos das telas ("... - Mercado Interno", "... - Mercado Externo" ou os dois),
a partir da coluna MERCADO ("MI"/"ME") dos títulos em aberto da seleção. Sem títulos, sem sufixo.
"""

import pandas as pd


def sufixo_mercado(df_titulos) -> str:
    if df_titulos is None or df_titulos.empty or "MERCADO" not in df_titulos.columns:
        return ""
    mercados = [nome for cod, nome in (("MI", "Interno"), ("ME", "Externo")) if (df_titulos["MERCADO"] == cod).any()]
    return " - Mercado " + " e ".join(mercados) if mercados else ""
