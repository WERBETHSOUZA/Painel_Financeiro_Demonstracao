"""
Dados 100% fictícios dos relatórios de Contas a Pagar, Aprovações, Boletos DDA, Adiantamentos e
Extrato bancário. Nomes, valores, contas e CNPJs são inventados (semente fixa: sempre iguais).
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

SEMENTE = 20261021
HOJE = date.today()
INICIO_MES = HOJE.replace(day=1)

_ORGS = {"Organização Alfa": ["Filial Matriz", "Filial Norte", "Filial Sul"],
         "Organização Beta": ["Filial Centro", "Filial Leste"]}
_FORNECEDORES = [
    "AGROPECUARIA VALE VERDE", "TRANSPORTES RAPIDO SUL", "EMBALAGENS PLANALTO", "SERVICOS GERAIS HORIZONTE",
    "MANUTENCAO INDUSTRIAL NORTE", "COMERCIAL ESTRELA DISTRIBUIDORA", "FERTILIZANTES BOA SAFRA", "LOGISTICA COSTA AZUL",
    "SEGURANCA E VIGILANCIA ALFA", "CONSULTORIA CONTABIL MODELO", "COMBUSTIVEIS PRIMAVERA", "MATERIAIS DE ESCRITORIO UNIAO",
    "SEMENTES E INSUMOS CAMPO BELO", "ENERGIA E UTILIDADES BRASIL", "TECNOLOGIA E SISTEMAS ORION",
]
_APROVADORES = ["Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Prado", "Elisa Ramos"]
_SOLICITANTES = ["MARCOS", "RENATA", "CAMILA", "THIAGO", "LUCIANA"]
_CATEGORIAS_ERRO = ["Sem anexo", "Rateio divergente", "Classificação pendente", "Centro de custo ausente"]
_CLASSES = ["Insumos agrícolas", "Frete", "Manutenção", "Serviços de terceiros", "Utilidades", "Material de consumo"]
_CCUSTOS = ["Operações", "Administrativo", "Logística", "Comercial"]
_PROJETOS = ["Safra 2026", "Expansão", "Manutenção geral", "Sem projeto"]


def _cnpj_ficticio(rng):
    base = rng.integers(10_000_000, 99_999_999)
    return f"{base:08d}"[:2] + "." + f"{base:08d}"[2:5] + "." + f"{base:08d}"[5:] + f"/0001-{rng.integers(10, 99)}"


def _fmt(d):
    return d.strftime("%d/%m/%Y")


def gerar_extra():
    rng = np.random.default_rng(SEMENTE)

    # ── Contas a Pagar ────────────────────────────────────────────────────────
    linhas, ap = [], 700100
    for i in range(110):
        org = str(rng.choice(list(_ORGS)))
        filial = str(rng.choice(_ORGS[org]))
        ap += int(rng.integers(1, 5))
        valor = float(np.round(rng.uniform(1.2e3, 9.5e4), 2))
        pago = rng.random() < 0.12
        saldo = float(np.round(valor * (0.5 if pago else 1.0), 2))
        prorr = INICIO_MES + timedelta(days=int(rng.integers(0, max((HOJE - INICIO_MES).days + 12, 1))))
        emissao = prorr - timedelta(days=int(rng.integers(20, 90)))
        entrada = emissao + timedelta(days=int(rng.integers(0, 6)))
        vencto = prorr - timedelta(days=int(rng.integers(0, 4)))
        dias = (prorr - HOJE).days
        status = "VENCIDO" if prorr < HOJE else "A VENCER"
        faixa = ("Vencido 30+ dias" if dias < -30 else "Vencido até 30 dias" if dias < 0 else
                 "A vencer até 30 dias" if dias <= 30 else "A vencer 31 a 60 dias")
        forn = str(rng.choice(_FORNECEDORES))
        tem_erro = rng.random() < 0.16
        classes = str(rng.choice(_CLASSES))
        linhas.append({
            "ORG": org, "FILIAL": filial, "AP": ap, "APROVACAO": str(rng.choice(["Aprovado", "Aprovado", "Pendente"])),
            "APROVADORES": ", ".join(rng.choice(_APROVADORES, size=int(rng.integers(1, 3)), replace=False)),
            "DOCTO": int(rng.integers(10_000, 99_999)), "PARC": int(rng.integers(1, 4)),
            "TIPO_DOCTO": str(rng.choice(["NF", "Boleto", "Fatura"])),
            "TIPO_FAVORECIDO": "Pessoa jurídica",
            "TIPO_CLASSIFICACAO": str(rng.choice(["Fornecedor", "Fornecedor", "Produtor"])),
            "FAVORECIDO": f"{2000 + i} - {forn}", "VALOR": valor, "SALDO": saldo, "STATUS": status, "DIAS": dias,
            "STATUS_DIAS": (f"{abs(dias)} dias vencido" if dias < 0 else f"{dias} dias para vencer" if dias > 0 else "Vence hoje"),
            "FAIXA_DIAS": faixa, "EMISSAO": pd.Timestamp(emissao), "ENTRADA": pd.Timestamp(entrada),
            "VENCTO": pd.Timestamp(vencto), "PRORROGADO": pd.Timestamp(prorr),
            "FORMA_PAGTO": str(rng.choice(["Transferência", "Boleto", "PIX"])),
            "PIX": f"chave{i}@exemplo.com.br" if rng.random() < 0.3 else "",
            "LINHA_DIGITAVEL": "", "COMPLEMENTO": f"Referente ao pedido {int(rng.integers(1000, 9999))}",
            "ACAO": "Compra de mercadoria" if rng.random() < 0.6 else "Prestação de serviço",
            "RATEIO_CLASSES": f"{classes} 100,00%", "RATEIO_CENTRO_CUSTO": f"{rng.choice(_CCUSTOS)} 100,00%",
            "RATEIO_PROJETO": f"{rng.choice(_PROJETOS)} 100,00%",
            "CATEGORIA_ERRO": str(rng.choice(_CATEGORIAS_ERRO)) if tem_erro else None,
            "SOLICITANTE": str(rng.choice(_SOLICITANTES)),
            "STATUS_ANEXO": str(rng.choice(["Com anexo", "Com anexo", "Sem anexo"])),
            "QTD_ANEXOS": int(rng.integers(0, 4)), "NOME_ANEXO": f"nota_{int(rng.integers(100, 999))}.pdf",
        })
    contas_pagar = pd.DataFrame(linhas)

    # ── Aprovações pendentes (datas em texto dd/mm/aaaa, como a tela espera) ─────
    aprov = []
    ap = 810200
    for i in range(48):
        org = str(rng.choice(list(_ORGS)))
        filial = str(rng.choice(_ORGS[org]))
        ap += int(rng.integers(1, 6))
        venc = INICIO_MES + timedelta(days=int(rng.integers(0, max((HOJE - INICIO_MES).days, 1) + 1)))
        emissao = venc - timedelta(days=int(rng.integers(20, 70)))
        valor = float(np.round(rng.uniform(900, 7.5e4), 2))
        aprov.append({
            "ORG": org, "FILIAL": filial, "AP": ap, "STATUS": str(rng.choice(["Aguardando aprovação", "Em análise"])),
            "APROVADORES": ", ".join(rng.choice(_APROVADORES, size=int(rng.integers(1, 3)), replace=False)),
            "TP DOC": str(rng.choice(["NF", "Boleto", "Fatura"])), "DOC": str(int(rng.integers(10_000, 99_999))),
            "PARC": int(rng.integers(1, 4)), "FAVORECIDO": f"{2000 + i} - {rng.choice(_FORNECEDORES)}",
            "SALDO": valor, "VALOR": valor, "EMISSAO": _fmt(emissao), "ENTRADA": _fmt(emissao + timedelta(days=2)),
            "VENCTO": _fmt(venc), "QTD_ANEXOS": int(rng.integers(0, 4)),
            "STATUS_ANEXO": str(rng.choice(["Com anexo", "Sem anexo"])), "NOME_ANEXO": f"doc_{int(rng.integers(100, 999))}.pdf",
            "CATEGORIA_ERRO": str(rng.choice(_CATEGORIAS_ERRO)) if rng.random() < 0.5 else "Sem pendência",
        })
    aprovacoes = pd.DataFrame(aprov)

    # ── Boletos DDA ────────────────────────────────────────────────────────────
    sacados = ["EMPRESA EXEMPLO MATRIZ LTDA", "EMPRESA EXEMPLO FILIAL NORTE LTDA", "EMPRESA EXEMPLO FILIAL SUL LTDA"]
    cnpjs = {s: _cnpj_ficticio(rng) for s in sacados}
    dda = []
    for i in range(130):
        sac = str(rng.choice(sacados))
        dda.append({
            "SACADO": sac, "CNPJ": cnpjs[sac],
            "DT_VENCIMENTO": pd.Timestamp(HOJE + timedelta(days=int(rng.integers(-25, 45)))),
            "VALOR": float(np.round(rng.uniform(450, 8.8e4), 2)),
            "DOCUMENTO": f"DOC{int(rng.integers(10_000, 99_999))}", "NUM_TITULO": f"{int(rng.integers(100_000, 999_999))}",
            "MOTIVO": str(rng.choice(["Pagamento", "Pagamento", "Duplicidade", "Aguardando análise"])),
            "NOSSO_NUMERO": f"{int(rng.integers(10**9, 10**10 - 1))}",
        })
    boletos_dda = pd.DataFrame(dda)

    # ── Inconsistências de lançamentos (gerador separado: não altera os demais números) ──
    rng_e = np.random.RandomState(SEMENTE + 5)
    cat_erros = ["ERRO ACAO SEGMENTO", "ERRO ACAO SEGMENTO", "ERRO TIPO FAVORECIDO CLIENTE",
                 "ERRO CLASSE ADIANTAMENTO", "ERRO ACAO SEGMENTO", "ERRO TIPO FAVORECIDO CLIENTE",
                 "ERRO CLASSE ADIANTAMENTO | ERRO ACAO SEGMENTO", "ERRO ACAO SEGMENTO"]
    rateio = chr(10).join(f"{c} - {n} - {p:.2f}%" for c, n, p in (
        (101, "OPERACOES", 38.40), (102, "ADMINISTRATIVO", 21.10), (103, "LOGISTICA", 18.50),
        (104, "COMERCIAL", 12.00), (105, "TECNOLOGIA", 10.00)))
    erros = []
    for i, cat in enumerate(cat_erros):
        org = str(rng_e.choice(list(_ORGS)))
        filial = str(rng_e.choice(_ORGS[org]))
        erros.append({
            "ORGANIZAÇÃO": org, "CÓD_FILIAL": 10 + i, "NOME_FILIAL": filial, "AP": 701000 + i * 7,
            "DOCUMENTO": f"DOC{int(rng_e.randint(10_000, 99_999))}",
            "DATA": pd.Timestamp(HOJE - timedelta(days=int(rng_e.randint(1, 20)))),
            "SALDO": float(np.round(rng_e.uniform(1.0, 2.0e4), 2)),
            "TIPO_ACAO": str(rng_e.choice(["MVFN", "NFEN", "CPAG", "RECEB"])), "COD_ACAO": int(rng_e.choice([201, 248, 630])),
            "ACAO": str(rng_e.choice(["Tarifas e encargos", "Devolução de vendas", "Provisões diversas a pagar"])),
            "CLASSE": f"{int(rng_e.randint(100, 900))} - {str(rng_e.choice(_CLASSES))}",
            "CENTRO_CUSTO": rateio if i == 6 else f"{int(rng_e.randint(100, 300))} - {str(rng_e.choice(_CCUSTOS)).upper()} - 100%",
            "SOLICITANTE": str(rng_e.choice(["ana.souza", "bruno.lima", "carla.mendes", "diego.prado"])),
            "NUM_LANCTO": 3580000 + i * 3, "NOME_AGENTE": str(rng_e.choice(_FORNECEDORES)),
            "CATEGORIA_ERRO": cat,
        })
    erros = pd.DataFrame(erros)

    return {"contas_pagar": contas_pagar, "aprovacoes": aprovacoes, "boletos_dda": boletos_dda, "erros": erros}
