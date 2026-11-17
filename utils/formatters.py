import unicodedata
import pandas as pd


def formatar_cnpj_cpf(valor) -> str:
    """CNPJ (14 dígitos) como 00.000.000/0000-00 e CPF (11 dígitos) como 000.000.000-00; vazio se não há documento; o que não tiver 11 ou 14
    dígitos volta como veio (pode ser documento estrangeiro)."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return ""
    texto = str(valor).strip()
    digitos = "".join(c for c in texto if c.isdigit())
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return texto


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
