"""
Atualiza a demonstração a partir do projeto real (../dashboardfinanceiro).

    python tools/sincronizar_com_projeto_real.py

O que faz
- Copia o `app.py`, as telas (views), componentes, utilitários, configs e serviços do projeto real para a demo,
  trocando os nomes da empresa por nomes genéricos (ver TROCAS_GERAIS) e tirando do menu o que não existe na demo.
- NÃO copia `services/data_service.py` (na demo ele devolve dados inventados), `services/auth_service.py` (login de
  demonstração) nem `config/*.json`.
- No fim confere se sobrou algum nome real (empresa, pessoas, clientes) nos arquivos da demo e avisa.

A demo roda por `app_demo.py`, que só semeia os grupos de demonstração e executa o `app.py` copiado.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
REAL = DEMO.parent / "dashboardfinanceiro"

# Telas que a demo não tem: dependem de acesso direto ao banco ou ainda estão em teste.
VIEWS_FORA = {
    "relatorio_extrato_saldo_bancos.py",      # Saldos Bancários (base de teste)
    "relatorio_movimentacao_financeira.py",   # Extratos Bancários (consulta direta ao banco)
}
RENOMEAR = {"relatorio_fretes_mot_ibacem_pegasus.py": "relatorio_fretes_mot_matriz_filial.py"}

CONFIGS = ["settings.py", "frases.py", "pdd.py", "pagador.py", "classes_desconto.py"]
SERVICOS = ["permissoes.py", "email_service.py", "excel_service.py", "clientes_transferencia.py"]
ASSETS = ["styles.css", "brasil_estados.geojson"]

# Ordem importa: as trocas mais específicas vêm antes das genéricas.
TROCAS_GERAIS = [
    ("https://glpi.corporativo.ibacem.com.br/glpi", "https://exemplo.com.br/suporte"),
    ("Contas a Receber - Ibacem", "Contas a Receber - Exportação"),
    ("Contas_a_Receber_Ibacem", "Contas_a_Receber_Exportacao"),
    ("Fretes Mot - Ibacem x Pegasus", "Fretes Mot - Matriz x Filial"),
    ("Ibacem x Pegasus", "Matriz x Filial"),
    ("ibacem_pegasus", "matriz_filial"),
    ("ibacem_logo.png", "demo_logo.png"),
    ("ArcelorMittal", "Siderúrgica"),
    ("Arcelor Mittal", "Siderúrgica"),
    ("Pegasus", "Filial"),
    ("PEGASUS", "FILIAL"),
    ("IBACEM", "DEMO"),
    ("Ibacem", "Demo"),
    ("ibacem", "demo"),
    ("Desenvolvido por **Werbeth Lino**", "Demonstração com dados fictícios"),
    ("Werbeth Lino", "Equipe Demo"),
    ("werbeth.lino", "admin"),
    ("SONDA SUPERMERCADOS", "ALFA SUPERMERCADOS"),
    ('"Sonda"', '"Alfa"'),
]

# Ajustes só do app.py (texto exato; se o projeto real mudar esse trecho o script avisa).
AJUSTES_APP = [
    ("Use suas credenciais do Active Directory para acessar.",
     "Acesso de demonstração: usuário **admin** · senha **admin**. Todos os dados são fictícios."),
    ("Use seu usuário corporativo sem o domínio.", "Demonstração: use admin / admin."),
]
LINHAS_FORA_APP = [
    '("🏦", "Saldos Bancários"),',
    '("🏦", "Extratos Bancários"),',
    '"Tesouraria > Extratos Bancários": "Extrato de Movimentação Bancária",',
]
BLOCOS_FORA_APP = [
    ('    elif painel_atual == "Tesouraria > Saldos Bancários":\n        relatorio_extrato_saldo_bancos.render()\n\n', ""),
    ('    elif painel_atual == "Tesouraria > Extratos Bancários":\n        relatorio_movimentacao_financeira.render()\n\n', ""),
]
MODULOS_FORA_APP = ["relatorio_extrato_saldo_bancos", "relatorio_movimentacao_financeira"]

# Nomes que NÃO podem aparecer em nenhum arquivo da demo.
PROIBIDOS = ["ibacem", "pegasus", "arcelor", "mittal", "werbeth", "sonda", "zanlorenzi", "atacadao", "glpi.corporativo",
             "amana", "osmar", "multicom", "nicolini"]


def _ler(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def _sanear(texto: str) -> str:
    for antigo, novo in TROCAS_GERAIS:
        texto = texto.replace(antigo, novo)
    return texto


def _ajustar_app(texto: str, avisos: list) -> str:
    for antigo, novo in AJUSTES_APP:
        if antigo not in texto:
            avisos.append(f"app.py: trecho não encontrado (login): {antigo[:60]}")
        texto = texto.replace(antigo, novo)
    for mod in MODULOS_FORA_APP:
        texto, n = re.subn(rf",\s*{mod}\b", "", texto)
        if n == 0:
            avisos.append(f"app.py: import de {mod} não encontrado")
    for linha in LINHAS_FORA_APP:
        if linha not in texto:
            avisos.append(f"app.py: linha não encontrada: {linha}")
        texto = "\n".join(l for l in texto.split("\n") if l.strip() != linha)
    for antigo, novo in BLOCOS_FORA_APP:
        if antigo not in texto:
            avisos.append(f"app.py: bloco não encontrado: {antigo.splitlines()[0].strip()}")
        texto = texto.replace(antigo, novo)
    return texto


def _copiar(origem: Path, destino: Path, tratar_app: bool = False, avisos: list | None = None) -> None:
    texto = _sanear(_ler(origem))
    if tratar_app:
        texto = _ajustar_app(texto, avisos if avisos is not None else [])
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8", newline="\n")


def sincronizar() -> list:
    avisos: list = []
    copiados = []

    _copiar(REAL / "app.py", DEMO / "app.py", tratar_app=True, avisos=avisos)
    copiados.append("app.py")

    for pasta in ("views", "components", "utils"):
        for origem in sorted((REAL / pasta).glob("*.py")):
            if pasta == "views" and origem.name in VIEWS_FORA:
                continue
            destino = DEMO / pasta / RENOMEAR.get(origem.name, origem.name)
            _copiar(origem, destino)
            copiados.append(f"{pasta}/{destino.name}")

    for nome in CONFIGS:
        if (REAL / "config" / nome).exists():
            _copiar(REAL / "config" / nome, DEMO / "config" / nome)
            copiados.append(f"config/{nome}")
    for nome in SERVICOS:
        if (REAL / "services" / nome).exists():
            _copiar(REAL / "services" / nome, DEMO / "services" / nome)
            copiados.append(f"services/{nome}")
    for nome in ASSETS:
        origem = REAL / "assets" / nome
        destino = DEMO / "assets" / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        if nome.endswith(".css"):
            destino.write_text(_sanear(_ler(origem)), encoding="utf-8", newline="\n")
        else:
            destino.write_bytes(origem.read_bytes())
        copiados.append(f"assets/{nome}")

    # tela de relatório renomeada: os imports dentro das outras telas já foram trocados por _sanear
    print(f"{len(copiados)} arquivos copiados do projeto real.")
    return avisos


def verificar_vazamentos() -> list:
    achados = []
    ignorar = {"sincronizar_com_projeto_real.py"}
    for p in DEMO.rglob("*"):
        if (not p.is_file() or p.name in ignorar or ".git" in p.parts or "__pycache__" in p.parts
                or p.suffix.lower() not in {".py", ".md", ".sql", ".css", ".txt", ".bat", ".json", ".html"}):
            continue
        texto = p.read_text(encoding="utf-8", errors="ignore").lower()
        for termo in PROIBIDOS:
            if termo in texto:
                achados.append(f"{p.relative_to(DEMO).as_posix()}: '{termo}' ({texto.count(termo)}x)")
    return achados


if __name__ == "__main__":
    if not REAL.exists():
        sys.exit(f"Projeto real não encontrado em {REAL}")
    problemas = sincronizar()
    vazamentos = verificar_vazamentos()
    for a in problemas:
        print("AVISO:", a)
    for v in vazamentos:
        print("NOME REAL ENCONTRADO:", v)
    if problemas or vazamentos:
        sys.exit(1)
    print("Sincronização concluída sem avisos e sem nomes reais.")
