"""
services/clientes_transferencia.py
==================================
Clientes do Mercado Interno que pagam por TRANSFERÊNCIA (todo cliente é boleto por padrão; aqui ficam só as exceções).
NENHUM cliente vem pré-cadastrado: a lista começa vazia em todo ambiente e só tem quem foi inserido manualmente na tela
Admin > Clientes por Transferência.
Grava em config/clientes_transferencia.json (fora do Git, como o permissoes.json; no servidor o arquivo é separado).
Quem está na lista sai do relatório Boleto Não Gerado e ganha a fatia "Transferência" em Distribuição por Banco.
A tela de cadastro fica em Admin > Clientes por Transferência.
"""

import json
import os
from datetime import datetime
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "config" / "clientes_transferencia.json"

def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def carregar() -> dict:
    """{código (texto): {"nome", "incluido_por", "em"}}. Sem arquivo (ambiente novo) a lista é vazia: nada é cadastrado
    sozinho, o arquivo só nasce quando alguém inclui o primeiro cliente."""
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        clientes = dados.get("clientes", {})
        return {str(k): v for k, v in clientes.items() if isinstance(v, dict)}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _gravar(clientes: dict, quem: str) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQUIVO.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"atualizado_em": _agora(), "atualizado_por": quem,
                   "clientes": dict(sorted(clientes.items(), key=lambda kv: kv[1].get("nome", "")))},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARQUIVO)


def codigos() -> set:
    """Conjunto de códigos (texto) dos clientes por transferência."""
    return set(carregar())


def incluir(codigo, nome: str, quem: str) -> None:
    clientes = carregar()
    clientes[str(int(codigo))] = {"nome": (nome or "").strip(), "incluido_por": quem, "em": _agora()}
    _gravar(clientes, quem)


def remover(codigo, quem: str) -> None:
    clientes = carregar()
    clientes.pop(str(codigo), None)
    _gravar(clientes, quem)
