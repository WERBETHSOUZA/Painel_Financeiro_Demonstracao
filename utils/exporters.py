import pandas as pd
import streamlit as st
from datetime import datetime
from io import BytesIO
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Identificadores (AP, NF, códigos): formato Geral, sem separador de milhar.
_COLUNAS_GERAL_PADRAO = {
    "AP", "NF", "DOC", "Cód. Agente", "COD_FILIAL", "COD_ORG", "COD_AGENTE",
    "COD_CLIENTE", "NUM_LANCTO", "Parcela", "PARC",
    "Cód. Cliente", "Ano", "Semana", "NF", "Nosso Número",
    "Dias", "DIAS",
}

# Cotações de câmbio: sempre com 4 casas decimais.
_COLUNAS_COTACAO_PADRAO = {"Cotação", "Cotacao", "COTACAO", "PTAX Faturamento"}
# Prefixos que também indicam coluna de cotação (ex.: "PTAX 07/10/2026")
_PREFIXOS_COTACAO = ("PTAX ",)

# Nomes de coluna tratados como valor monetário (formato R$ #.##0,00 no Excel).
_COLUNAS_MOEDA_PADRAO = {
    "LIQUIDO_FIN", "SALDO_EM_ABERTO", "VALOR_LIQUIDO_NF",
    "Saldo Total", "Saldo em Aberto", "Valor Total", "Valor Lançado", "Valor",
    "Saldo em Aberto (R$)", "Saldo em Aberto (Moeda)", "Valor da parcela (moeda)",
    "Valor Atualizado (R$)", "Variação (R$)",
    "SALDO", "VALOR",
}


REGRAS_STATUS_DESCONTO = [
    ("PENDENTE", "FFEB9C", "9C5700"),   # amarelo
    ("APLICADO", "BDD7EE", "1F4E78"),   # azul
]
REGRAS_STATUS_BOLETO = [
    ("LIBERADO", "C6EFCE", "006100"),   # verde
    ("BLOQUEADO", "BDD7EE", "1F4E78"),  # azul
]


