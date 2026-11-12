from csv import writer
import smtplib
import json
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from io import BytesIO
from pathlib import Path
from utils.formatters import normalizar_nome
from utils.exporters import exportar_excel


# Descrições amigáveis para cada categoria de erro
_DESCRICOES_ERRO = {
    "ERRO CLASSE ADIANTAMENTO": (
        "A classe  informada não é permitida para lançamentos de adiantamento."
        "Utilize uma das classes autorizadas: 364, 1721"
    ),
    "ERRO ACAO SEGMENTO": (
        "Filiais Rurais aceitam apenas Ações Rurais."
        "Filiais Comerciais aceitam apenas Ações Comerciais."
    ),
    "ERRO TIPO FAVORECIDO CLIENTE": (
       "Não é possível lançar Contas a Pagar para favorecidos do tipo Cliente"
    
    ),
}


def _obter_obs(categoria: str) -> str:
    if not categoria:
        return ""
    for chave, descricao in _DESCRICOES_ERRO.items():
        if chave in str(categoria).upper():
            return descricao
    return str(categoria)


def obter_obs_inconsistencia(categoria: str) -> str:
    """Descrição amigável da categoria de erro — usada na tela e no PNG."""
    return _obter_obs(categoria)


def carregar_smtp() -> dict | None:
    config_path = Path(__file__).parent.parent / ".env"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _montar_corpo_html(solicitante: str, df_erros: pd.DataFrame) -> str:
    # Colunas exibidas na tabela (mesma ordem do dicionário headers abaixo)
    colunas_exibir = ["CÓD_FILIAL", "NOME_FILIAL", "AP", "DOCUMENTO", "DATA", "NOME_AGENTE", "SALDO", "CATEGORIA_ERRO"]
    colunas_existentes = [c for c in colunas_exibir if c in df_erros.columns]

    headers = {
        "CÓD_FILIAL":    "Cod. Filial",
        "NOME_FILIAL":   "Filial",
        "AP":            "AP",
        "DOCUMENTO":     "Documento",
        "DATA":          "Data",
        "NOME_AGENTE":   "Favorecido",
        "SALDO":         "Valor",
        "CATEGORIA_ERRO":"Categoria do Erro",
    }

    cabecalho_html = "".join(
        f'<th style="background:#c0392b; color:white; padding:10px 14px; '
        f'text-align:left; font-weight:600; font-size:12px;">{headers.get(c, c)}</th>'
        for c in colunas_existentes
    ) + '<th style="background:#c0392b; color:white; padding:10px 14px; ' \
        'text-align:left; font-weight:600; font-size:12px;">Observação</th>'

    linhas_html = ""
    for _, row in df_erros.iterrows():
        cells = ""
        for c in colunas_existentes:
            val = row.get(c, "")
            if c == "SALDO":
                try:
                    val = f"R$ {float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except Exception:
                    pass
            elif c == "DATA":
                try:
                    val = pd.to_datetime(val).strftime("%d/%m/%Y")
                except Exception:
                    pass
            cells += (
                f'<td style="padding:9px 14px; border-bottom:1px solid #f0d0d0; '
                f'color:#333; font-size:12px;">{val}</td>'
            )
        obs = _obter_obs(row.get("CATEGORIA_ERRO", ""))
        cells += (
            f'<td style="padding:9px 14px; border-bottom:1px solid #f0d0d0; '
            f'color:#555; font-size:11px; font-style:italic;">{obs}</td>'
        )
        linhas_html += f"<tr>{cells}</tr>"

    qtd_fmt = f"{len(df_erros):02d}"

    return f"""
    <html>
    <body style="font-family:Arial, sans-serif; color:#333; max-width:800px; margin:0 auto; padding:20px;">

      <div style="display:inline-block; border:1px solid #e57373; border-radius:20px;
                  padding:4px 14px; color:#c0392b; font-size:13px; margin-bottom:20px;">
        Atenção — Inconsistências identificadas
      </div>

      <p style="font-size:15px; margin:0 0 8px;">Olá, <b>{solicitante}</b>.</p>
      <p style="font-size:14px; color:#555; margin:0 0 22px;">
        Identificamos <b>{qtd_fmt} inconsistência(s)</b> nos lançamentos abaixo de sua responsabilidade.<br>
        Por favor, verifique e regularize as pendências o quanto antes.
      </p>

      <table style="width:100%; border-collapse:collapse; margin-bottom:24px;">
        <thead><tr>{cabecalho_html}</tr></thead>
        <tbody>{linhas_html}</tbody>
      </table>

      <div style="border-left:4px solid #2980b9; background:#eaf4fb;
                  padding:10px 16px; font-size:13px; color:#2471a3; margin-bottom:24px; border-radius:0 4px 4px 0;">
        O arquivo Excel com o detalhamento completo está em anexo neste e-mail.
      </div>

      <p style="font-size:13px; color:#555; margin:0;">Em caso de dúvidas, entre em contato com o setor financeiro.</p>
      <p style="font-size:13px; color:#555; margin:4px 0 0;">Atenciosamente,<br>
        <b>Equipe Financeira — Demo</b>
      </p>

      <hr style="border:none; border-top:1px solid #eee; margin:28px 0 12px;">
      <p style="font-size:11px; color:#aaa; text-align:center; margin:0;">
        Mensagem automática gerada pelo Painel Financeiro Demo. Não responda este e-mail.
      </p>

    </body>
    </html>
    """


