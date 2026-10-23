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
