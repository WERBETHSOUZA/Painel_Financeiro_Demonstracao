"""
components/buttons.py
======================
Botões padrão reutilizados em todas as telas/relatórios — mantém a mesma
aparência (ícone, texto, cor) em qualquer lugar do painel. Para um relatório
novo, use botao_exportar_excel() em vez de um st.download_button avulso.
"""

import streamlit as st

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def botao_exportar_excel(
    data: bytes,
    file_name: str,
    key: str | None = None,
    use_container_width: bool = False,
    label: str = "Exportar para Excel",
    help: str | None = None,
) -> bool:
    """Botão padrão "Exportar para Excel" (ícone de download azul + texto),
    usado em todos os relatórios com exportação. Devolve True no clique,
    igual ao st.download_button original. Em layouts compactos (colunas
    estreitas), use label="Excel" mantendo o mesmo ícone."""
    return st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime=_MIME_XLSX,
        icon=":material/download:",
        key=key,
        help=help,
        use_container_width=use_container_width,
    )


def botao_salvar_imagem(
    data: bytes,
    file_name: str,
    key: str | None = None,
    use_container_width: bool = True,
    label: str = "Salvar PNG",
    help: str = "Salvar PNG (p/ E-mail)",
) -> bool:
    """Botão padrão "Salvar PNG" (ícone nativo, sem emoji no texto — emoji
    dentro do label do Streamlit pode quebrar em duas linhas em colunas
    estreitas). Mesmo padrão visual do botao_exportar_excel()."""
    return st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime="image/png",
        icon=":material/image:",
        key=key,
        help=help,
        use_container_width=use_container_width,
    )


def botoes_acao_row(
    excel: dict | None = None,
    imagem: dict | None = None,
    copiar: dict | None = None,
) -> None:
    """Linha padrão de botões Excel / Salvar PNG / Copiar.

    excel:  {"data": bytes, "file_name": str, "key": str, "label": str (opt)}
    imagem: {"data": bytes, "file_name": str, "key": str}
    copiar: {"data": bytes, "key": str}
    Cada parâmetro é opcional — omita o que não existir.
    Aplica 12 px de espaçamento acima e gap pequeno entre os botões.
    """
    from utils.imagem_email import render_botao_copiar_imagem

    n = sum(x is not None for x in (excel, imagem, copiar))
    if n == 0:
        return

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    cols = st.columns([1] * n + [max(1, 6 - n)], gap="small")

    idx = 0
    if excel is not None:
        with cols[idx]:
            botao_exportar_excel(
                excel["data"], excel["file_name"],
                key=excel["key"], use_container_width=True,
                label=excel.get("label", "Excel"),
            )
        idx += 1
    if imagem is not None:
        with cols[idx]:
            botao_salvar_imagem(
                imagem["data"], imagem["file_name"],
                key=imagem["key"], use_container_width=True,
            )
        idx += 1
    if copiar is not None:
        with cols[idx]:
            render_botao_copiar_imagem(copiar["data"], key=copiar["key"])
