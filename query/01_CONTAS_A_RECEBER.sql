-- =============================================================================
-- CONTAS A RECEBER — títulos em aberto  (EXEMPLO com nomes genéricos)
-- Base das telas Contas a Receber, Situação Cliente e Faturamento Cliente/Grupo.
-- Uma linha por parcela com saldo em aberto. Schema, tabelas, colunas e códigos fixos
-- são ilustrativos.
-- =============================================================================
WITH TITULO AS (
    SELECT
        CR.COD_CLIENTE,
        CL.NOME_CLIENTE                         AS CLIENTE,
        NF.NUM_NOTA                             AS NF,
        CR.PARCELA,
        NF.DT_EMISSAO                           AS ENTRADA,
        CR.DT_VENCIMENTO                        AS VENCIMENTO,
        CR.DT_PRORROGACAO                       AS PRORROGADO,
        CR.SALDO_ABERTO                         AS SALDO_EM_ABERTO,       -- em reais
        CR.VALOR_PARCELA                        AS VALOR_FATURADO,
        CR.VALOR_LIQUIDO                        AS LIQUIDO_FIN,           -- líquido da NF (base do desconto)
        CR.DESC_APLICADO_NF                     AS DESC_APLIC_NF,         -- nulo = desconto ainda não aplicado
        CR.DESC_APLICADO_FIN                    AS DESC_APLIC_FIN,        -- nulo = desconto ainda não aplicado
        CL.TIPO_PESSOA,                                                    -- F não recebe boleto
        CR.MOEDA,
        CR.COTACAO,
        CR.SALDO_MOEDA,                                                    -- só mercado externo
        CASE WHEN NF.COD_OPERACAO IN (:operacoes_internas) THEN 'MI' ELSE 'ME' END AS MERCADO,
        BC.NOME_BANCO                           AS BANCO_NOME,
        CASE WHEN CR.NOSSO_NUMERO IS NOT NULL THEN 'BOLETO GERADO' ELSE '-' END AS SITUACAO_BOLETO,
        CL.UF,
        CL.PAIS,
        RG.TIPO_REGRA,                                                     -- FATURAMENTO | FINANCEIRO
        RG.PERC_REGRA,
        TRUNC(CR.DT_VENCIMENTO) - TRUNC(SYSDATE) AS DIAS                   -- negativo = vencido
    FROM DOMINIO.CONTA_RECEBER      CR
    JOIN DOMINIO.NOTA_FISCAL        NF ON NF.ID_NOTA     = CR.ID_NOTA
    JOIN DOMINIO.CLIENTE            CL ON CL.COD_CLIENTE = CR.COD_CLIENTE
    LEFT JOIN DOMINIO.BANCO         BC ON BC.COD_BANCO   = CR.COD_BANCO
    LEFT JOIN DOMINIO.REGRA_CLIENTE RG ON RG.COD_CLIENTE = CR.COD_CLIENTE
    WHERE CR.COD_EMPRESA     = :empresa
      AND NF.DT_CANCELAMENTO IS NULL
      AND NVL(CR.SALDO_ABERTO, 0) > 0                                      -- só saldo em aberto
)
SELECT
    T.*,
    CASE WHEN T.DIAS < 0 THEN 'VENCIDO' ELSE 'A VENCER' END AS SITUACAO,
    CASE
        WHEN T.DIAS < -30 THEN 'Vencido 30+ dias'
        WHEN T.DIAS < 0   THEN 'Vencido até 30 dias'
        WHEN T.DIAS <= 30 THEN 'A vencer até 30 dias'
        WHEN T.DIAS <= 60 THEN 'A vencer 31 a 60 dias'
        WHEN T.DIAS <= 90 THEN 'A vencer 61 a 90 dias'
        ELSE                   'A vencer 90+ dias'
    END AS FAIXA_DIAS
FROM TITULO T
ORDER BY T.CLIENTE, T.VENCIMENTO
