-- =============================================================================
-- CONTAS A PAGAR — títulos por período e status  (EXEMPLO com nomes genéricos)
-- Parâmetros: :dt_ini / :dt_fim (período de vencimento).
-- =============================================================================
SELECT
    EM.NOME_EMPRESA                 AS ORG,
    FI.NOME_FILIAL                  AS FILIAL,
    AP.NUM_AP                       AS AP,
    AP.STATUS_APROVACAO             AS APROVACAO,
    AP.NUM_DOCUMENTO                AS DOCTO,
    AP.PARCELA                      AS PARC,
    TD.SIGLA                        AS TIPO_DOCTO,
    FV.TIPO_FAVORECIDO,
    CL.NOME_CLASSIFICACAO           AS TIPO_CLASSIFICACAO,
    FV.NOME_FAVORECIDO              AS FAVORECIDO,
    AP.VALOR,
    AP.SALDO,
    CASE WHEN AP.SALDO = 0 THEN 'PAGO'
         WHEN AP.DT_VENCIMENTO < TRUNC(SYSDATE) THEN 'VENCIDO'
         ELSE 'A VENCER' END        AS STATUS,
    TRUNC(AP.DT_VENCIMENTO) - TRUNC(SYSDATE) AS DIAS,                      -- negativo = vencido
    AP.DT_EMISSAO                   AS EMISSAO,
    AP.DT_ENTRADA                   AS ENTRADA,
    AP.DT_VENCIMENTO                AS VENCTO,
    AP.DT_PRORROGACAO               AS PRORROGADO,
    FP.NOME_FORMA_PAGTO             AS FORMA_PAGTO,
    AP.CHAVE_PIX                    AS PIX,
    AP.LINHA_DIGITAVEL,
    AP.COMPLEMENTO,
    AC.NOME_ACAO                    AS ACAO,
    AP.RATEIO_CLASSES,
    AP.RATEIO_CENTRO_CUSTO,
    AP.RATEIO_PROJETO,
    US.NOME_USUARIO                 AS SOLICITANTE,
    (SELECT COUNT(*) FROM DOMINIO.ANEXO_AP AN WHERE AN.ID_AP = AP.ID_AP) AS QTD_ANEXOS
FROM DOMINIO.CONTA_PAGAR        AP
JOIN DOMINIO.EMPRESA            EM ON EM.COD_EMPRESA    = AP.COD_EMPRESA
JOIN DOMINIO.FILIAL             FI ON FI.COD_FILIAL     = AP.COD_FILIAL
JOIN DOMINIO.FAVORECIDO         FV ON FV.COD_FAVORECIDO = AP.COD_FAVORECIDO
JOIN DOMINIO.TIPO_DOCUMENTO     TD ON TD.COD_TIPO_DOC   = AP.COD_TIPO_DOC
LEFT JOIN DOMINIO.CLASSIFICACAO CL ON CL.COD_CLASSIF    = AP.COD_CLASSIF
LEFT JOIN DOMINIO.FORMA_PAGTO   FP ON FP.COD_FORMA      = AP.COD_FORMA_PAGTO
LEFT JOIN DOMINIO.ACAO          AC ON AC.COD_ACAO       = AP.COD_ACAO
LEFT JOIN DOMINIO.USUARIO       US ON US.COD_USUARIO    = AP.COD_SOLICITANTE
WHERE AP.DT_VENCIMENTO BETWEEN :dt_ini AND :dt_fim
ORDER BY AP.DT_VENCIMENTO