def _montar_anexo_excel(df_erros: pd.DataFrame) -> BytesIO:
    # Nome_Filial e Data incluídas, na mesma ordem do e-mail
    colunas_excel = ["CÓD_FILIAL", "NOME_FILIAL", "AP", "DOCUMENTO", "DATA", "NOME_AGENTE", "SALDO", "CATEGORIA_ERRO"]
    colunas_existentes = [c for c in colunas_excel if c in df_erros.columns]
    df_export = df_erros[colunas_existentes]

    # Mesmo padrão visual dos demais relatórios (cabeçalho, bordas, filtro no topo).
    excel_bytes = BytesIO(exportar_excel(df_export, "Inconsistencias"))
    excel_bytes.seek(0)
    return excel_bytes


def enviar_email_inconsistencias(
    solicitante: str,
    df_erros_solicitante: pd.DataFrame,
    email_manual: str | None = None,
    emails_cc: list[str] | None = None
) -> str:
    """Envia e-mail com as inconsistências do solicitante e retorna o destinatário."""
    cfg = carregar_smtp()
    if not cfg:
        raise Exception("Arquivo smtp_config.json não encontrado.")

    smtp_user    = cfg["smtp_user"]
    smtp_pass    = cfg["smtp_pass"]
    dominio      = cfg.get("dominio_email", "demo.com.br")
    destinatario = email_manual if email_manual else f"{normalizar_nome(solicitante)}@{dominio}"
    cc_validos   = [e for e in (emails_cc or []) if e and "@" in e]

    corpo_html  = _montar_corpo_html(solicitante, df_erros_solicitante)
    excel_bytes = _montar_anexo_excel(df_erros_solicitante)

    msg = MIMEMultipart("mixed")
    msg["From"]    = smtp_user
    msg["To"]      = destinatario
    msg["Subject"] = f"Inconsistências de Lançamento — {solicitante}"
    if cc_validos:
        msg["Cc"] = ", ".join(cc_validos)

    msg.attach(MIMEText(corpo_html, "html"))

    anexo = MIMEBase("application", "octet-stream")
    anexo.set_payload(excel_bytes.read())
    encoders.encode_base64(anexo)
    anexo.add_header(
        "Content-Disposition",
        f'attachment; filename="Inconsistencias_{normalizar_nome(solicitante)}.xlsx"'
    )
    msg.attach(anexo)

    # CORREÇÃO: não passar lista explícita — os cabeçalhos To/Cc já controlam a entrega
    with smtplib.SMTP("smtp.office365.com", 587) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)  # send_message usa os cabeçalhos To/Cc automaticamente

    return destinatario
