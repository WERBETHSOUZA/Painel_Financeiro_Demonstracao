import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
from pathlib import Path
import hashlib

PAINEL_PATH = Path(__file__).parent.parent / "Painel.xlsx"

def gerar_hash_registro(row):
    """Gera hash único para evitar duplicatas"""
    chave = f"{row['AP']}{row['DOCTO']}{row['PARC']}"
    return hashlib.md5(chave.encode()).hexdigest()

def carregar_log_erros():
    """Carrega dados da aba LOG_ERROS_FIN_CP do Painel.xlsx"""
    
    if not PAINEL_PATH.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_excel(PAINEL_PATH, sheet_name="LOG_ERROS_FIN_CP")
        return df
    except:
        return pd.DataFrame()

def exportar_para_painel(df_erros, sheet_name="LOG_ERROS_FIN_CP"):
    """Exporta erros para Painel.xlsx evitando duplicatas"""
    
    # Adicionar coluna de hash para controle de duplicatas
    df_erros = df_erros.copy()
    df_erros['HASH_REGISTRO'] = df_erros.apply(gerar_hash_registro, axis=1)
    
    # Carregar ou criar workbook
    if PAINEL_PATH.exists():
        wb = load_workbook(PAINEL_PATH)
        
        # Criar ou limpar aba
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            ws.delete_rows(2, ws.max_row)  # Manter apenas cabeçalho
        else:
            ws = wb.create_sheet(sheet_name)
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
    
    # Verificar se já tem cabeçalho
    if ws.max_row == 1 or ws['A1'].value is None:
        ws.append(df_erros.columns.tolist())
        
        # Estilizar cabeçalho
        header_fill = PatternFill(start_color="D32F2F", end_color="D32F2F", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Obter hashes já existentes
    hashes_existentes = set()
    for row in ws.iter_rows(min_row=2, max_col=ws.max_column, values_only=True):
        if row and len(row) > 0:
            hashes_existentes.add(str(row[-1]))  # Última coluna é HASH_REGISTRO
    
    # Filtrar apenas novos registros
    df_novos = df_erros[~df_erros['HASH_REGISTRO'].isin(hashes_existentes)]
    
    # Adicionar novos registros
    for _, row in df_novos.iterrows():
        ws.append(row.tolist())
    
    # Ajustar largura das colunas
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Salvar e retornar bytes
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return output.getvalue()