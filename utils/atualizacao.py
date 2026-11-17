"""Observação discreta "Última atualização dd/mm às hh:mm" abaixo do título de cada painel.

A hora é a do momento em que o painel buscou os dados no banco pela última vez: fica guardada por 5 minutos (o menor prazo de cache das
consultas) e é zerada junto com o cache no botão Atualizar. Consultas com cache mais longo (por exemplo o recebido do mês, 30 minutos)
podem estar um pouco mais antigas que a hora mostrada."""
import datetime

import streamlit as st

_PRAZO_SEGUNDOS = 300
_ATRIBUTO_ORIGINAL = "_ibc_title_original"
_SEM_LEGENDA = {"Resumo Pendências", "Acessos"}     # o Resumo Pendências já tem a sua; Acessos é configuração, não dado


@st.cache_data(ttl=_PRAZO_SEGUNDOS, show_spinner=False)
def _momento(painel: str) -> datetime.datetime:
    return datetime.datetime.now()


def html_ultima_atualizacao(painel: str) -> str:
    m = _momento(painel)
    return (f"<div style='font-size:12px;color:#6b7280;margin:-.3rem 0 .3rem 2px'>Última atualização {m:%d/%m} às {m:%H:%M}</div>")


def ativar_nos_titulos(painel: str | None) -> None:
    """Faz todo `st.title(...)` das telas mostrar a observação logo abaixo, sem mexer em cada painel. Chamada a cada execução da
    tela; o `st.title` original é guardado uma vez só (a função de fora do script persiste entre as execuções)."""
    if not hasattr(st, _ATRIBUTO_ORIGINAL):
        setattr(st, _ATRIBUTO_ORIGINAL, st.title)
    original = getattr(st, _ATRIBUTO_ORIGINAL)
    if not painel or painel in _SEM_LEGENDA:
        st.title = original
        return

    def titulo(*args, **kwargs):
        resultado = original(*args, **kwargs)
        st.html(html_ultima_atualizacao(painel))
        return resultado

    st.title = titulo
