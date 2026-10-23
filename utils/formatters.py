import unicodedata
import pandas as pd


def normalizar_nome(nome: str) -> str:
    """Converte 'João Silva' em 'joao.silva' para montar o e-mail."""
    nome = nome.strip().lower()
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    partes = nome.split()
    return ".".join(partes)


def formatar_datas(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas de data para o formato dd/mm/yyyy."""
    for coluna in ["EMISSÃO", "ENTRADA", "VENCTO", "PRORROGADO", "EMISSAO"]:
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce").dt.strftime("%d/%m/%Y")
    return df
