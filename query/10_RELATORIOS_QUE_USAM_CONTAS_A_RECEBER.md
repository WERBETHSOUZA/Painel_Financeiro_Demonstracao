# Relatórios que reutilizam queries existentes

Estes relatórios não têm query própria: leem o resultado de uma consulta já listada e filtram em memória.

| Relatório | Query base | Filtro aplicado |
|-----------|-----------|-----------------|
| Contas a Receber - Exportação | `01_CONTAS_A_RECEBER.sql` | todos os títulos em aberto |
| Variação Cambial ME | `01_CONTAS_A_RECEBER.sql` | `MERCADO = 'ME'`, com a PTAX escolhida (cotação pública do Banco Central) |
| Desconto Financeiros Pendentes | `01_CONTAS_A_RECEBER.sql` | `MERCADO = 'MI'` e `TIPO_REGRA = 'FINANCEIRO'`; status pelo campo `DESC_APLIC_FIN` |
| Boleto Não Gerado | `01_CONTAS_A_RECEBER.sql` | `MERCADO = 'MI'`, `SITUACAO_BOLETO <> 'BOLETO GERADO'`, `TIPO_PESSOA <> 'F'` |
| Grupo de Crédito (relatório) | `02_GRUPO_DE_CREDITO.sql` | sem filtro adicional |
