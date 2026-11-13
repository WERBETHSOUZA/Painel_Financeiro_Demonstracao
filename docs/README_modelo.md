# 💰 Painel Financeiro — demonstração com dados fictícios

Painel financeiro (financeiro, comercial e relatórios) feito em **Python + Streamlit + Pandas**: contas a pagar e a receber,
recebimentos por banco, limite de crédito por grupo econômico, situação do cliente, faturamento, boletos DDA, adiantamentos e
inconsistências de lançamento. Este repositório é a **demonstração**: roda **o mesmo painel do ambiente de produção** (o mesmo
`app.py`, as mesmas telas, o mesmo menu e os mesmos botões), só que com **dados 100% inventados** (nomes de empresas, valores,
bancos e datas), sem banco de dados e sem nenhuma informação real.

> Os dados são gerados por `dados_ficticios.py`, `dados_ficticios_extra.py` e `dados_ficticios_novos.py` com semente fixa, então a
> demonstração é sempre igual. Nenhuma pessoa, empresa ou valor real aparece aqui.
>
> **Este README é gerado a partir do README do painel de produção** (`python tools/sincronizar_com_projeto_real.py`): as seções de
> estrutura, painéis, exportação, desempenho e arquitetura são as mesmas, com os nomes da empresa trocados por nomes genéricos.
> O que é diferente na demonstração está marcado como **[na demo]** ou **[fora da demonstração]**.

## Veja em movimento

![Todos os painéis em movimento (30 s)](docs/img/gif_todos_os_paineis.gif)

{{ESTRUTURA}}

### Arquivos próprios da demonstração

Além da estrutura acima (idêntica à de produção), a demonstração tem estes arquivos:

```
app_demo.py                  # abre a demonstração: semeia os grupos fictícios da tela Acessos e executa o app.py
dados_ficticios.py           # dados inventados: clientes, títulos a receber, grupos de crédito, faturado
dados_ficticios_extra.py     # dados inventados: contas a pagar, boletos DDA e inconsistências
dados_ficticios_novos.py     # dados inventados: recebimentos (baixas por banco), vendas por vendedor, adiantamentos,
                             # descontos, fretes, aprovação com Produtor/Fornecedor e histórico de pagamentos
services/data_service.py     # [na demo] mesmas funções e colunas do painel real, devolvendo os dados inventados (sem Oracle)
services/auth_service.py     # [na demo] login de demonstração (admin / admin) e diretório de usuários fictício
assets/demo_logo.png         # logo fictício
tools/sincronizar_com_projeto_real.py  # atualiza a demonstração (código e este README) a partir do painel de produção
docs/README_modelo.md        # modelo deste README (as seções de produção são preenchidas pelo script)
docs/img/                    # imagens e GIF
query/                       # exemplos GENÉRICOS e ilustrativos das consultas (schema DOMINIO); não são as consultas reais
```

O **extrato bancário** e os **saldos bancários** ficam fora da demonstração: dependem de acesso direto ao banco.

## 🚀 Como rodar

```bash
pip install -r requirements.txt
streamlit run app_demo.py --server.port 8590
```

No Windows, dê dois cliques em **`ABRIR DEMO.bat`**. O navegador abre em `http://localhost:8590`.

**Login de demonstração:** usuário `admin`, senha `admin` (sem autenticação real). A tela de **Acessos** (botão Admin) mostra
como o painel controla quem vê o quê, com grupos e usuários fictícios.

## 🔄 Como atualizar a demonstração

A demo roda o mesmo código do painel de produção; só a camada de dados (`services/data_service.py`) e o login
(`services/auth_service.py`) são da demonstração. Para acompanhar mudanças do painel real:

```bash
python tools/sincronizar_com_projeto_real.py
```

O script copia as telas, componentes e utilitários, troca os nomes da empresa por nomes genéricos, tira do menu o que não existe
na demo, **regera este README** a partir do README de produção e, no fim, confere se sobrou algum nome real nos arquivos.
Se o painel real ganhar uma consulta nova, crie a função de mesmo nome em `services/data_service.py` devolvendo um DataFrame com as
mesmas colunas (o gerador fica em `dados_ficticios_novos.py`).

{{PAINEIS}}

{{EXPORTACAO}}

## 🎞️ Animações

Os gráficos principais entram com uma animação curta (cerca de 1 segundo), feita **só com CSS**
(sem JavaScript, sem varredura da página e sem custo de processamento no servidor):

| Onde | Efeito |
|------|--------|
| Aging de vencimentos (Contas a Receber, Situação Cliente, Faturamento) | barras crescem da esquerda para a direita |
| Rosca "Situação" (Contas a Receber, Situação Cliente, Grupo de Crédito, Faturamento) | a rosca se desenha até o valor |
| Distribuição por banco e por estado, limite de crédito | barras empilhadas e barras de ranking crescem |
| Total Faturado (por ano e últimos 12 meses) | linha e área reveladas da esquerda para a direita |
| Contas a Receber MI: lista do card Recebimentos por Data e Top Clientes a Receber | barras crescem da esquerda para a direita **em cascata** (cada linha começa 45 ms depois da anterior) |
| Contas a Receber MI: bloco "Hoje" | a barra de progresso (esperado / recebido) enche até o percentual |
| Contas a Receber MI: gráfico do Resumo | as colunas **sobem de baixo para cima**, mês a mês; depois os valores e as marcas do ano anterior aparecem com um fade |
| Contas a Receber MI: botão A receber \| Recebido | o card vira (giro rápido) ao trocar de lado |

A animação roda quando o gráfico aparece (abrir a tela, trocar de cliente ou grupo, abrir uma aba) e não se repete
ao clicar em **Atualizar**. Os cards e os números não são animados, e quem usa "reduzir movimento" no sistema
operacional não vê as animações. Os estilos estão em [`assets/styles.css`](assets/styles.css) (classes `an-wipe`,
`an-rosca`, `an-area`, `an-col` e `an-fade`).

{{PERFORMANCE}}

{{ARQUITETURA}}

## Observações

- A cotação PTAX do mercado externo é consultada na API pública do Banco Central (`olinda.bcb.gov.br`);
  sem internet, esse bloco fica vazio e o resto funciona normalmente.
- Tecnologias: Python, Streamlit, Pandas, Plotly e Pillow (imagens para e-mail).
