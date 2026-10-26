-- =============================================================================
-- GRUPO DE CRÉDITO  (EXEMPLO com nomes genéricos)
-- Duas consultas: (A) visão geral por grupo e (B) consumo por cliente do grupo.
-- A tela Faturamento usa (A) para limite/consumido/disponível e (B) para o UF e o
-- consumo de cada cliente. Schema, tabelas e colunas são ilustrativos.
-- =============================================================================

-- (A) GERAL — limite, consumo e situação por grupo
SELECT
    G.COD_GRUPO                         AS GRUPO_CODIGO,
    G.NOME_GRUPO,
    S.VALOR_LIMITE,
    S.VALOR_RECEBER_ABERTO,             -- consumido em notas fiscais (títulos a receber)
    S.VALOR_PEDIDO_ABERTO,              -- consumido em pedidos de venda ainda não faturados
    S.VALOR_LIMITE - S.VALOR_RECEBER_ABERTO - S.VALOR_PEDIDO_ABERTO AS VALOR_DISPONIVEL,
    S.SITUACAO_CLIENTE                  -- LIBERADO | BLOQUEADO
FROM DOMINIO.GRUPO_CREDITO  G
JOIN DOMINIO.VW_SALDO_GRUPO S ON S.COD_GRUPO = G.COD_GRUPO
ORDER BY G.COD_GRUPO;

-- (B) SALDO POR AGENTE — clientes de cada grupo e quanto cada um consome do limite
SELECT
    CL.COD_CLIENTE                      AS COD_AGENTE,
    CL.NOME_CLIENTE                     AS NOME_AGENTE,
    CL.COD_GRUPO,
    CL.UF,
    CL.PAIS,
    CL.TIPO_PESSOA,
    S.VALOR_LIMITE                      AS LIMITE_DO_GRUPO,
    NVL(C.CONSUMIDO_EM_NF, 0)           AS CONSUMIDO_EM_NF,
    NVL(C.CONSUMIDO_EM_PV, 0)           AS CONSUMIDO_EM_PV
FROM DOMINIO.CLIENTE CL
JOIN DOMINIO.VW_SALDO_GRUPO S ON S.COD_GRUPO = CL.COD_GRUPO
LEFT JOIN (
    SELECT COD_CLIENTE,
           SUM(CASE WHEN ORIGEM = 'NF' THEN VALOR_ABERTO END) AS CONSUMIDO_EM_NF,
           SUM(CASE WHEN ORIGEM = 'PV' THEN VALOR_ABERTO END) AS CONSUMIDO_EM_PV
    FROM DOMINIO.VW_CONSUMO_LIMITE
    GROUP BY COD_CLIENTE
) C ON C.COD_CLIENTE = CL.COD_CLIENTE
ORDER BY CL.COD_GRUPO, CL.NOME_CLIENTE;
