"""
components/buttons.py
======================
Botões padrão reutilizados em todas as telas/relatórios — mantém a mesma
aparência (ícone, texto, cor) em qualquer lugar do painel. Para um relatório
novo, use botao_exportar_excel() em vez de um st.download_button avulso.
"""

import base64
from collections.abc import Callable

import streamlit as st

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def botao_exportar_excel(
    data: bytes | Callable[[], bytes],
    file_name: str,
    key: str | None = None,
    use_container_width: bool = False,
    label: str = "Exportar para Excel",
    help: str | None = None,
) -> bool:
    """Botão padrão "Exportar para Excel" (ícone de download azul + texto),
    usado em todos os relatórios com exportação. Devolve True no clique,
    igual ao st.download_button original. Em layouts compactos (colunas
    estreitas), use label="Excel" mantendo o mesmo ícone. Com um relatório pesado, passe uma função
    (data=lambda: gerar()) para o arquivo só ser gerado quando o botão for clicado."""
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


def botao_salvar_pdf(
    data: bytes,
    file_name: str,
    key: str | None = None,
    use_container_width: bool = True,
    label: str = "Salvar PDF",
    help: str = "Salvar PDF (mesmo layout do PNG, para anexar em documentação)",
) -> bool:
    """Botão padrão "Salvar PDF", no mesmo padrão do "Salvar PNG"."""
    return st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime="application/pdf",
        icon=":material/picture_as_pdf:",
        key=key,
        help=help,
        use_container_width=use_container_width,
    )


def botao_abrir_em_aba(
    data: bytes,
    mime: str,
    label: str,
    key: str,
    icone: str = "pdf",
) -> None:
    """Botão que ABRE o arquivo (PDF ou imagem) numa aba nova do navegador, em vez de baixar a cada clique: a aba mostra o arquivo e de lá se baixa, se quiser.
    O arquivo já vai pronto dentro do botão (por isso gere-o em cache) e a aba nasce no clique, sem bloqueio de pop-up. Se o navegador bloquear a aba nova,
    o botão baixa o arquivo como plano B. Mesmo visual do botão Copiar."""
    b64 = base64.b64encode(data).decode("ascii")
    key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(key))        # a chave vira nome de variável JavaScript
    ext = "pdf" if mime == "application/pdf" else "png"
    svg = {
        "pdf": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"></path><path d="M14 3v5h5"></path><path d="M9 13h6M9 17h4"></path>',
        "imagem": '<rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="M21 15l-5-5L5 21"></path>',
    }.get(icone, "")
    st.iframe(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        html, body {{ margin:0; padding:0; overflow:hidden; background:transparent; font-family:"Source Sans", "Source Sans Pro", sans-serif; }}
        /* mesmas medidas do botão nativo do Streamlit (o do Excel): 35 px, canto 7 px, fonte 12,25 px, fundo e borda do tema escuro */
        #btn_{key} {{ width:100%; height:35px; border-radius:7px; border:0.67px solid rgba(224,224,224,0.2); background-color:#14171f; color:#e0e0e0;
            cursor:pointer; font-family:inherit; font-size:12.25px; font-weight:400; line-height:1.6; box-sizing:border-box; padding:3.5px 10.5px; display:flex;
            align-items:center; justify-content:center; gap:6px; white-space:nowrap; transition:border-color .15s ease, color .15s ease; }}
        #btn_{key} svg {{ flex-shrink:0; width:14px; height:14px; color:inherit; }}
        #btn_{key}:hover {{ border-color:#1E88E5; color:#1E88E5; }}
        #btn_{key}:active {{ background-color:#1E88E5; color:#ffffff; border-color:#1E88E5; }}
        #msg_{key} {{ font-size:12px; min-height:14px; margin-top:4px; text-align:center; }}
    </style>
    </head>
    <body>
        <button id="btn_{key}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{svg}</svg>
            <span>{label}</span>
        </button>
        <div id="msg_{key}"></div>
        <script>
            // empresta a fonte do Streamlit (o quadro é isolado e não a carrega sozinho)
            try {{ window.parent.document.fonts.forEach(function(f) {{ document.fonts.add(f); }}); }} catch (e) {{}}
            var B64_{key} = '{b64}';
            function blob_{key}() {{
                var bin = atob(B64_{key}), arr = new Uint8Array(bin.length);
                for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                return new Blob([arr], {{ type: '{mime}' }});
            }}
            document.getElementById('btn_{key}').addEventListener('click', function() {{
                var msg = document.getElementById('msg_{key}');
                var url = URL.createObjectURL(blob_{key}());
                var aba = window.open(url, '_blank');
                if (aba) {{
                    msg.style.color = '#22c55e'; msg.innerText = 'Aberto em nova aba';
                }} else {{
                    var a = document.createElement('a'); a.href = url; a.download = '{label.replace(" ", "_")}.{ext}'; document.body.appendChild(a); a.click(); a.remove();
                    msg.style.color = '#f5c070'; msg.innerText = 'Pop-up bloqueado: baixei o arquivo';
                }}
                setTimeout(function() {{ msg.innerText = ''; }}, 3500);
            }});
        </script>
    </body>
    </html>
    """, height=54)


# Padrão atual da linha de botões: PDF e imagem abrem numa aba nova do navegador (de lá se baixa, se quiser) em vez de baixar a cada clique, e o botão
# Copiar não aparece. Para voltar a mostrar o Copiar, mude para True.
MOSTRAR_BOTAO_COPIAR = False


def botoes_acao_row(
    excel: dict | None = None,
    imagem: dict | None = None,
    copiar: dict | None = None,
    pdf: dict | None = None,
) -> None:
    """Linha padrão de botões: Excel (baixa) / Gerar Imagem / Gerar PDF (abrem numa aba nova do navegador, de onde se baixa, se quiser).

    excel:  {"data": bytes | função, "file_name": str, "key": str, "label": str (opt)}
    imagem: {"data": bytes, "file_name": str, "key": str}   (o arquivo vai pronto dentro do botão; gere-o em cache)
    pdf:    {"data": bytes, "file_name": str, "key": str}
    copiar: {"data": bytes, "key": str}   (só aparece com MOSTRAR_BOTAO_COPIAR = True)
    Cada parâmetro é opcional — omita o que não existir.
    Aplica 12 px de espaçamento acima e gap pequeno entre os botões.
    """
    copiar = copiar if MOSTRAR_BOTAO_COPIAR else None
    n = sum(x is not None for x in (excel, imagem, pdf, copiar))
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
            botao_abrir_em_aba(imagem["data"], "image/png", "Gerar Imagem", key=imagem["key"], icone="imagem")
        idx += 1
    if pdf is not None:
        with cols[idx]:
            botao_abrir_em_aba(pdf["data"], "application/pdf", "Gerar PDF", key=pdf["key"], icone="pdf")
        idx += 1
    if copiar is not None:
        from utils.imagem_email import render_botao_copiar_imagem
        with cols[idx]:
            render_botao_copiar_imagem(copiar["data"], key=copiar["key"])
