-- =============================================================================
-- BOLETOS DDA — boletos recebidos via Débito Direto Autorizado  (EXEMPLO)
-- Cruza o boleto recebido do banco com o título a pagar correspondente.
-- =============================================================================
SELECT
    BO.NOSSO_NUMERO,
    BO.NOME_SACADO                  AS SACADO,
    BO.CNPJ,
    BO.DT_VENCIMENTO,
    BO.VALOR,
    AP.NUM_TITULO,
    AP.NUM_DOCUMENTO                AS DOCUMENTO,
    CASE WHEN AP.ID_AP IS NULL THEN 'Sem título correspondente'
         WHEN AP.VALOR <> BO.VALOR THEN 'Valor divergente'
         ELSE 'Pagamento' END       AS MOTIVO
FROM DOMINIO.BOLETO_DDA         BO
LEFT JOIN DOMINIO.CONTA_PAGAR   AP ON AP.CNPJ_FAVORECIDO = BO.CNPJ
                                  AND AP.DT_VENCIMENTO   = BO.DT_VENCIMENTO
WHERE BO.SITUACAO = 'ABERTO'
ORDER BY BO.DT_VENCIMENTO
