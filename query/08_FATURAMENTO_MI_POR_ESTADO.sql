-- =============================================================================
-- FATURAMENTO MI (por estado)  (EXEMPLO com nomes genéricos)
-- Base da tela "Faturamento MI": mapa do Brasil por UF, com a métrica escolhida
-- (faturado, em aberto, inadimplência ou variação), o ano escolhido e o card
-- "Total Faturado" por ano e por mês.
-- Schema, tabelas, colunas e códigos fixos são ilustrativos.
--
-- A tela usa três fontes, todas já vistas nas outras consultas:
--   * esta consulta (abaixo)        -> faturado por cliente, UF e mês (desde 2019)
--   * 01_CONTAS_A_RECEBER.sql       -> em aberto, vencido, inadimplência e prazo médio
--   * 03_SITUACAO_CLIENTE.sql       -> nomes dos clientes e faturado anual (apoio)
-- =============================================================================

-- FATURADO MENSAL POR CLIENTE E ESTADO — desde 01/01/2019
-- (o ano atual, os anos fechados do seletor e os últimos 12 meses saem desta mesma base)
SELECT
    NF.COD_CLIENTE,
    TRIM(NF.UF_DESTINO)                   AS UF,      -- estado de DESTINO gravado na nota
    NVL(TRIM(CL.PAIS), 'BRA')             AS PAIS,    -- cadastro do cliente (separa mercado interno de externo)
    EXTRACT(YEAR  FROM NF.DT_EMISSAO)     AS ANO,
    EXTRACT(MONTH FROM NF.DT_EMISSAO)     AS MES,
    SUM(NVL(NF.VALOR_TOTAL, 0))           AS VALOR_TOTAL_FATURADO
FROM DOMINIO.NOTA_FISCAL NF
LEFT JOIN DOMINIO.CLIENTE CL ON CL.COD_CLIENTE = NF.COD_CLIENTE
WHERE NF.COD_EMPRESA     = :empresa
  AND NF.DT_CANCELAMENTO IS NULL                       -- sem notas canceladas
  AND NF.COD_OPERACAO    IN (:operacoes_venda)         -- só operações de venda
  AND NF.DT_EMISSAO     >= DATE '2019-01-01'
GROUP BY NF.COD_CLIENTE,
         TRIM(NF.UF_DESTINO),
         NVL(TRIM(CL.PAIS), 'BRA'),
         EXTRACT(YEAR  FROM NF.DT_EMISSAO),
         EXTRACT(MONTH FROM NF.DT_EMISSAO)
ORDER BY 1, 4, 5;

-- Como a tela monta o mapa (no Python, sobre o resultado acima):
--   Estado do cliente  = UF da nota (a do cadastro entra só como reserva quando a nota não traz UF)
--   Mercado interno    = clientes do Brasil; clientes do exterior não entram no mapa
--   Período            = ano atual (só meses FECHADOS, comparado ao mesmo período do ano anterior)
--                        ou um ano fechado (janeiro a dezembro, comparado ao ano anterior)
--   Faturado do estado = soma do faturado dos clientes daquele estado no período
--   % no mapa          = faturado do estado / faturado do Brasil
--   Variação           = faturado do período / faturado do período anterior - 1
--   Valores em "mi"    = cortados (não arredondados) na 2ª casa: 2.587.431,20 aparece como 2,58 mi
--
-- Conferência sugerida: a soma do faturado de um cliente num ano fechado precisa ser igual
-- ao valor do gráfico anual da tela Faturamento Cliente/Grupo (03_SITUACAO_CLIENTE.sql).
