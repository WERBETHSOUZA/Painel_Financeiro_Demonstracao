"""
Painel Financeiro — demonstração com dados 100% fictícios.

Roda o MESMO painel (o `app.py` copiado do projeto real, com o mesmo menu, telas e botões), só que sem banco de dados e
sem nenhuma informação real: os dados vêm de `services/data_service.py` (inventados) e o login é de demonstração
(usuário `admin`, senha `admin`).

    streamlit run app_demo.py --server.port 8590

Para atualizar a demonstração depois de mudanças no projeto real:  python tools/sincronizar_com_projeto_real.py
"""

import runpy
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from services import permissoes  # noqa: E402

USUARIO_DEMO = "admin"

# Grupos e usuários fictícios da tela Admin > Acessos (só semeia na primeira vez; depois vale o que foi salvo)
if not permissoes.ARQUIVO.exists():
    permissoes.salvar({"grupos": {
        permissoes.GRUPO_ADMIN: {"membros": ["elisa.ramos"]},
        "Financeiro": {"paineis": ["Financeiro > Visão Geral MI-ME", "Financeiro > Mercado Interno",
                                    "Financeiro > Mercado Externo", "Financeiro > Inconsistências",
                                    "Tesouraria > Recebimento por Banco"],
                       "relatorios": ["📄 Contas a Receber - Exportação", "💱 Variação Cambial ME", "📄 Boleto Não Gerado"],
                       "membros": ["ana.souza", "bruno.lima"]},
        "Comercial": {"paineis": ["Comercial > Visão Geral Comercial", "Comercial > Grupo de Crédito",
                                   "Comercial > Situação Cliente", "Comercial > Faturamento Cliente/Grupo"],
                      "relatorios": ["💳 Grupo de Crédito"], "membros": ["carla.mendes", "diego.prado"]},
    }}, USUARIO_DEMO)

runpy.run_path(str(RAIZ / "app.py"), run_name="__main__")