@st.cache_data(show_spinner=False, max_entries=100)
def exportar_excel(df: pd.DataFrame, nome_aba: str = "RELATORIO", colunas_situacao: tuple = (),
                   colunas_centralizar: tuple = (), colunas_moeda: tuple = (),
                   colunas_percentual: tuple = (), colunas_destacadas: tuple = (),
                   colunas_status: dict = None,
                   colunas_verde_vermelho: tuple = (),
                   colunas_valor_abs: tuple = (),
                   colunas_sempre_verde: tuple = (),
                   colunas_sempre_vermelho: tuple = (),
                   colunas_cor_por_situacao: tuple = (),
                   colunas_situacao_sem_fundo: tuple = ()) -> bytes:
    # colunas_valor_abs: exibe sem sinal (▼ só pela cor) mas mantém valor real para coloração condicional
    """Serializa um DataFrame em bytes no formato .xlsx, com o cabeçalho
    estilizado (fundo azul escuro, texto branco em negrito), largura de
    coluna ajustada ao conteúdo, a primeira linha congelada e colunas
    numéricas/monetárias formatadas como número (ex: 11.020,00), não texto."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)

        planilha = writer.sheets[nome_aba]

        # ── Cabeçalho: fundo azul escuro, texto branco em negrito ──────────
        fonte_header = Font(color="FFFFFF", bold=True)
        fundo_header = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        for celula in planilha[1]:
            celula.font = fonte_header
            celula.fill = fundo_header
            celula.alignment = Alignment(vertical="center")

        # ── Zebra: linhas alternadas branco / azul claro ─────────────────
        # Aplicado antes das demais regras de cor; fills diretos posteriores
        # (destacadas, pos/neg) sobrescrevem; formatação condicional tem prioridade.
        _fill_par  = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        _fill_impar = PatternFill(start_color="EEF4FB", end_color="EEF4FB", fill_type="solid")
        for linha in range(2, len(df) + 2):
            _fill = _fill_par if linha % 2 == 0 else _fill_impar
            for col in range(1, len(df.columns) + 1):
                planilha.cell(row=linha, column=col).fill = _fill

        # ── Colunas numéricas: aplica formato de número/moeda nas células ──
        for i, coluna in enumerate(df.columns, start=1):
            if pd.api.types.is_datetime64_any_dtype(df[coluna]):
                # Data de verdade, exibida como dd/mm/aaaa (permite filtrar por ano/mês no Excel).
                letra = get_column_letter(i)
                for linha in range(2, len(df) + 2):
                    planilha[f"{letra}{linha}"].number_format = "dd/mm/yyyy"
                continue
            eh_numerica = pd.api.types.is_numeric_dtype(df[coluna])
            if eh_numerica:
                letra = get_column_letter(i)
                if coluna == "Prazo":
                    formato = '0" dias"'
                elif coluna in colunas_percentual:
                    # O valor já vem como percentual (ex.: 12.3 = "12,30%"), sem dividir por
                    # 100 — o "%" aqui é só um sufixo de exibição, não o formato nativo do Excel.
                    # Se também for abs, usa formato que esconde o sinal negativo.
                    formato = '0.00"%";0.00"%"' if coluna in colunas_valor_abs else '0.00"%"'
                elif coluna in colunas_valor_abs:
                    # Exibe sem sinal mas mantém valor real para coloração condicional
                    formato = "#,##0.00;#,##0.00"
                elif coluna in colunas_moeda:
                    formato = "#,##0.00"   # forçado pela tela (ex.: coluna "NF" que é valor, não número de nota)
                elif coluna in _COLUNAS_GERAL_PADRAO:
                    formato = "General"
                elif coluna in _COLUNAS_COTACAO_PADRAO or any(coluna.startswith(p) for p in _PREFIXOS_COTACAO):
                    formato = "#,##0.0000"
                elif coluna in _COLUNAS_MOEDA_PADRAO:
                    formato = "#,##0.00"
                else:
                    formato = "#,##0"
                for linha in range(2, len(df) + 2):
                    planilha[f"{letra}{linha}"].number_format = formato

        # ── Colunas centralizadas (cabeçalho e células) ──
        for i, coluna in enumerate(df.columns, start=1):
            if coluna in colunas_centralizar:
                letra = get_column_letter(i)
                for linha in range(1, len(df) + 2):
                    planilha[f"{letra}{linha}"].alignment = Alignment(horizontal="center", vertical="center")

        # ── Colunas destacadas (fundo azul claro, pra chamar atenção) ──
        if colunas_destacadas:
            fundo_destaque = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
            for i, coluna in enumerate(df.columns, start=1):
                if coluna not in colunas_destacadas:
                    continue
                letra = get_column_letter(i)
                for linha in range(2, len(df) + 2):
                    planilha[f"{letra}{linha}"].fill = fundo_destaque

        # ── Cores de situação (VENCIDO / A VENCER / BAIXADO), igual ao Contas a Pagar ──
        if colunas_situacao and len(df) > 0:
            from openpyxl.formatting.rule import FormulaRule
            for i, coluna in enumerate(df.columns, start=1):
                if coluna not in colunas_situacao:
                    continue
                letra = get_column_letter(i)
                faixa = f"{letra}2:{letra}{len(df) + 1}"
                for texto, fundo, fonte in _REGRAS_STATUS_CAP:
                    planilha.conditional_formatting.add(
                        faixa,
                        FormulaRule(
                            formula=[f'EXACT({letra}2,"{texto}")'],
                            fill=PatternFill(start_color=fundo, end_color=fundo, fill_type="solid"),
                            font=Font(color=fonte),
                        ),
                    )

        # ── Cores de Status custom (ex.: PENDENTE/APLICADO, LIBERADO/BLOQUEADO) ──
        # Usa prefixo (LEFT) em vez de EXACT porque o valor pode vir com sufixo
        # explicativo (ex.: "BLOQUEADO - Desconto Faturamento pendente").
        if colunas_status and len(df) > 0:
            from openpyxl.formatting.rule import FormulaRule
            for coluna, regras in colunas_status.items():
                if coluna not in df.columns:
                    continue
                i = list(df.columns).index(coluna) + 1
                letra = get_column_letter(i)
                faixa = f"{letra}2:{letra}{len(df) + 1}"
                for texto, fundo, fonte in regras:
                    planilha.conditional_formatting.add(
                        faixa,
                        FormulaRule(
                            formula=[f'EXACT(LEFT({letra}2,{len(texto)}),"{texto}")'],
                            fill=PatternFill(start_color=fundo, end_color=fundo, fill_type="solid"),
                            font=Font(color=fonte),
                        ),
                    )

        # ── Verde/Vermelho por sinal — somente cor da fonte, sem fundo ──────────
        if colunas_verde_vermelho and len(df) > 0:
            from openpyxl.formatting.rule import CellIsRule, FormulaRule
            fonte_verde = Font(color="00B050", bold=True)
            fonte_verm  = Font(color="FF0000", bold=True)
            sem_fill    = PatternFill(fill_type=None)   # garante que nenhum fundo seja aplicado
            for i, coluna in enumerate(df.columns, start=1):
                if coluna not in colunas_verde_vermelho:
                    continue
                letra = get_column_letter(i)
                faixa = f"{letra}2:{letra}{len(df) + 1}"
                if pd.api.types.is_numeric_dtype(df[coluna]):
                    planilha.conditional_formatting.add(
                        faixa, CellIsRule(operator="greaterThanOrEqual", formula=["0"],
                                          fill=sem_fill, font=fonte_verde))
                    planilha.conditional_formatting.add(
                        faixa, CellIsRule(operator="lessThan", formula=["0"],
                                          fill=sem_fill, font=fonte_verm))
                else:
                    # texto "▲ Positiva" / "▼ Negativa"
                    planilha.conditional_formatting.add(
                        faixa, FormulaRule(
                            formula=[f'LEFT({letra}2,1)="▲"'],
                            fill=sem_fill, font=fonte_verde))
                    planilha.conditional_formatting.add(
                        faixa, FormulaRule(
                            formula=[f'LEFT({letra}2,1)="▼"'],
                            fill=sem_fill, font=fonte_verm))

        # ── Sempre verde / sempre vermelho (fonte bold, sem fundo) ───────────────
        for _cols, _cor_hex in ((colunas_sempre_verde, "00B050"), (colunas_sempre_vermelho, "FF0000")):
            if _cols and len(df) > 0:
                from openpyxl.formatting.rule import CellIsRule as _CIR
                _fonte = Font(color=_cor_hex, bold=True)
                _fill0 = PatternFill(fill_type=None)
                for i, coluna in enumerate(df.columns, start=1):
                    if coluna not in _cols:
                        continue
                    letra = get_column_letter(i)
                    faixa = f"{letra}2:{letra}{len(df) + 1}"
                    planilha.conditional_formatting.add(
                        faixa, _CIR(operator="greaterThan", formula=["0"],
                                    fill=_fill0, font=_fonte))

        # ── Cor da fonte por SITUACAO (verde=A VENCER / vermelho=VENCIDO) ─────
        if colunas_cor_por_situacao and len(df) > 0:
            from openpyxl.formatting.rule import FormulaRule as _FR
            _fonte_v  = Font(color="00B050", bold=True)
            _fonte_r  = Font(color="FF0000", bold=True)
            _sem_fill = PatternFill(fill_type=None)
            _sit_ref  = next((c for c in (*colunas_situacao, *colunas_situacao_sem_fundo) if c in df.columns), None)
            if _sit_ref:
                _sit_idx  = list(df.columns).index(_sit_ref) + 1
                _sit_l    = get_column_letter(_sit_idx)
                for _i, _col in enumerate(df.columns, start=1):
                    if _col not in colunas_cor_por_situacao:
                        continue
                    _l    = get_column_letter(_i)
                    _fx   = f"{_l}2:{_l}{len(df) + 1}"
                    planilha.conditional_formatting.add(
                        _fx, _FR(formula=[f'EXACT({_sit_l}2,"A VENCER")'], fill=_sem_fill, font=_fonte_v))
                    planilha.conditional_formatting.add(
                        _fx, _FR(formula=[f'EXACT({_sit_l}2,"VENCIDO")'],  fill=_sem_fill, font=_fonte_r))

        # ── Situação sem fundo (só fonte bold verde/vermelho) ────────────────────
        if colunas_situacao_sem_fundo and len(df) > 0:
            from openpyxl.formatting.rule import FormulaRule as _FR2
            _sem = PatternFill(fill_type=None)
            for _i, _col in enumerate(df.columns, start=1):
                if _col not in colunas_situacao_sem_fundo:
                    continue
                _l  = get_column_letter(_i)
                _fx = f"{_l}2:{_l}{len(df) + 1}"
                planilha.conditional_formatting.add(
                    _fx, _FR2(formula=[f'EXACT({_l}2,"VENCIDO")'],
                              fill=_sem, font=Font(color="FF0000", bold=True)))
                planilha.conditional_formatting.add(
                    _fx, _FR2(formula=[f'EXACT({_l}2,"A VENCER")'],
                              fill=_sem, font=Font(color="00B050", bold=True)))

        # ── Filtro (autofiltro) no cabeçalho e bordas finas em todas as células ──
        ultima_coluna = get_column_letter(len(df.columns))
        ultima_linha = len(df) + 1
        planilha.auto_filter.ref = f"A1:{ultima_coluna}{ultima_linha}"

        borda_fina = Side(style="thin", color="B7B7B7")
        bordas = Border(left=borda_fina, right=borda_fina, top=borda_fina, bottom=borda_fina)
        for linha in planilha.iter_rows(min_row=1, max_row=ultima_linha, min_col=1, max_col=len(df.columns)):
            for celula in linha:
                celula.border = bordas

        # ── Largura das colunas, ajustada ao maior conteúdo (com limites) ──
        for i, coluna in enumerate(df.columns, start=1):
            maior_valor = 0
            if not df.empty:
                for valor in df[coluna]:
                    if pd.isna(valor):
                        continue
                    tamanho = len(str(valor))
                    if tamanho > maior_valor:
                        maior_valor = tamanho
            largura = max(len(str(coluna)), maior_valor) + 2
            largura = min(max(largura, 10), 60)
            # Colunas de valor: cabem até 10.000.000,00 (13 caracteres) com folga.
            if coluna in _COLUNAS_MOEDA_PADRAO:
                largura = max(largura, 16)
            planilha.column_dimensions[get_column_letter(i)].width = largura

        # ── Congela a primeira linha (cabeçalho) ────────────────────────────
        planilha.freeze_panes = "A2"

    return output.getvalue()


# ── Grupos de Crédito: exportação customizada ────────────────────────────────

@st.cache_data(show_spinner=False, max_entries=20)
def exportar_excel_grupos_credito(df: pd.DataFrame, nome_aba: str = "GRUPOS_CREDITO") -> bytes:
    """Excel do relatório de Grupos de Crédito.

    Espera df com colunas: Cód., Grupo, Limite, Disponível, % Util.,
    Consumido NF, Consumido PV, Documentação, Faturamento.
    Colunas monetárias devem ser float; Cód. deve ser string.
    """
    _MOEDA      = {"Limite", "Disponível", "Consumido NF", "Consumido PV"}
    _FONT_VERDE = Font(color="006100", bold=True)
    _FONT_VERM  = Font(color="9C0006", bold=True)
    _FILL_VERDE = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    _FILL_VERM  = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    # Zeros nas colunas monetárias viram NaN (célula vazia no Excel)
    df = df.copy()
    for _c in _MOEDA:
        if _c in df.columns:
            df[_c] = pd.to_numeric(df[_c], errors="coerce")
            df[_c] = df[_c].where(df[_c] != 0)

    # Cód.: converte para número onde possível (ex.: "44082" → 44082)
    if "Cód." in df.columns:
        _cod_num = pd.to_numeric(df["Cód."], errors="coerce")
        df["Cód."] = _cod_num.where(_cod_num.notna(), df["Cód."])

    # Linhas 1-2 = título + subtítulo; dados começam na linha 3 (startrow=2)
    _HDR_ROW  = 3   # linha do cabeçalho das colunas
    _DATA_INI = 4   # primeira linha de dados
    _DATA_FIM = _DATA_INI + len(df) - 1
    _N_COLS   = len(df.columns)
    _ULTIMA   = get_column_letter(_N_COLS)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba, startrow=2)
        ws = writer.sheets[nome_aba]

        # ── Contagens para o resumo no canto direito ────────────────────────
        _cnt_fat = int(df["Faturamento"].astype(str).str.upper().str.contains("BLOQ").sum()) if "Faturamento" in df.columns else 0
        _cnt_doc = int(df["Documentação"].astype(str).str.upper().str.contains("BLOQ").sum()) if "Documentação" in df.columns else 0

        _FILL_TIT  = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        _FILL_SUB  = _FILL_TIT

        # ── Linhas de título (1) e subtítulo (2) ────────────────────────────
        # Merge dinâmico: A até N-2; últimas 2 colunas reservadas para o resumo
        _COL_MERGE_FIM = get_column_letter(_N_COLS - 2)
        _COL_RESUMO_L  = get_column_letter(_N_COLS - 1)   # label (ex: "Fat. Bloqueado")
        _COL_RESUMO_V  = get_column_letter(_N_COLS)        # valor (contagem)
        ws.merge_cells(f"A1:{_COL_MERGE_FIM}1")
        ws.merge_cells(f"A2:{_COL_MERGE_FIM}2")

        cel_tit = ws["A1"]
        cel_tit.value     = "Grupos de Crédito"
        cel_tit.font      = Font(color="FFFFFF", bold=True, size=13)
        cel_tit.fill      = _FILL_TIT
        cel_tit.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[1].height = 22

        cel_sub = ws["A2"]
        cel_sub.value     = f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
        cel_sub.font      = Font(color="FFFFFF", size=10)
        cel_sub.fill      = _FILL_SUB
        cel_sub.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[2].height = 16

        # Aplica fundo nas colunas do resumo (dinâmicas)
        for _r, _fill in ((1, _FILL_TIT), (2, _FILL_SUB)):
            for _ltr in (_COL_RESUMO_L, _COL_RESUMO_V):
                ws[f"{_ltr}{_r}"].fill = _fill

        # Resumo — linha 1: "Fat. Bloqueado" | contagem
        ws[f"{_COL_RESUMO_L}1"].value     = "Fat. Bloqueado"
        ws[f"{_COL_RESUMO_L}1"].font      = Font(color="FFCCCC", size=10)
        ws[f"{_COL_RESUMO_L}1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws[f"{_COL_RESUMO_V}1"].value     = _cnt_fat
        ws[f"{_COL_RESUMO_V}1"].font      = Font(color="FFFFFF", bold=True, size=11)
        ws[f"{_COL_RESUMO_V}1"].alignment = Alignment(horizontal="center", vertical="center")

        # Resumo — linha 2: "Doc. Bloqueado" | contagem
        ws[f"{_COL_RESUMO_L}2"].value     = "Doc. Bloqueado"
        ws[f"{_COL_RESUMO_L}2"].font      = Font(color="FFCCCC", size=10)
        ws[f"{_COL_RESUMO_L}2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws[f"{_COL_RESUMO_V}2"].value     = _cnt_doc
        ws[f"{_COL_RESUMO_V}2"].font      = Font(color="FFFFFF", bold=True, size=11)
        ws[f"{_COL_RESUMO_V}2"].alignment = Alignment(horizontal="center", vertical="center")

        # ── Cabeçalho das colunas (linha 3): fundo azul escuro, branco negrito
        fundo_hdr = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        fonte_hdr = Font(color="FFFFFF", bold=True)
        for cel in ws[_HDR_ROW]:
            cel.font      = fonte_hdr
            cel.fill      = fundo_hdr
            cel.alignment = Alignment(vertical="center")

        idx_col = {col: i for i, col in enumerate(df.columns, start=1)}

        for i, col in enumerate(df.columns, start=1):
            letra = get_column_letter(i)

            # Formato numérico: monetário
            if col in _MOEDA:
                for row in range(_DATA_INI, _DATA_FIM + 1):
                    ws[f"{letra}{row}"].number_format = "#,##0.00"

            # Cód.: formato número inteiro
            if col == "Cód.":
                for row in range(_DATA_INI, _DATA_FIM + 1):
                    ws[f"{letra}{row}"].number_format = "0"

            # Documentação e Faturamento: fundo + texto colorido por valor
            if col in ("Documentação", "Faturamento"):
                for row in range(_DATA_INI, _DATA_FIM + 1):
                    cel = ws[f"{letra}{row}"]
                    val = str(cel.value or "").upper()
                    if "BLOQ" in val:
                        cel.font = _FONT_VERM
                        cel.fill = _FILL_VERM
                    elif val and val != "-":
                        cel.font = _FONT_VERDE
                        cel.fill = _FILL_VERDE
                    cel.alignment = Alignment(horizontal="center", vertical="center")

        # % Util.: formato percentual, centraliza e colore por faixa (sem fundo, negrito)
        if "% Util." in idx_col:
            letra = get_column_letter(idx_col["% Util."])
            for row in range(_DATA_INI, _DATA_FIM + 1):
                cel = ws[f"{letra}{row}"]
                if cel.value is not None:
                    cel.number_format = "0.00%"
                    try:
                        v = float(cel.value)
                        if v >= 0.80:
                            cel.font = Font(color="CC0000", bold=True)
                        elif v >= 0.50:
                            cel.font = Font(color="E97020", bold=True)
                        else:
                            cel.font = Font(color="1A7D3A", bold=True)
                    except (TypeError, ValueError):
                        pass
            for row in range(_HDR_ROW, _DATA_FIM + 1):
                ws[f"{letra}{row}"].alignment = Alignment(horizontal="center", vertical="center")

        # Cód.: centraliza
        if "Cód." in idx_col:
            letra = get_column_letter(idx_col["Cód."])
            for row in range(_HDR_ROW, _DATA_FIM + 1):
                ws[f"{letra}{row}"].alignment = Alignment(horizontal="center", vertical="center")

        # Bordas finas (apenas na tabela, não no título/subtítulo)
        borda_fina = Side(style="thin", color="B7B7B7")
        bordas = Border(left=borda_fina, right=borda_fina, top=borda_fina, bottom=borda_fina)
        for row in ws.iter_rows(min_row=_HDR_ROW, max_row=_DATA_FIM, min_col=1, max_col=_N_COLS):
            for cel in row:
                cel.border = bordas

        # Mercado, Tipo e Classificação: centraliza
        for _col_c in ("Mercado", "Tipo", "Classificação"):
            if _col_c in idx_col:
                _l = get_column_letter(idx_col[_col_c])
                for row in range(_HDR_ROW, _DATA_FIM + 1):
                    ws[f"{_l}{row}"].alignment = Alignment(horizontal="center", vertical="center")

        # Classificação: cor + negrito sem fundo por faixa
        if "Classificação" in idx_col:
            _l = get_column_letter(idx_col["Classificação"])
            _mapa_classif = {
                "Livre":    Font(color="1A7D3A", bold=True),
                "Atenção":  Font(color="E97020", bold=True),
                "Em Risco": Font(color="CC0000", bold=True),
            }
            for row in range(_DATA_INI, _DATA_FIM + 1):
                cel = ws[f"{_l}{row}"]
                fonte = _mapa_classif.get(str(cel.value or "").strip())
                if fonte:
                    cel.font = fonte

        # Largura das colunas
        _LARGURAS = {"Cód.": 8, "Grupo": 40, "Tipo": 18, "Limite": 16,
                     "Consumido NF": 16, "Consumido PV": 16, "% Util.": 10,
                     "Classificação": 12, "Disponível": 16, "Documentação": 18, "Faturamento": 14}
        for i, col in enumerate(df.columns, start=1):
            ws.column_dimensions[get_column_letter(i)].width = _LARGURAS.get(col, 14)

        # Autofiltro na linha do cabeçalho + congela título/subtítulo/cabeçalho
        ws.auto_filter.ref = f"A{_HDR_ROW}:{_ULTIMA}{_DATA_FIM}"
        ws.freeze_panes    = f"A{_DATA_INI}"

    return output.getvalue()


# ── Contas a Pagar: mesmo padrão visual da planilha modelo ──────────────────
_LARGURAS_CAP = {
    "ORG": 46, "FILIAL": 38, "AP": 8, "APROVACAO": 14, "APROVADORES": 20,
    "DOCTO": 15, "PARC": 6, "TIPO_DOCTO": 12, "TIPO_FAVORECIDO": 18, "TIPO_CLASSIFICACAO": 18, "CÓD_FORNEC": 14, "FORNECEDOR": 45,
    "FAVORECIDO": 45, "VALOR": 14, "SALDO": 14, "STATUS": 10, "DIAS": 6,
    "STATUS_DIAS": 14, "FAIXA_DIAS": 20, "EMISSAO": 12, "ENTRADA": 12,
    "VENCTO": 12, "PRORROGADO": 12, "FORMA_PAGTO": 27, "PIX": 12,
    "LINHA_DIGITAVEL": 50, "COMPLEMENTO": 20, "ACAO": 56, "RATEIO_CLASSES": 53,
    "RATEIO_CENTRO_CUSTO": 49, "RATEIO_PROJETO": 38, "CATEGORIA_ERRO": 18,
    "SOLICITANTE": 18, "STATUS_ANEXO": 15, "QTD_ANEXOS": 13, "NOME_ANEXO": 59,
}
_CENTRALIZAR_CAP = {"PARC", "DIAS", "QTD_ANEXOS"}
_COLUNAS_MOEDA_CAP = {"VALOR", "SALDO"}
_COLUNAS_DATA_CAP = {"EMISSAO", "ENTRADA", "VENCTO", "PRORROGADO"}
_FORMATO_CONTABIL = r'_-* #,##0.00_-;\-* #,##0.00_-;_-* "-"??_-;_-@_-'

# (texto exato, cor de fundo, cor da fonte)
_REGRAS_STATUS_CAP = [
    ("VENCIDO", "FFC7CE", "9C0006"),
    ("A VENCER", "FFEB9C", "9C5700"),
    ("BAIXADO", "C6EFCE", "006100"),
]
_REGRAS_APROVACAO_CAP = [
    ("Aprovado", "C6EFCE", "006100"),
    ("Em Aprovação", "FFEB9C", "9C5700"),
    ("Não Aprovado", "FFC7CE", "9C0006"),
]


@st.cache_data(show_spinner=False, max_entries=100)
def exportar_excel_contas_pagar(df: pd.DataFrame, nome_aba: str = "CONTAS A PAGAR") -> bytes:
    """Excel do Contas a Pagar no padrão da planilha modelo: cabeçalho azul-marinho
    com texto branco em negrito, bordas finas, larguras fixas por coluna, valores em
    formato contábil, datas dd/mm/aaaa e cores condicionais em STATUS e APROVACAO."""
    from openpyxl.styles import Border, Side
    from openpyxl.formatting.rule import FormulaRule

    df = df.copy()
    for col in _COLUNAS_DATA_CAP & set(df.columns):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in _COLUNAS_MOEDA_CAP & set(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)
        planilha = writer.sheets[nome_aba]

        borda = Side(style="thin")
        bordas = Border(left=borda, right=borda, top=borda, bottom=borda)
        fonte_header = Font(color="FFFFFF", bold=True)
        fundo_header = PatternFill(start_color="163E64", end_color="163E64", fill_type="solid")
        ultima_linha = len(df) + 1

        for i, coluna in enumerate(df.columns, start=1):
            letra = get_column_letter(i)
            planilha.column_dimensions[letra].width = _LARGURAS_CAP.get(coluna, 18)

            cab = planilha.cell(row=1, column=i)
            cab.font = fonte_header
            cab.fill = fundo_header
            cab.border = bordas
            if coluna in _CENTRALIZAR_CAP:
                cab.alignment = Alignment(horizontal="center")

            for linha in range(2, ultima_linha + 1):
                celula = planilha.cell(row=linha, column=i)
                celula.border = bordas
                if coluna in _COLUNAS_MOEDA_CAP:
                    celula.number_format = _FORMATO_CONTABIL
                elif coluna in _COLUNAS_DATA_CAP:
                    celula.number_format = "dd/mm/yyyy"
                if coluna in _CENTRALIZAR_CAP:
                    celula.alignment = Alignment(horizontal="center")

            regras = {"STATUS": _REGRAS_STATUS_CAP, "APROVACAO": _REGRAS_APROVACAO_CAP}.get(coluna)
            if regras and len(df) > 0:
                faixa = f"{letra}2:{letra}{ultima_linha}"
                for texto, fundo, fonte in regras:
                    planilha.conditional_formatting.add(
                        faixa,
                        FormulaRule(
                            formula=[f'EXACT({letra}2,"{texto}")'],
                            fill=PatternFill(start_color=fundo, end_color=fundo, fill_type="solid"),
                            font=Font(color=fonte),
                        ),
                    )

        # ── Filtro (autofiltro) no cabeçalho — mesmo padrão dos demais relatórios ──
        ultima_coluna_letra = get_column_letter(len(df.columns))
        planilha.auto_filter.ref = f"A1:{ultima_coluna_letra}{ultima_linha}"

    return output.getvalue()


@st.cache_data(show_spinner=False, max_entries=50)
def exportar_excel_faturamento_cliente_grupo(
    titulo: str,
    kpis: list,
    faturamento_por_ano: list,
    clientes_grupo: list | None,
    por_estado: list | None,
    df_titulos: pd.DataFrame,
    clientes_pv_nf: list | None = None,
    nota_rodape: str | None = None,
) -> bytes:
    """Excel do relatório "Faturamento - Cliente/Grupo": aba "Resumo" com as
    tabelas de indicadores, faturamento anual, (só no modo Grupo) top
    clientes, faturamento por estado e clientes do grupo (PV/NF/Total) — sem
    gráfico, só a informação, com cabeçalho azul/negrito e sem linhas de
    grade — e aba "Titulos em Aberto" com a lista completa dos títulos do
    cliente/grupo selecionado."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    ws.sheet_view.showGridLines = False

    fonte_header = Font(color="FFFFFF", bold=True)
    fundo_header = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
    fonte_secao = Font(bold=True, size=12)

    ws["A1"] = titulo or "Faturamento"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Gerado em {datetime.now():%d/%m/%Y %H:%M}"
    ws["A2"].font = Font(size=9, color="808080")
    if nota_rodape:
        ws["A3"] = nota_rodape
        ws["A3"].font = Font(size=10, bold=True, color="A07000")

    FORMATO_MOEDA = "#,##0.00"
    FORMATO_PERCENTUAL = "0.00%"
    FORMATO_COTACAO = "#,##0.0000"

    def _tabela(linha_titulo: int, col_ini: int, titulo_secao: str, col1: str, dados: list,
                formato_valor: str = FORMATO_MOEDA, label_numerico: bool = False,
                label_centralizado: bool = False, valor_alinhado_direita: bool = False):
        """Escreve um bloco "título da seção" + cabeçalho azul + linhas de dado,
        a partir de (linha_titulo, col_ini). `dados` é uma lista de (label, valor)
        ou (label, valor, "moeda"/"percentual"/"texto") — quando o tipo não é
        informado, usa `formato_valor` (moeda, por padrão). `label_numerico`
        escreve o label como número (ex.: Ano), centralizado. `label_centralizado`
        centraliza o label sem mudar o tipo (ex.: Estado, texto). `valor_alinhado_direita`
        força alinhamento à direita na coluna de valor mesmo quando é texto (ex.: Situação).
        Devolve a última linha usada."""
        letra_label = get_column_letter(col_ini)
        letra_valor = get_column_letter(col_ini + 1)
        ws[f"{letra_label}{linha_titulo}"] = titulo_secao
        ws[f"{letra_label}{linha_titulo}"].font = fonte_secao
        linha_header = linha_titulo + 1
        ws[f"{letra_label}{linha_header}"] = col1
        ws[f"{letra_valor}{linha_header}"] = "Valor"
        for cel in (ws[f"{letra_label}{linha_header}"], ws[f"{letra_valor}{linha_header}"]):
            cel.font = fonte_header
            cel.fill = fundo_header
        for i, item in enumerate(dados, start=linha_header + 1):
            label, valor, tipo = (item[0], item[1], item[2]) if len(item) == 3 else (item[0], item[1], None)
            cel_label = ws[f"{letra_label}{i}"]
            if label_numerico:
                cel_label.value = label
            else:
                cel_label.value = str(label)
            if label_numerico or label_centralizado:
                cel_label.alignment = Alignment(horizontal="center")
            cel_valor = ws[f"{letra_valor}{i}"]
            cel_valor.value = valor
            if valor_alinhado_direita:
                cel_valor.alignment = Alignment(horizontal="right")
            if tipo == "percentual":
                cel_valor.number_format = FORMATO_PERCENTUAL
            elif tipo == "percentual_alerta":
                # % Inadimplência: verde/âmbar/vermelho pela mesma faixa do painel.
                cel_valor.number_format = FORMATO_PERCENTUAL
                pct = float(valor) * 100
                cor = "22C55E" if pct < 5 else "EF9F27" if pct < 15 else "E24B4A"
                cel_valor.font = Font(bold=True, color=cor)
            elif tipo == "situacao":
                # Verde se liberado/ativo, vermelho se bloqueado/inadimplente — mesma
                # convenção de cor do painel.
                situacao_upper = str(valor).upper()
                if any(t in situacao_upper for t in ("BLOQ", "INADIMPL", "SUSPENS")):
                    cel_valor.font = Font(bold=True, color="E24B4A")
                elif any(t in situacao_upper for t in ("LIBERADO", "ATIVO", "OK", "NORMAL")):
                    cel_valor.font = Font(bold=True, color="22C55E")
            elif tipo == "texto":
                pass
            else:
                cel_valor.number_format = formato_valor
        largura_label = max((len(str(item[0])) for item in dados), default=8)
        ws.column_dimensions[letra_label].width = max(20, min(50, max(largura_label, len(col1)) + 2))
        ws.column_dimensions[letra_valor].width = 16
        return linha_header + len(dados)

    LINHA_TITULO = 4
    kpi_fim = _tabela(LINHA_TITULO, 1, "Resumo geral", "Indicador", kpis,
                       formato_valor=_FORMATO_CONTABIL, valor_alinhado_direita=True)

    COL_DADOS_INICIAL = 4  # coluna D em diante (colunas B/C ficam de respiro)
    col_dados = COL_DADOS_INICIAL

    if faturamento_por_ano:
        _tabela(LINHA_TITULO, col_dados, "Faturamento anual", "Ano", faturamento_por_ano, label_numerico=True)
        col_dados += 3

    if clientes_grupo:
        # 3 colunas (Cód. Agente / Cliente / Valor) — título acima da coluna "Cliente".
        letra_cod = get_column_letter(col_dados)
        letra_nome = get_column_letter(col_dados + 1)
        letra_valor = get_column_letter(col_dados + 2)
        ws[f"{letra_nome}{LINHA_TITULO}"] = "Top Cliente Faturamento"
        ws[f"{letra_nome}{LINHA_TITULO}"].font = fonte_secao
        linha_header = LINHA_TITULO + 1
        ws[f"{letra_cod}{linha_header}"] = "Cód. Agente"
        ws[f"{letra_nome}{linha_header}"] = "Cliente"
        ws[f"{letra_valor}{linha_header}"] = "Valor"
        for cel in (ws[f"{letra_cod}{linha_header}"], ws[f"{letra_nome}{linha_header}"], ws[f"{letra_valor}{linha_header}"]):
            cel.font = fonte_header
            cel.fill = fundo_header
        for i, (cod, nome, valor) in enumerate(clientes_grupo, start=linha_header + 1):
            ws[f"{letra_cod}{i}"] = cod
            ws[f"{letra_nome}{i}"] = str(nome)
            cel_v = ws[f"{letra_valor}{i}"]
            cel_v.value = valor
            cel_v.number_format = FORMATO_MOEDA
        ws.column_dimensions[letra_cod].width = 14
        ws.column_dimensions[letra_nome].width = max(20, min(50, max((len(str(n)) for _, n, _ in clientes_grupo), default=8) + 2))
        ws.column_dimensions[letra_valor].width = 16
        col_dados += 4

    if por_estado:
        _tabela(LINHA_TITULO, col_dados, "Faturamento por Estado", "Estado", por_estado, label_centralizado=True)

    # ── Clientes do grupo (PV/NF/Total — consumo do limite de crédito), só Grupo ──
    if clientes_pv_nf:
        linha_header_grupo = kpi_fim + 3
        cabecalhos = ["Cód. Agente", "Cliente", "PV", "NF", "Total"]
        for j, texto in enumerate(cabecalhos, start=1):
            cel = ws.cell(row=linha_header_grupo, column=j, value=texto)
            cel.font = fonte_header
            cel.fill = fundo_header
        for i, (nome, cod, pv, nf, total) in enumerate(clientes_pv_nf, start=linha_header_grupo + 1):
            ws.cell(row=i, column=1, value=cod)
            ws.cell(row=i, column=2, value=str(nome))
            for col_idx, valor in ((3, pv), (4, nf), (5, total)):
                cel = ws.cell(row=i, column=col_idx, value=valor)
                cel.number_format = _FORMATO_CONTABIL
        maior_nome = max((len(str(n)) for n, *_ in clientes_pv_nf), default=8)
        ws.column_dimensions["B"].width = max(ws.column_dimensions["B"].width or 0, min(60, maior_nome + 2))
        for letra in ("C", "D", "E"):
            ws.column_dimensions[letra].width = max(ws.column_dimensions[letra].width or 0, 16)

    # ── Aba com a lista completa de títulos em aberto ────────────────────────
    ws2 = wb.create_sheet("Títulos em Aberto")
    ws2.sheet_view.showGridLines = False
    if df_titulos is not None and not df_titulos.empty:
        # Coluna de porcentagem em texto (ex.: "% Regra"): mantém como texto, sem
        # formato nativo de %, pelo mesmo motivo do relatório Contas a Receber —
        # evita multiplicar por 100 se alguém reaplicar o % nativo por cima.
        colunas_percentual_texto = {"% Regra", "% Aplic. NF", "% Aplic. Financeiro"}
        # Classifica o formato de cada coluna ANTES de mexer no conteúdo (NaN etc.).
        tipo_coluna = {}
        for col in df_titulos.columns:
            if pd.api.types.is_datetime64_any_dtype(df_titulos[col]):
                tipo_coluna[col] = "data"
            elif col in colunas_percentual_texto:
                tipo_coluna[col] = "texto"
            elif col in _COLUNAS_GERAL_PADRAO:
                tipo_coluna[col] = "geral"
            elif col in _COLUNAS_COTACAO_PADRAO:
                tipo_coluna[col] = "cotacao"
            elif pd.api.types.is_numeric_dtype(df_titulos[col]):
                tipo_coluna[col] = "moeda"
            else:
                tipo_coluna[col] = "texto"

        # NaN não é um valor válido de célula pro openpyxl — troca por None (célula vazia).
        df_titulos = df_titulos.where(df_titulos.notna(), None)
        for j, col in enumerate(df_titulos.columns, start=1):
            cel = ws2.cell(row=1, column=j, value=col)
            cel.font = fonte_header
            cel.fill = fundo_header
        for i, row in enumerate(df_titulos.itertuples(index=False), start=2):
            for j, val in enumerate(row, start=1):
                ws2.cell(row=i, column=j, value=val)
        ultima_linha = len(df_titulos) + 1
        ultima_col = get_column_letter(len(df_titulos.columns))
        ws2.auto_filter.ref = f"A1:{ultima_col}{ultima_linha}"
        for j, col in enumerate(df_titulos.columns, start=1):
            letra = get_column_letter(j)
            tipo = tipo_coluna[col]
            if tipo == "data":
                formato = "dd/mm/yyyy"
            elif tipo == "cotacao":
                formato = FORMATO_COTACAO
            elif tipo == "moeda":
                formato = _FORMATO_CONTABIL
            else:
                formato = None
            if formato:
                for linha in range(2, ultima_linha + 1):
                    ws2[f"{letra}{linha}"].number_format = formato
            maior = df_titulos[col].map(lambda v: len(str(v)) if pd.notna(v) else 0).max() if len(df_titulos) else 0
            largura = max(len(str(col)), maior) + 2
            ws2.column_dimensions[letra].width = min(max(largura, 10), 40)
        ws2.freeze_panes = "A2"

        # ── Cores de situação (VENCIDO / A VENCER), igual aos demais relatórios ──
        if "Situação" in df_titulos.columns:
            from openpyxl.formatting.rule import FormulaRule
            letra = get_column_letter(list(df_titulos.columns).index("Situação") + 1)
            faixa = f"{letra}2:{letra}{ultima_linha}"
            for texto, fundo, fonte in _REGRAS_STATUS_CAP:
                ws2.conditional_formatting.add(
                    faixa,
                    FormulaRule(
                        formula=[f'EXACT({letra}2,"{texto}")'],
                        fill=PatternFill(start_color=fundo, end_color=fundo, fill_type="solid"),
                        font=Font(color=fonte),
                    ),
                )
    else:
        ws2["A1"] = "Nenhum título em aberto."

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


