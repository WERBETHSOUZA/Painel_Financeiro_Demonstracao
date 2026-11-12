"""
views/relatorio_desconto_financeiro_pendente.py
==================================================
Relatório "Descontos Contratuais Pendentes MI": todos os títulos de Mercado
Interno com regra de desconto FINANCEIRO — pendente ou já aplicado, com uma
coluna Status pra diferenciar — usando a mesma base do Contas a Receber
(QUERY_CONTAS_RECEBER.sql).
"""

import pandas as pd
import streamlit as st

from components.buttons import botao_exportar_excel
from components.cards import card_html, render_cards_row, render_tabela_html
from config.classes_desconto import CLASSE_DESCONTO, DESCONTO_DESCRICAO
from services.data_service import carregar_classes_desconto
from utils.exporters import exportar_excel, REGRAS_STATUS_DESCONTO

# Nomes exatamente como pedido — colunas cruas da consulta, sem "embelezar".
_COLUNAS = {
    "ENTRADA":        "ENTRADA",
    "VENCIMENTO":     "VENCIMENTO",
    "PRORROGADO":     "PRORROGADO",
    "SITUACAO":       "SITUACAO",
    "DIAS":           "DIAS",
    "COD_CLIENTE":    "CÓD.CLIENTE",
    "CLIENTE":        "CLIENTE",
    "PARCELA":        "PARC",
    "NF":             "NF",
    "PERC_REGRA":     "%",
    "LIQUIDO_FIN":    "VALOR LIQUIDO NF",
    "LANCAMENTOS_DESCONTO": "CLASSE DESCONTO",
    "DESCONTO_A_APLICAR": "DESCONTO TOTAL",
    "VALOR_ATUALIZADO":   "VALOR ATUALIZADO",
    "STATUS":         "STATUS",
}
_COLUNAS_MULTILINHA = ("LANCAMENTOS_DESCONTO",)
_STATUS_ERRO = ("CLASSE LANÇADA INCORRETA", "LANÇADO A MENOR", "LANÇADO A MAIOR", "CLASSE SEM DESCONTO")
_STATUS_OPCOES = ["PENDENTE", "APLICADO"]   # PENDENTE = tudo que não é APLICADO
_REGRAS_STATUS = REGRAS_STATUS_DESCONTO + [(e, "FFC7CE", "9C0006") for e in _STATUS_ERRO]   # vermelho
# DESC_APLIC_FIN / PERC_APLIC_FIN não entram: este relatório já é só o que está
# pendente, então essas duas colunas viriam sempre em branco — sem sentido mostrar.
# SALDO_EM_ABERTO também sai — no lugar entra VALOR_ATUALIZADO (líquido já com o
# desconto financeiro pendente aplicado).
_COLUNAS_MOEDA = ("VALOR LIQUIDO NF", "DESCONTO TOTAL", "VALOR ATUALIZADO")
_COLUNAS_PERCENTUAL_TEXTO = ("%",)


