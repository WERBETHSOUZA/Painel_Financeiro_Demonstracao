-- =============================================================================
-- SITUAÇÃO CLIENTE  (EXEMPLO com nomes genéricos)
-- A tela combina: títulos em aberto (01_CONTAS_A_RECEBER.sql), faturado por ano (A) e
-- adiantamentos recebidos em aberto (B). Schema, tabelas e colunas são ilustrativos.
-- =============================================================================

-- (A) FATURADO POR CLIENTE E ANO — todo o histórico
--     Alimenta o gráfico "Total Faturado" por ano e o painel "Variação anual".
SELECT
    NF.COD_CLIENTE,
    CL.NOME_CLIENTE                        AS CLIENTE,
    EXTRACT(YEAR FROM NF.DT_EMISSAO)       AS ANO,
    CASE WHEN NF.COD_OPERACAO IN (:operacoes_internas) THEN 'MI' ELSE 'ME' END AS MERCADO,
    SUM(NVL(NF.VALOR_TOTAL, 0))            AS VALOR_TOTAL_FATURADO,
    COUNT(DISTINCT NF.ID_NOTA)             AS QTD_NOTAS
FROM DOMINIO.NOTA_FISCAL NF
JOIN DOMINIO.CLIENTE     CL ON CL.COD_CLIENTE = NF.COD_CLIENTE
WHERE NF.COD_EMPRESA     = :empresa
  AND NF.DT_CANCELAMENTO IS NULL
  AND NF.COD_OPERACAO    IN (:operacoes_venda)
GROUP BY NF.COD_CLIENTE, CL.NOME_CLIENTE,
         EXTRACT(YEAR FROM NF.DT_EMISSAO),
         CASE WHEN NF.COD_OPERACAO IN (:operacoes_internas) THEN 'MI' ELSE 'ME' END
ORDER BY CL.NOME_CLIENTE, ANO;

-- (B) ADIANTAMENTOS — saldo em aberto por cliente
--     Só roda quando o usuário clica em "Carregar adiantamento", porque o cálculo do
--     saldo é mais pesado.
SELECT
    AD.COD_CLIENTE,
    AD.NATUREZA,                           -- RECEBIDO | EFETUADO
    SUM(AD.SALDO_ADIANTAMENTO)             AS SALDO
FROM DOMINIO.VW_ADIANTAMENTO AD
WHERE AD.SALDO_ADIANTAMENTO > 0
GROUP BY AD.COD_CLIENTE, AD.NATUREZA;