# ── Aba PTAX: cotações de compra, venda e variação das moedas, mês anterior e vigente ──
_DIAS_SEMANA_PTAX = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
_MOEDAS_PTAX = ("EUR", "GBP", "USD")


def adicionar_aba_ptax(xlsx_bytes: bytes, linhas: list[dict], desde, nome_aba: str = "PTAX") -> bytes:
    """Acrescenta à planilha uma aba PTAX com uma linha por dia útil a partir de `desde`.
    `linhas` vem em ordem crescente de data e pode começar antes de `desde`: esse dia anterior
    só serve para calcular a variação (venda do dia em relação ao dia útil anterior)."""
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment

    wb = load_workbook(BytesIO(xlsx_bytes))
    ws = wb.create_sheet(nome_aba)

    fundo = PatternFill("solid", fgColor="1F3864")
    fonte_cab = Font(color="FFFFFF", bold=True)
    centro = Alignment(horizontal="center")
    fino = Side(style="thin", color="BFBFBF")
    borda = Border(left=fino, right=fino, top=fino, bottom=fino)

    # Colunas: A Dia | B Data | cada moeda ocupa 3 colunas (Compra, Venda, Variação) + 1 espaço
    ws.cell(row=1, column=1, value="Dia")
    ws.cell(row=1, column=2, value="Data")
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    ws.merge_cells(start_row=1, start_column=2, end_row=2, end_column=2)
    for i, m in enumerate(_MOEDAS_PTAX):
        c0 = 3 + i * 4
        ws.cell(row=1, column=c0, value=f"{m}/BRL")
        ws.merge_cells(start_row=1, start_column=c0, end_row=1, end_column=c0 + 2)
        for j, titulo in enumerate(("Compra", "Venda", "Variação")):
            ws.cell(row=2, column=c0 + j, value=titulo)
    espacos = {3 + i * 4 + 3 for i in range(len(_MOEDAS_PTAX))}
    colunas_dados = [c for c in range(1, 3 + len(_MOEDAS_PTAX) * 4) if c not in espacos]
    for col in colunas_dados:
        for row in (1, 2):
            cel = ws.cell(row=row, column=col)
            cel.fill = fundo
            cel.font = fonte_cab
            cel.alignment = centro
            cel.border = borda

    # do dia mais recente para o mais antigo, como no mockup aprovado
    linha_xl = 3
    for idx in range(len(linhas) - 1, 0, -1):
        atual = linhas[idx]
        if atual["data"] < desde:
            continue
        anterior = linhas[idx - 1]
        ws.cell(row=linha_xl, column=1, value=_DIAS_SEMANA_PTAX[(atual["data"].weekday() + 1) % 7])
        dc = ws.cell(row=linha_xl, column=2, value=atual["data"])
        dc.number_format = "dd/mm/yyyy"
        for i, m in enumerate(_MOEDAS_PTAX):
            c0 = 3 + i * 4
            compra, venda = atual[m]["compra"], atual[m]["venda"]
            ws.cell(row=linha_xl, column=c0, value=compra).number_format = "#,##0.0000"
            ws.cell(row=linha_xl, column=c0 + 1, value=venda).number_format = "#,##0.0000"
            var = venda / anterior[m]["venda"] - 1
            vc = ws.cell(row=linha_xl, column=c0 + 2, value=var)
            vc.number_format = "+0.00%;-0.00%;0.00%"
            vc.font = Font(color="2E7D32" if var >= 0 else "C62828")
        for col in colunas_dados:
            ws.cell(row=linha_xl, column=col).border = borda
        linha_xl += 1

    ws.column_dimensions["A"].width = 7
    ws.column_dimensions["B"].width = 12
    for i in range(len(_MOEDAS_PTAX)):
        c0 = 3 + i * 4
        for j in range(3):
            ws.column_dimensions[get_column_letter(c0 + j)].width = 12
        ws.column_dimensions[get_column_letter(c0 + 3)].width = 2
    ws.freeze_panes = "C3"

    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()
