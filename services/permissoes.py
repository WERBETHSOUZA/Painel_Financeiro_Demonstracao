"""
services/permissoes.py
======================
Permissões por grupo: cada grupo libera painéis e relatórios e tem uma lista de membros (usuários).

Fica em `config/permissoes.json` (fora do Git). Cada gravação guarda uma cópia do arquivo anterior em
`config/permissoes_backup/`. O grupo "Administrador" libera tudo; os administradores fixos
(USUARIOS_ADMIN / GRUPOS_ADMIN, definidos no app.py) também veem tudo e não dependem deste arquivo.

Formato:
    {
      "versao": 2,
      "grupos": {
        "Administrador": {"membros": ["fulano"]},
        "Comercial": {"paineis": ["Comercial > Grupo de Crédito"], "relatorios": [], "membros": ["maria.teles"]}
      }
    }
Quem está em mais de um grupo recebe a soma dos acessos; quem não está em nenhum grupo não acessa nada.
"""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "config" / "permissoes.json"
MAX_BACKUPS = 50
GRUPO_ADMIN = "Administrador"
_USUARIO_VALIDO = re.compile(r"^[a-z0-9._-]{2,64}$")


def normalizar_usuario(nome) -> str:
    return str(nome or "").strip().lower()


def usuario_valido(nome) -> bool:
    return bool(_USUARIO_VALIDO.match(normalizar_usuario(nome)))


def nome_grupo_valido(nome) -> bool:
    return 2 <= len(str(nome or "").strip()) <= 40


# Itens de menu que foram divididos: quem tinha o antigo passa a ter os novos (mantém o acesso que já existia).
_SUBSTITUIDOS = {
    "Financeiro > Contas a Receber": ["Financeiro > Visão Geral MI-ME", "Financeiro > Mercado Interno",
                                      "Financeiro > Mercado Externo"],
}


def _migrar_paineis(paineis) -> list:
    saida = []
    for p in paineis:
        saida.extend(_SUBSTITUIDOS.get(str(p), [str(p)]))
    return saida


def _grupo(v) -> dict:
    v = v or {}
    return {
        "paineis": _migrar_paineis(v.get("paineis", [])),
        "relatorios": [str(r) for r in v.get("relatorios", [])],
        "membros": sorted({normalizar_usuario(m) for m in v.get("membros", []) if normalizar_usuario(m)}),
    }


def _vazio() -> dict:
    return {"versao": 2, "grupos": {GRUPO_ADMIN: _grupo(None)}}


def carregar(arquivo: Path = ARQUIVO) -> dict:
    """Lê o arquivo; se não existir (ou estiver ilegível), devolve a configuração inicial: só os administradores
    fixos têm acesso e ninguém mais está em grupo algum."""
    try:
        bruto = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _vazio()
    dados = _vazio()
    for nome, v in (bruto.get("grupos") or {}).items():
        dados["grupos"][str(nome)] = _grupo(v)
    dados["grupos"][GRUPO_ADMIN]["paineis"] = []
    dados["grupos"][GRUPO_ADMIN]["relatorios"] = []
    return dados


def salvar(dados: dict, quem: str, arquivo: Path = ARQUIVO) -> None:
    """Grava com escrita atômica e guarda o arquivo anterior em `permissoes_backup/` (com data e hora)."""
    arquivo = Path(arquivo)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    if arquivo.exists():
        pasta = arquivo.parent / "permissoes_backup"
        pasta.mkdir(exist_ok=True)
        shutil.copy2(arquivo, pasta / f"permissoes_{datetime.now():%Y%m%d_%H%M%S_%f}.json")
        for antigo in sorted(pasta.glob("permissoes_*.json"))[:-MAX_BACKUPS]:
            antigo.unlink(missing_ok=True)
    grupos = {}
    for nome, v in sorted(dados.get("grupos", {}).items()):
        g = _grupo(v)
        if nome == GRUPO_ADMIN:
            g = {"membros": g["membros"]}
        else:
            g["paineis"], g["relatorios"] = sorted(set(g["paineis"])), sorted(set(g["relatorios"]))
        grupos[nome] = g
    saida = {
        "versao": 2,
        "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "atualizado_por": quem,
        "grupos": grupos,
    }
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, arquivo)


def grupos_do_usuario(usuario: str, dados: dict) -> list:
    u = normalizar_usuario(usuario)
    return [nome for nome, g in dados["grupos"].items() if u in g["membros"]]


def eh_admin_por_grupo(usuario: str, dados: dict | None = None) -> bool:
    dados = dados if dados is not None else carregar()
    return normalizar_usuario(usuario) in dados["grupos"][GRUPO_ADMIN]["membros"]


def permissoes_do_usuario(usuario: str, admin: bool, dados: dict | None = None):
    """None = acesso total (administrador fixo ou do grupo Administrador).
    Caso contrário, {"paineis": {...}, "relatorios": {...}} com a soma dos grupos do usuário."""
    if admin:
        return None
    dados = dados if dados is not None else carregar()
    nomes = grupos_do_usuario(usuario, dados)
    if GRUPO_ADMIN in nomes:
        return None
    if not nomes:
        return {"paineis": set(), "relatorios": set()}
    return {
        "paineis": {p for n in nomes for p in dados["grupos"][n]["paineis"]},
        "relatorios": {r for n in nomes for r in dados["grupos"][n]["relatorios"]},
    }


def filtrar_menu(estrutura: list, perm) -> list:
    """Aplica as permissões à estrutura do menu (mesmo formato de PAINEIS_ADMIN do app.py).
    Grupos sem nenhum painel liberado somem; o item Relatórios só aparece se houver relatório liberado."""
    if perm is None:
        return list(estrutura)
    saida = []
    for item in estrutura:
        if len(item) != 3:
            saida.append(item)
            continue
        icone, nome, conteudo = item
        if isinstance(conteudo, dict):
            liberados = {k: v for k, v in conteudo.items() if k in perm["relatorios"]}
            if liberados:
                saida.append((icone, nome, liberados))
        else:
            subs = [(i, s) for i, s in conteudo if f"{nome} > {s}" in perm["paineis"]]
            if subs:
                saida.append((icone, nome, subs))
    return saida
