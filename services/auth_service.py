"""Diretório de usuários da demonstração (nomes 100% fictícios; no painel real a busca é feita no Active Directory)."""

_DIRETORIO = [
    ("admin", "Administrador"),
    ("ana.souza", "Ana Souza"),
    ("bruno.lima", "Bruno Lima"),
    ("carla.mendes", "Carla Mendes"),
    ("diego.prado", "Diego Prado"),
    ("elisa.ramos", "Elisa Ramos"),
    ("fabio.costa", "Fábio Costa"),
    ("gabriela.alves", "Gabriela Alves"),
]


USUARIO_DEMO, SENHA_DEMO, NOME_DEMO = "admin", "admin", "Administrador"


def authenticate_user(username: str, password: str) -> dict:
    """Login de demonstração (sem Active Directory): usuário `admin` e senha `admin`. Mesmo formato do painel real."""
    usuario = sanitize_username(username)
    if not usuario or not password:
        return {"success": False, "error": "Informe um usuário e uma senha válidos."}
    if usuario != USUARIO_DEMO or password != SENHA_DEMO:
        return {"success": False, "error": f"Usuário ou senha incorretos. Use {USUARIO_DEMO} / {SENHA_DEMO}."}
    return {"success": True, "username": USUARIO_DEMO, "name": NOME_DEMO, "groups": ["BI_FINANCEIRO_ADMIN"],
            "email": "admin@example.com", "department": "Demonstração"}


def sanitize_username(username: str) -> str | None:
    return str(username).strip().lower() if username else None


def buscar_usuarios(termo: str, limite: int = 20) -> list:
    termo = str(termo or "").strip().lower()
    if len(termo) < 3:
        return []
    return [(l, n) for l, n in _DIRETORIO if termo in l or termo in n.lower()][:limite]


def nomes_por_login(logins) -> dict:
    mapa = dict(_DIRETORIO)
    return {l: mapa[l] for l in logins if l in mapa}
