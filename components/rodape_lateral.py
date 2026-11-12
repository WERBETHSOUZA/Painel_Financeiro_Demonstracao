"""
components/rodape_lateral.py
=============================
Ícone (?) discreto no topo da barra lateral: ao clicar, abre a janela "Ajuda" com a build (data do último commit),
a versão (1.00.<número de commits>), quem desenvolveu o BI e o link do GLPI. Sem o histórico do git, a build usa a
data do arquivo de código mais recente e a versão fica só com o 1.00.
"""

import subprocess
from datetime import datetime
from pathlib import Path

import streamlit as st

_RAIZ = Path(__file__).resolve().parent.parent
_PASTAS_CODIGO = ("views", "services", "components", "utils", "query", "config")
_VERSAO_BASE = "1.00"
_URL_GLPI = "https://exemplo.com.br/suporte"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_RAIZ, capture_output=True, text=True, timeout=5, check=True,
    ).stdout.strip()


@st.cache_resource(show_spinner=False)
def _build_e_versao() -> tuple[str, str]:
    """('03.11.2026', '1.00.295'): data do último commit e versão pelo número de commits."""
    try:
        momento = datetime.fromtimestamp(int(_git("log", "-1", "--format=%ct")))
        versao = f"{_VERSAO_BASE}.{int(_git('rev-list', '--count', 'HEAD'))}"
    except (OSError, subprocess.SubprocessError, ValueError):
        arquivos = [_RAIZ / "app.py"]
        for pasta in _PASTAS_CODIGO:
            arquivos += [p for p in (_RAIZ / pasta).rglob("*") if p.suffix in (".py", ".sql", ".json")]
        datas = [p.stat().st_mtime for p in arquivos if p.exists()]
        momento = datetime.fromtimestamp(max(datas)) if datas else None
        versao = _VERSAO_BASE
    return (momento.strftime("%d.%m.%Y") if momento else "-"), versao


_ICONE_AJUDA = (
    "url(\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill-rule='evenodd' d='M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16'/><path d='M5.255 5.786a.237.237 0 0 0 .241.247h.825c.138 0 .248-.113.266-.25.09-.656.54-1.134 1.342-1.134.686 0 1.314.343 1.314 1.168 0 .635-.374.927-.965 1.371-.673.489-1.206 1.06-1.168 1.987l.003.217a.25.25 0 0 0 .25.246h.811a.25.25 0 0 0 .25-.25v-.105c0-.718.273-.927 1.01-1.486.609-.463 1.244-.977 1.244-2.056 0-1.511-1.276-2.241-2.673-2.241-1.267 0-2.655.59-2.75 2.286m1.557 5.763c0 .533.425.927 1.01.927.609 0 1.028-.394 1.028-.927 0-.552-.42-.94-1.029-.94-.584 0-1.009.388-1.009.94'/></svg>\")"
)

_CSS = """
<style>
/* (?) no topo da barra lateral, na linha da setinha de recolher. Não ocupa espaço no layout e rola junto com o resto
   (logo e título "BI - FINANCEIRO"): ao rolar, ele some com eles. Também some com a barra recolhida. */
[data-testid="stLayoutWrapper"]:has(> .st-key-info_dev) { order: -1; height: 0; margin-bottom: -1rem; overflow: visible; }
/* O contêiner ocupa a largura toda da barra e ficava por cima da setinha de recolher, engolindo o clique: só o botão (?) recebe clique. */
.st-key-info_dev { position: relative; top: -3.81rem; left: 0.4rem; width: auto !important; pointer-events: none; }
.st-key-info_dev button { pointer-events: auto; }
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stLayoutWrapper"]:has(> .st-key-info_dev) { display: none !important; }
.st-key-info_dev button {
    width: 26px !important; min-width: 26px !important; height: 26px !important; min-height: 26px !important;
    padding: 0 !important; border: none !important;
    background-color: rgba(224, 224, 224, 0.6) !important;
    -webkit-mask: ICONE center / contain no-repeat; mask: ICONE center / contain no-repeat;
}
.st-key-info_dev button:hover { background-color: rgba(224, 224, 224, 0.9) !important; }
.st-key-info_dev button * { visibility: hidden; }
</style>
""".replace("ICONE", _ICONE_AJUDA)


@st.dialog("Ajuda")
def _dialogo_ajuda() -> None:
    build, versao = _build_e_versao()
    st.markdown(f"<div style='font-size:14px;color:#8892a4'>Build {build} &nbsp; V {versao}</div>", unsafe_allow_html=True)
    st.markdown("Demonstração com dados fictícios")
    st.markdown(f"Precisa de ajuda?  \n[Clique aqui para acessar o GLPI ↗]({_URL_GLPI})")
    if st.button("Fechar", key="info_dev_fechar"):
        st.rerun()


def render() -> None:
    """Desenha o (?) no topo da barra lateral. Chamar uma vez por execução, depois do login."""
    with st.sidebar:
        st.markdown(_CSS, unsafe_allow_html=True)
        with st.container(key="info_dev"):
            if st.button(" ", key="info_dev_abrir", help=None):
                _dialogo_ajuda()
