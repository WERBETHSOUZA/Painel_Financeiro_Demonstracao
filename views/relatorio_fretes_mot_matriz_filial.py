"""
views/relatorio_fretes_mot_matriz_filial.py
=============================================
Relatório "Fretes Mot - Matriz x Filial": confere, par a par, o que a Demo efetuou e o que a Filial recebeu (adiantamentos e pagamentos).
O período (data de prorrogação, dia final incluído; abre no mês vigente) é escolhido na barra lateral e só ele vai ao banco.
Tabela, cards, filtros e Excel ficam em views/relatorio_conferencia_matriz_filial.py; regras em services/conferencia_matriz_filial.py.
"""

import calendar
import datetime

import streamlit as st

from services.data_service import carregar_conferencia_matriz_filial
from views import relatorio_conferencia_matriz_filial


def render() -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Fretes Mot - Matriz x Filial")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        # Callback: com st.rerun no meio da página os filtros da barra lateral seriam esquecidos
        st.button("🔄 Atualizar", key="rfm_atualizar", use_container_width=True, on_click=st.cache_data.clear)

    hoje = datetime.date.today()
    mes_vigente = (hoje.replace(day=1), hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]))
    with st.sidebar:
        st.caption("Fretes Mot - Matriz x Filial")
        periodo = st.date_input(
            "Prorrogado (período)", value=mes_vigente, format="DD/MM/YYYY", key="rfm_periodo",
            help="Data de prorrogação do título; abre no mês vigente. Só o período escolhido é buscado no banco; o dia final entra.",
        )
        st.multiselect("Grupo", ["Adiantamento", "Pagamento"], key="rci_grupo", placeholder="Adiantamento e Pagamento",
                       help="Vazio = adiantamentos e pagamentos")
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rfm_gerar")

    if gerar:
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            st.session_state["_rfm_periodo"] = (periodo[0], periodo[1])
            carregar_conferencia_matriz_filial.clear()            # Gerar Relatório sempre refaz a consulta no banco
        else:
            st.session_state.pop("_rfm_periodo", None)
            st.warning("Selecione o período (data inicial e final) na barra lateral e clique em Gerar Relatório.")
            return

    periodo_sel = st.session_state.get("_rfm_periodo")
    if not periodo_sel:
        st.info("O período de prorrogação abre no **mês vigente**. Ajuste-o na barra lateral, se precisar, e clique em **Gerar Relatório**.")
        return
    dt_ini, dt_fim = periodo_sel

    relatorio_conferencia_matriz_filial.render_corpo(dt_ini, dt_fim)