def _formatar_numero(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def _parse_percentual(texto) -> float:
    """"3.00%" -> 0.03 (fração). Vazio/ inválido -> 0.0."""
    try:
        if pd.isna(texto):
            return 0.0
        return float(str(texto).strip().rstrip("%").replace(",", ".")) / 100
    except (TypeError, ValueError):
        return 0.0


def _cod_geral(valor) -> str:
    """Código sem separador de milhar (51456, não 51.456)."""
    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return "" if pd.isna(valor) else str(valor)


def _chave(cliente, nf, parcela) -> tuple:
    try:
        cliente = str(int(float(cliente)))
    except (TypeError, ValueError):
        cliente = str(cliente).strip()
    return cliente, str(nf).strip(), str(parcela).strip()


def _montar_classes(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta CLASSES_NF (classes de receita da parcela), LANCAMENTOS_DESCONTO
    (classes de desconto a lançar no Senior, % da regra sobre cada classe, classes
    iguais somadas), LANCADO_MEGA (ação 948, nome na tela: LANÇADO_MEGA) e STATUS (PENDENTE, APLICADO quando tudo confere, ou o erro). Linhas separadas por quebra de linha."""
    df = df.copy()
    df["CLASSES_NF"] = df["LANCAMENTOS_DESCONTO"] = df["LANCADO_MEGA"] = ""
    df["STATUS"] = "PENDENTE"
    base = carregar_classes_desconto(
        tuple(sorted({int(float(n)) for n in df["NF"] if str(n).strip().isdigit()})),
        tuple(sorted({int(float(c)) for c in df["COD_CLIENTE"].dropna()})),
    )
    if base.empty:
        return df
    base["_k"] = [_chave(c, n, p) for c, n, p in zip(base["COD_CLIENTE"], base["NF"], base["PARCELA"])]
    classes = {k: g for k, g in base[base["TIPO"] == "CLASSE"].groupby("_k")}
    lancados = {k: g for k, g in base[base["TIPO"] == "DESCONTO"].groupby("_k")}

    for i, linha in df.iterrows():
        k = _chave(linha["COD_CLIENTE"], linha["NF"], linha["PARCELA"])
        perc = _parse_percentual(linha["PERC_REGRA"])
        g = classes.get(k)
        if g is None:
            continue
        g = g.sort_values("REDUZIDO")
        df.at[i, "CLASSES_NF"] = "\n".join(
            f"{int(r.REDUZIDO)} - {r.DESCRICAO} - R$ {_formatar_numero(r.VALOR)}" for r in g.itertuples()
        )
        por_desc, sem = {}, []
        for r in g.itertuples():
            dest = CLASSE_DESCONTO.get(int(r.REDUZIDO))
            if dest is None:
                sem.append(f"SEM CLASSE: {int(r.REDUZIDO)}")
            else:
                por_desc[dest] = por_desc.get(dest, 0.0) + round(float(r.VALOR) * perc, 2)
        linhas = [f"{d} - {_formatar_numero(v)}" for d, v in sorted(por_desc.items())]
        df.at[i, "LANCAMENTOS_DESCONTO"] = "\n".join(linhas + sem)
        lanc = lancados.get(k)
        if lanc is not None:
            pago = {}
            linhas_l = []
            if lanc is not None:
                for r in lanc.sort_values("REDUZIDO", na_position="last").itertuples():
                    cod = None if pd.isna(r.REDUZIDO) else int(r.REDUZIDO)
                    pago[cod] = pago.get(cod, 0.0) + float(r.VALOR)
                    nome = DESCONTO_DESCRICAO.get(cod, r.DESCRICAO if isinstance(r.DESCRICAO, str) else "SEM CLASSE")
                    linhas_l.append(f"{cod if cod is not None else '-'} - {nome} - R$ {_formatar_numero(r.VALOR)}")
            df.at[i, "LANCADO_MEGA"] = "\n".join(linhas_l)
            df.at[i, "STATUS"] = _conferir(por_desc, pago, bool(sem))
        elif sem:
            df.at[i, "STATUS"] = "CLASSE SEM DESCONTO"
    return df


def resumo_descontos_pendentes(df_cr: pd.DataFrame) -> dict | None:
    """Pendentes do relatório "Descontos Contratuais Pendentes MI" para o card do Contas a Receber MI, com a mesma regra
    dele: MI com regra FINANCEIRO, status pelas classes lançadas no Mega, e erro de mês já encerrado fora da conta.
    Devolve {pendentes, erros, valor, clientes, por_cliente[(cliente, qtd_titulos, desconto)]} (do cliente com mais
    desconto a lançar para o menor), ou None se faltar coluna ou a consulta das classes falhar (o card então some)."""
    obrig = {"MERCADO", "TIPO_REGRA", "LIQUIDO_FIN", "PERC_REGRA", "NF", "PARCELA", "COD_CLIENTE", "ENTRADA", "CLIENTE"}
    if df_cr is None or df_cr.empty or not obrig.issubset(df_cr.columns):
        return None
    f = df_cr[(df_cr["MERCADO"] == "MI") & (df_cr["TIPO_REGRA"] == "FINANCEIRO")].copy()
    if f.empty:
        return {"pendentes": 0, "erros": 0, "valor": 0.0, "clientes": 0, "por_cliente": []}
    try:
        f["DESCONTO_A_APLICAR"] = f["LIQUIDO_FIN"] * f["PERC_REGRA"].apply(_parse_percentual)
        f = _montar_classes(f)
    except Exception:
        return None
    fechado = pd.to_datetime(f["ENTRADA"], errors="coerce") < pd.Timestamp.today().normalize().replace(day=1)
    f = f[~(f["STATUS"].isin(_STATUS_ERRO) & fechado)]
    pend = f[f["STATUS"] == "PENDENTE"].sort_values("DESCONTO_A_APLICAR", ascending=False)
    por_cliente = (
        pend.groupby("COD_CLIENTE").agg(CLIENTE=("CLIENTE", "first"), QTD=("NF", "size"), DESC=("DESCONTO_A_APLICAR", "sum"))
        .sort_values("DESC", ascending=False)
    )
    return {
        "pendentes": len(pend),
        "erros": int(f["STATUS"].isin(_STATUS_ERRO).sum()),
        "valor": float(pend["DESCONTO_A_APLICAR"].sum()),
        "clientes": len(por_cliente),
        "por_cliente": [(str(r.CLIENTE), int(r.QTD), float(r.DESC)) for r in por_cliente.itertuples()],
    }


def _conferir(esperado: dict, pago: dict, sem_classe: bool) -> str:
    """Compara o desconto lançado (por classe) com o esperado. A trava do Mega já impede
    desconto acima do permitido; aqui interessa lançado a menor ou em classe incorreta."""
    if not pago:
        return "PENDENTE"
    if any(c not in esperado for c in pago):
        return "CLASSE LANÇADA INCORRETA"
    if any(pago.get(c, 0.0) < v - 0.05 for c, v in esperado.items()):
        return "LANÇADO A MENOR"
    if any(pago[c] > esperado[c] + 0.05 for c in pago):
        return "LANÇADO A MAIOR"
    return "CLASSE SEM DESCONTO" if sem_classe else "APLICADO"


# Layout do relatório no Excel (igual à planilha do usuário): largura, alinhamento horizontal do
# título e do corpo; texto sempre centralizado na vertical; quebra de linha em CLASSE DESCONTO
# e STATUS; altura da linha pelo número de classes.
_LAYOUT = {   # coluna: (largura, horizontal do título, horizontal do corpo)
    "ENTRADA": (11.9, None, None), "VENCIMENTO": (15.6, None, None), "PRORROGADO": (14.7, None, None),
    "SITUACAO": (10.7, None, None), "DIAS": (7.6, "center", "center"), "CÓD.CLIENTE": (13, None, None),
    "CLIENTE": (64.1, None, None), "PARC": (8.3, None, None), "NF": (8.7, "center", "center"),
    "%": (7.7, "center", None), "VALOR LIQUIDO NF": (20.4, None, None), "CLASSE DESCONTO": (20, None, None),
    "DESCONTO TOTAL": (13.1, "center", None), "VALOR ATUALIZADO": (14.7, "center", None),
    "STATUS": (18.3, "center", "center"),
}
_QUEBRA_CORPO = ("CLASSE DESCONTO", "STATUS")
# data no padrão do Excel (segue o idioma do computador) e código do cliente em formato geral
_FORMATO_NUMERO = {"ENTRADA": "mm-dd-yy", "VENCIMENTO": "mm-dd-yy", "PRORROGADO": "mm-dd-yy", "CÓD.CLIENTE": "General"}


def _ajustar_para_tela(xlsx: bytes, colunas_multilinha: list = ()) -> bytes:
    """Aplica o layout acima, com zoom 90% (relatório inteiro cabe em tela de 24")."""
    import math
    from io import BytesIO
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter

    wb = load_workbook(BytesIO(xlsx))
    ws = wb.active
    nomes = [c.value for c in ws[1]]
    for idx, nome in enumerate(nomes, start=1):
        if nome in _LAYOUT:
            ws.column_dimensions[get_column_letter(idx)].width = _LAYOUT[nome][0]
    for linha in range(1, ws.max_row + 1):
        maior = 1
        for idx, nome in enumerate(nomes, start=1):
            largura, h_cab, h_corpo = _LAYOUT.get(nome, (10, None, None))
            cel = ws.cell(linha, idx)
            if linha > 1 and nome in _FORMATO_NUMERO:
                cel.number_format = _FORMATO_NUMERO[nome]
            if linha == 1:
                cel.alignment = Alignment(horizontal=h_cab, vertical="center", wrap_text=True if nome != "PARC" else None)
                continue
            quebra = nome in _QUEBRA_CORPO
            cel.alignment = Alignment(horizontal=h_corpo, vertical="center", wrap_text=True if quebra else None)
            if quebra:
                linhas = sum(max(1, math.ceil(len(t) / largura)) for t in str(cel.value or "").split("\n"))
                maior = max(maior, linhas)
        ws.row_dimensions[linha].height = 30 if linha == 1 else 15 * maior
    ws.sheet_view.zoomScale = 90
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def render(df_cr: pd.DataFrame) -> None:
    _col_t, _col_at = st.columns([8, 1])
    with _col_t:
        st.title("Descontos Contratuais Pendentes MI")
    with _col_at:
        st.markdown("<div style='margin-top:1.05rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", key="dfp_atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with st.sidebar:
        st.caption("Descontos Contratuais Pendentes MI")
        status_sel = st.multiselect(
            "Status", _STATUS_OPCOES, default=["PENDENTE"], key="rdf_status",
            help="APLICADO = lançado no Mega conforme as classes. PENDENTE = tudo que não está "
                 "aplicado (falta lançar ou tem erro). Deixe em branco para trazer os dois.",
        )
        gerar = st.button("Gerar Relatório", use_container_width=True, key="rdf_gerar")

    if gerar:
        st.session_state["_rdf_gerou"] = True

    if not st.session_state.get("_rdf_gerou"):
        st.info("Clique em **Gerar Relatório** na barra lateral para visualizar.")
        return

    if df_cr is None or df_cr.empty:
        st.warning("Nenhum dado de Contas a Receber disponível.")
        return

    obrigatorias = {"MERCADO", "TIPO_REGRA", "DESC_APLIC_FIN"}
    if not obrigatorias.issubset(df_cr.columns):
        st.warning("Dados incompletos para montar este relatório.")
        return

    df_filtrado = df_cr[
        (df_cr["MERCADO"] == "MI")
        & (df_cr["TIPO_REGRA"] == "FINANCEIRO")
    ].copy()

    if df_filtrado.empty:
        st.success("Nenhum título com regra de desconto financeiro no Mercado Interno.")
        return

    # A fórmula (Líquido x % da regra) vale pra qualquer título, esteja o desconto
    # já aplicado ou não — ela só calcula o que a regra determina. O que diferencia
    # é a coluna Status: PENDENTE (DESC_APLIC_FIN vazio) ou APLICADO (já preenchido).
    df_filtrado["DESCONTO_A_APLICAR"] = df_filtrado["LIQUIDO_FIN"] * df_filtrado["PERC_REGRA"].apply(_parse_percentual)
    df_filtrado["VALOR_ATUALIZADO"] = df_filtrado["LIQUIDO_FIN"] - df_filtrado["DESCONTO_A_APLICAR"]

    df_filtrado = _montar_classes(df_filtrado)

    # Contabilidade fecha o período: erro de um mês já encerrado não dá mais para validar nem
    # corrigir, então sai do relatório. Vale a data de ENTRADA da NF contra o mês atual.
    inicio_mes = pd.Timestamp.today().normalize().replace(day=1)
    fechado = pd.to_datetime(df_filtrado["ENTRADA"], errors="coerce") < inicio_mes
    df_filtrado = df_filtrado[~(df_filtrado["STATUS"].isin(_STATUS_ERRO) & fechado)]
    if df_filtrado.empty:
        st.success("Nenhum título com regra de desconto financeiro no período em aberto.")
        return

    if status_sel:
        # PENDENTE inclui os erros: tudo que não é APLICADO ainda precisa de ação.
        df_filtrado = df_filtrado[df_filtrado["STATUS"].eq("APLICADO").map(
            {True: "APLICADO", False: "PENDENTE"}).isin(status_sel)]
        if df_filtrado.empty:
            st.info("Nenhum título encontrado para o status selecionado.")
            return

    qtd_pendente = int((df_filtrado["STATUS"] == "PENDENTE").sum())
    qtd_aplicado = int((df_filtrado["STATUS"] == "APLICADO").sum())
    qtd_erro = int(df_filtrado["STATUS"].isin(_STATUS_ERRO).sum())

    render_cards_row([
        card_html("Qtd. Títulos", str(len(df_filtrado)), cor_borda="#8B5CF6"),
        card_html("Qtd. Pendente", str(qtd_pendente), cor_borda="#E24B4A"),
        card_html("Qtd. Aplicado", str(qtd_aplicado), cor_borda="#22c55e"),
        card_html("Qtd. com Erro", str(qtd_erro), cor_borda="#F59E0B"),
        card_html("Desconto a Aplicar (total)",
                  "R$ " + _formatar_numero(df_filtrado["DESCONTO_A_APLICAR"].sum()), cor_borda="#639922"),
    ])

    st.divider()
    st.caption(f"{len(df_filtrado)} título(s) encontrado(s).")

    colunas_existentes = [c for c in _COLUNAS if c in df_filtrado.columns]
    df_tela = df_filtrado[colunas_existentes].copy()
    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
        if col in df_tela.columns:
            df_tela[col] = pd.to_datetime(df_tela[col], errors="coerce").dt.strftime("%d/%m/%Y")
    for col in ("VALOR_FATURADO", "LIQUIDO_FIN", "DESCONTO_A_APLICAR", "VALOR_ATUALIZADO"):
        if col in df_tela.columns:
            df_tela[col] = df_tela[col].apply(_formatar_numero)
    df_tela["COD_CLIENTE"] = df_tela["COD_CLIENTE"].apply(_cod_geral)
    for col in _COLUNAS_MULTILINHA:
        if col in df_tela.columns:
            df_tela[col] = df_tela[col].str.replace("\n", " | ", regex=False)
    df_tela = df_tela.rename(columns=_COLUNAS)
    render_tabela_html(df_tela)

    df_excel = df_filtrado[colunas_existentes].copy()
    for col in ("ENTRADA", "VENCIMENTO", "PRORROGADO"):
        if col in df_excel.columns:
            df_excel[col] = pd.to_datetime(df_excel[col], errors="coerce")
    for col in ("VALOR_FATURADO", "LIQUIDO_FIN", "DESCONTO_A_APLICAR", "VALOR_ATUALIZADO"):
        if col in df_excel.columns:
            df_excel[col] = pd.to_numeric(df_excel[col], errors="coerce")
    df_excel["COD_CLIENTE"] = pd.to_numeric(df_excel["COD_CLIENTE"], errors="coerce").astype("Int64")
    df_excel = df_excel.rename(columns=_COLUNAS)
    # % Regra fica como a consulta já devolve (texto "12.30%"),
    # sem virar percentual nativo — mesmo motivo do Contas a Receber: evita que
    # a formatação de % do Excel multiplique o valor por 100 se reaplicada.
    for col in set(_COLUNAS_PERCENTUAL_TEXTO) & set(df_excel.columns):
        df_excel[col] = (
            df_excel[col].astype(str).str.strip()
            .str.replace("-", "", regex=False)
            .replace({"None": "", "nan": ""})
        )

    arquivo_excel = exportar_excel(
        df_excel, "DESCONTO_FINANCEIRO_PENDENTE",
        colunas_situacao=("SITUACAO",), colunas_moeda=_COLUNAS_MOEDA,
        colunas_destacadas=("DESCONTO TOTAL",),
        colunas_status={"STATUS": _REGRAS_STATUS},
    )
    arquivo_excel = _ajustar_para_tela(arquivo_excel)
    botao_exportar_excel(arquivo_excel, "Descontos_Contratuais_Pendentes_MI.xlsx", key="rdf_export")
