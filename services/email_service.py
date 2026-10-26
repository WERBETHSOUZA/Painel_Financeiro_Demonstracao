"""Descrições amigáveis das categorias de erro da tela Inconsistências (textos de demonstração)."""

_DESCRICOES_ERRO = {
    "ERRO CLASSE ADIANTAMENTO": (
        "A classe informada não é permitida para lançamentos de adiantamento. "
        "Utilize uma das classes autorizadas."
    ),
    "ERRO ACAO SEGMENTO": (
        "Filiais do segmento A aceitam apenas Ações do segmento A. "
        "Filiais do segmento B aceitam apenas Ações do segmento B."
    ),
    "ERRO TIPO FAVORECIDO CLIENTE": "Não é possível lançar Contas a Pagar para favorecidos do tipo Cliente.",
}


def obter_obs_inconsistencia(categoria: str) -> str:
    """Descrição amigável da categoria de erro — usada na tela e no PNG."""
    if not categoria:
        return ""
    for chave, descricao in _DESCRICOES_ERRO.items():
        if chave in str(categoria).upper():
            return descricao
    return str(categoria)
