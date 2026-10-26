-- =============================================================================
-- FATURAMENTO CLIENTE/GRUPO  (EXEMPLO com nomes genéricos)
-- Esta tela reaproveita as consultas das outras telas:
--   * 01_CONTAS_A_RECEBER.sql  -> cards (a vencer, vencido, inadimplência), aging,
--                                 resumo de títulos e distribuição por estado
--   * 02_GRUPO_DE_CREDITO.sql  -> limite, consumido (NF + PV), disponível e situação
--   * 03_SITUACAO_CLIENTE.sql  -> faturado por ano (gráfico anual e variação anual)
--                                 e adiantamentos
-- Só uma consulta é própria dela: o faturado MENSAL, abaixo.
-- =============================================================================

-- FATURADO MENSAL POR CLIENTE — últimos 24 meses
-- (12 meses + o mesmo período do ano anterior, para a variação mensal)
SELECT
    NF.COD_CLIENTE,
    EXTRACT(YEAR  FROM NF.DT_EMISSAO)  AS ANO,
    EXTRACT(MONTH FROM NF.DT_EMISSAO)  AS MES,
    SUM(NVL(NF.VALOR_TOTAL, 0))        AS VALOR_TOTAL_FATURADO
FROM DOMINIO.NOTA_FISCAL NF
WHERE NF.COD_EMPRESA     = :empresa
  AND NF.DT_CANCELAMENTO IS NULL
  AND NF.COD_OPERACAO    IN (:operacoes_venda)
  AND NF.DT_EMISSAO     >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -24)
GROUP BY NF.COD_CLIENTE,
         EXTRACT(YEAR  FROM NF.DT_EMISSAO),
         EXTRACT(MONTH FROM NF.DT_EMISSAO)
ORDER BY 1, 2, 3;

-- Como a tela calcula os indicadores (no Python, sobre o resultado das consultas acima):
--   % Limite utilizado = (consumido NF + consumido PV) / limite do grupo
--   % Inadimplência    = total vencido / total em aberto
--   Variação mensal    = faturado do mês / faturado do mesmo mês do ano anterior - 1
--   Variação anual     = faturado do ano / faturado do ano anterior - 1
--                        (o ano em andamento é parcial e fica sem percentual)
