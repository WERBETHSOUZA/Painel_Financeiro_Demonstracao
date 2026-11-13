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

## 📁 Estrutura do Projeto

```
projeto/
├── app.py                              # Entry point — login, roteamento, menu e tema
├── PAINEL FINANCEIRO.bat               # Atalho para iniciar o painel no Windows
├── .env                                # Credenciais Oracle / Active Directory (não versionar)  [não usado na demo]
├── auth_config.yaml                    # Fallback local de login (não versionar — legado)  [não usado na demo]
├── requirements.txt                    # Dependências Python
├── smtp_config.json                    # Credenciais SMTP (não versionar)  [não usado na demo]
│
├── .streamlit/
│   └── config.toml                     # Força tema escuro fixo, independente do SO do usuário
│
├── assets/
│   ├── styles.css                      # Estilos globais da interface
│   └── demo_logo.png                 # Logo (sem fundo) — login e sidebar
│
├── config/
│   ├── settings.py                     # Configuração da página e injeção de CSS
│   ├── pdd.py                          # Regra de PDD (dias de corte do vencido)
│   ├── pagador.py                      # Perfil de pagamento: crédito esperado (feriados), faixas e níveis Ótimo/Bom/Regular/Atenção/Mau
│   ├── frases.py                       # Frase do dia da barra lateral (uma por dia, 40 frases)
│   ├── classes_desconto.py             # Tabela de classes de desconto por regra
│   └── permissoes.json                 # Grupos e acessos (fora do Git — ver "Acessos por grupo")
│
├── components/
│   ├── buttons.py                      # Botões padrão (Exportar para Excel, Salvar PNG, Copiar) usados em todas as telas
│   ├── rodape_lateral.py               # Ícone (?) no topo da barra lateral: janela Ajuda com a build e o contato do suporte
│   └── cards.py                        # card_html() + render_cards_row() — cards padronizados
│                                        # (largura/altura configuráveis, usados em todo o painel)
│
├── services/
│   ├── data_service.py                 # Conexão Oracle, execução das queries, filtros e cache  [na demo: dados fictícios, sem Oracle]
│   ├── email_service.py                # Envio de e-mails via SMTP (Office 365)
│   ├── permissoes.py                   # Acesso por grupo (lê/grava config/permissoes.json)
│   ├── clientes_transferencia.py       # Clientes que pagam por transferência (config/clientes_transferencia.json, fora do Git)
│   ├── excel_service.py                # Gravação de planilhas Excel (apoio às exportações)
│   └── auth_service.py                 # Autenticação via Active Directory (LDAP)  [na demo: login admin / admin]
│
├── utils/
│   ├── formatters.py                   # Formatação de datas e normalização de nomes
│   ├── exporters.py                    # Exportação de DataFrames para Excel
│   ├── pendencias.py                   # Card e gráfico "Notas Pendentes de Validação" (Situação Cliente e Grupo de Crédito)
│   ├── prazos.py                       # Dias a vencer / dias vencido a partir de vencimento e prorrogado
│   ├── ptax.py                         # Cotações PTAX do Banco Central (API pública), base da variação cambial
│   └── imagem_email.py                 # Gera imagem PNG (fundo branco) para e-mail e
│                                        # botão de copiar direto para a área de transferência
│
├── query/
│   ├── QUERY_APS_VENCIDAS.sql          # APs vencidas (painel fora do menu)
│   ├── QUERY_APS_ERRO.sql              # Inconsistências de lançamento
│   ├── RELATORIO_APPROVO.sql           # Relatório de aprovadores
│   ├── QUERY_CONTAS_APAGAR.sql         # Contas a pagar
│   ├── QUERY_BOLETOS_DDA.sql           # Boletos DDA
│   ├── QUERY_ADIANTAMENTOS_GERAL.sql   # Adiantamentos — lançamentos detalhados (com organização)
│   ├── QUERY_ADIANTAMENTOS_TOTAL_AGENTE.sql # Adiantamentos — totais por agente
│   ├── QUERY_CONTAS_RECEBER.sql        # Contas a receber (títulos em aberto, MI/ME, moeda, Classificação por ação)
│   ├── QUERY_TOTAL_FATURADO_CLIENTE.sql # Total faturado por cliente e por ano (soma o total da nota, igual ao financeiro)
│   ├── QUERY_HISTORICO_PAGAMENTOS_MI.sql # Histórico de pagamentos MI (emissão, vencimento, baixa) — perfil de pagamento
│   ├── QUERY_LISTA_CLIENTES.sql        # Clientes para a busca da tela Admin > Clientes por Transferência
│   ├── QUERY_MOVIMENTACAO_FINANCEIRA.sql # Extratos Bancários (lançamentos e saldos por conta)  [fora da demonstração]
│   ├── QUERY_BAIXAS_CR_MI.sql / QUERY_PARCELAS_CR_MI.sql # Contas a Receber - MI (baixas e parcelas)
│   ├── QUERY_FATURADO_MENSAL_*.sql     # Faturado mensal (cliente, MI, vendedor) — Visão Geral Comercial / UF
│   ├── QUERY_RECEBIDO_*.sql / QUERY_RECEBIMENTO_HOJE_MI.sql / QUERY_BAIXA_DIA_MI.sql # Recebimentos do Contas a Receber MI (card Recebido, Resumo, bloco Hoje)
│   ├── QUERY_EMISSAO_NF_MI.sql / QUERY_VENCIMENTO_PARCELAS_CR_MI.sql # Emissão e vencimento das parcelas (PMR e em dia/atraso)
│   ├── QUERY_RECEBIMENTOS.sql / QUERY_ORGANIZACOES_RECEBIMENTOS.sql # Recebimento por Banco (baixas por banco)
│   ├── QUERY_DESCONTOS_OPERACIONAIS_MI.sql / QUERY_DESCONTO_CLASSES.sql / QUERY_REGRA_DESCONTO_CLIENTE.sql # Descontos
│   ├── QUERY_FRETES_MOT_MATRIZ_FILIAL.sql # Fretes Mot (contas a pagar de fretes)
│   ├── QUERY_VARIACAO_CAMBIAL_ME.sql / QUERY_HISTORICO_PAGAMENTOS_ME.sql # Mercado Externo
│   ├── QUERY_VENDAS_DIA_VENDEDOR_MI.sql / QUERY_NOTAS_VENDIDAS_MI.sql # Visão Geral Comercial (vendas por dia e notas vendidas)
│   ├── QUERY_ADIANTAMENTO_SALDO_AGENTE.sql # Adiantamentos — saldo por agente
│   ├── QUERY_PENDENCIAS_BLOQUEANTES.sql # Notas do MI com pendência bloqueante ou validação manual, por cliente (esquema SYNCPROCESS)
│   ├── QUERY_PENDENCIAS_NOTAS.sql       # As mesmas notas, uma linha por pendência (gráfico da Situação Cliente)
│   ├── QUERY_SALDOS_BANCARIOS.sql / QUERY_EXTRATO_SALDO_BANCOS_LANCAMENTOS.sql # Saldos Bancários (base de teste)  [fora da demonstração]
│   ├── GRUPO DE CREDITO - GERAL.sql    # Limite/saldo consolidado por Grupo de Crédito
│   └── GRUPO DE CRÉDITO - SALDO AGENTE.sql # Saldo detalhado por cliente dentro do grupo
│
└── views/
    ├── vencidas.py                     # Painel — APs Vencidas (fora do menu)
    ├── inconsistencias.py              # Painel — Inconsistências de Lançamento
    ├── relatorios.py                   # Painel — Relatório de Aprovadores
    ├── relatorio_contas_apagar.py      # Painel — Contas a Pagar
    ├── relatorio_contas_receber.py     # Relatório — Contas a Receber - Exportação (exportação completa)
    ├── boletos_dda.py                  # Relatório — Boletos DDA
    ├── adiantamentos.py                # Relatório — Adiantamentos (efetuados/recebidos)
    ├── contas_receber_painel.py        # Painel — Contas a Receber (itens Visão Geral / MI / ME)
    ├── contas_receber.py               # Aba Mercado Interno (usada dentro do painel acima)
    ├── contas_receber_externo.py       # Aba Mercado Externo, por moeda (usada dentro do painel acima)
    ├── faturamento_ano.py              # Módulo compartilhado — faturamento por ano (Situação Cliente e Grupo de Crédito)
    ├── faturamento_cliente_grupo.py    # Painel — Faturamento Cliente/Grupo (títulos, adiantamento e faturamento por agente)
    ├── faturamento_estado.py           # Painel — Faturamento por Estado (mapa do Brasil por UF, clientes do estado)
    ├── grupo_credito.py                # Painel — Limite de Crédito
    ├── situacao_cliente.py             # Painel — Situação Cliente (visão consolidada)
    ├── visao_geral_comercial.py        # Painel — Visão Geral Comercial (Mercado Interno)
    ├── resumo_pendencias.py            # Painel — Resumo Pendências (só quantidades; grupo fixo na tela Acessos)
    ├── acessos.py                      # Tela Admin — Acessos por grupo
    ├── relatorio_contas_receber_mi.py  # Relatório — Contas a Receber - MI
    ├── relatorio_movimentacao_financeira.py # Tesouraria — Extratos Bancários  [fora da demonstração]
    ├── resumo_contas_receber_mi.py     # Contas a Receber MI — visão Resumo (recebimentos por mês, PMR, comparação com o ano anterior)
    ├── relatorio_boleto_nao_gerado.py  # Relatório — Boleto Não Gerado
    ├── relatorio_desconto_financeiro_pendente.py # Relatório — Descontos Contratuais Pendentes MI
    ├── relatorio_descontos_operacionais_mi.py # Relatório — Descontos Realizados
    ├── relatorio_fretes_mot_matriz_filial.py # Relatório — Fretes Mot
    ├── relatorio_grupos_credito.py     # Relatório — Grupo de Crédito (limite, disponível e status por grupo)
    ├── relatorio_variacao_cambial_me.py # Relatório — Variação Cambial ME (PTAX escolhida)
    ├── relatorio_extrato_saldo_bancos.py # Tesouraria — Saldos Bancários (base de teste, só administrador)  [fora da demonstração]
    └── relatorio_recebimentos.py       # Tesouraria — Recebimento por Banco
```

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

## 🖥️ Painéis Disponíveis

A barra lateral abre **expandida**; o botão « a **recolhe** para uma coluna só de ícones (os grupos abrem uma janelinha ao passar o mouse) e ela volta a expandir sozinha ao abrir uma tela com filtros. No topo há o **cartão do usuário** (iniciais e nome, ou só o círculo quando recolhida), que abre o tempo de acesso, Admin e Sair, e abaixo dele a **frase do dia** (40 frases de motivação, uma por dia). A navegação fica na sidebar: grupos (**Financeiro 💲**, **Tesouraria** e **Comercial**) e o item **Relatórios**, que abre a página de cartões. Cada grupo é um menu que **abre ao passar o mouse** e fecha quando o mouse sai. O painel abre "limpo" ao iniciar — nenhum item vem pré-selecionado, apenas uma mensagem de boas-vindas até o usuário escolher algo no menu.

### 🏦 Financeiro

#### 💳 Contas a Receber
**3 itens do menu** (liberados separadamente por grupo), mostrados como Contas a Receber - Visão Geral, Contas a Receber - MI e Contas a Receber - ME — todos lendo a mesma consulta (`QUERY_CONTAS_RECEBER.sql`), sem misturar valores de moedas diferentes entre si.

- **Visão Geral:** os dois mercados lado a lado, nunca somados. Mercado Interno em reais; Mercado Externo com um card por moeda (US$, €, £, NF Complementar) e a soma em reais. Aging por faixas de data — vencidos (até 30 / 30+ dias), 4 intervalos de domingo a sábado a partir de hoje, e a vencer (até 60 dias / 60+) — com barras empilhadas por moeda no lado externo. Botões de Salvar Imagem / Copiar.
- **Mercado Interno:** títulos em reais, com card de inadimplência, aging "A Vencer" (até 30 / 31–60 / 61–90 / 90+ dias), saldo por banco, recebimentos por data e ranking de clientes. Abas internas **Resumo** e **Títulos em Aberto**, com botão 🙈/👁 para ocultar valores.
- **Mercado Externo:** títulos na moeda de origem e em reais, seletor de moeda, ranking de clientes e aging com percentual. Inclui cards de **variação cambial em tempo real** (US$, €, £) com cotação de compra/venda e variação do dia, obtidos via **API do Banco Central do Brasil (BCB/PTAX)**. A planilha Excel exportada traz uma aba extra **PTAX** com o histórico de cotações (compra, venda e variação) de cada moeda na data de geração.

**PDD (Mercado Interno):** título vencido há mais de **90 dias** (contados do vencimento) vira PDD: sai do Vencido e da Inadimplência, mas continua no Saldo em Aberto. Os cards do Mercado Interno mostram Saldo, A Vencer, Vencido, PDD e Inadimplência (botão Vencido | Total), e a classificação (coluna `Classif. Vencto.`) aparece nas tabelas, no Excel e no relatório Contas a Receber - MI. Os limites ficam em `config/pdd.py`.

**Recebimentos e Resumo (Mercado Interno):** o card **Recebimentos por Data** tem o botão **A receber | Recebido**. *A receber* mostra os próximos créditos por data (vencimento + 1 dia útil). *Recebido* mostra o que **entrou no banco** no mês escolhido (padrão: o mês atual; pela data da baixa 196/953), só dinheiro: **desconto, adiantamento e o banco "Encontro de contas transitório" (que só zera lançamentos) ficam de fora**. O botão **Exportar para Excel** gera 3 abas: *A receber*, *Recebido* (com a coluna Banco e a situação Em dia / Em atraso) e *Resumo* (recebido por banco, a receber por mês de crédito e por banco de cobrança). O botão **Painel | Resumo**, abaixo do título, abre a visão **Resumo**: cards (recebido no ano, média mensal, melhor mês, mês contra o mesmo mês do ano anterior até o mesmo dia, **PMR**), giro da carteira, gráfico do recebido por mês com a marca do ano anterior e, ao passar o mouse na coluna, o quadro por banco, tabela por mês e Excel (Resumo mensal, Por banco e Títulos recebidos). O **PMR** (prazo médio de recebimento) é a média de dias entre a emissão da nota e o pagamento, ponderada pelo valor pago; o giro é 365 dividido pelo PMR. Ambos respeitam o botão Ocultar.

**Mercado interno x externo e Classificação:** definidos pela **ação** do movimento (não pelo país do cliente). Ações `161`, `170` = Mercado Interno (`MI`); `162`, `171` = Mercado Externo (`ME`); `262` = NF Complementar ME; `288` = NF Complementar MI; `326` = Sucatas. A coluna `CLASSIFICACAO` (usada na Situação Cliente) reflete esse mesmo agrupamento.

#### ❌ Inconsistências
Exibe lançamentos com erros identificados no processamento (categoria de erro por classe, ação/segmento e tipo de favorecido). **Abre direto com todos os dados, sem filtros** (igual ao Contas a Receber), com cards de total e por categoria, tabela e Excel. Envio automático de e-mail para os solicitantes, com tabela formatada no corpo (incluindo Filial, Data e Valor) e planilha `.xlsx` em anexo com as mesmas colunas.

### 🏛️ Tesouraria

- **Extratos Bancários:** *(fora da demonstração: depende de acesso direto ao banco)*
- **Recebimento por Banco:** recebimentos agrupados por banco.
- **Saldos Bancários:** *(fora da demonstração)*

### 🛒 Comercial

#### 📊 Visão Geral Comercial - MI
Painel do Mercado Interno para o comercial: cards de **Vendido no mês anterior e no atual**, faturamento dos últimos 12 meses **por vendedor** (colunas empilhadas, com variação % sobre o mês anterior), **Top Vendedores** do mês, Top Clientes a Receber, Vencido por Cliente, Faixa de Atraso e a tabela **Situação Grupo de Crédito** (grupos bloqueados, com pesquisa). O vendido soma o total da NF (ações MI 161/170/288/326, sem canceladas) e foi conferido contra o relatório de faturamento do Mega.

#### 💳 Grupo de Crédito (Limite de Crédito)
Consulta de limite, saldo disponível e consumo (Nota Fiscal / Pedido de Venda) por **grupo econômico**, com gráfico de rosca (`plotly.graph_objects`, mais leve que `plotly.express`) e tabela de clientes vinculados ao grupo (colunas PV / NF / Total / Faturado). Botões de exportação (Excel / Imagem / Copiar) no rodapé.

O painel também mostra o **Total Faturado do Grupo** e o **faturamento por ano** (soma de todos os agentes do grupo, ao lado do gráfico de rosca), além do **Adiantamento Recebido em Aberto** (cartão no topo e coluna por cliente na tabela, inclusive no Excel e na imagem) — o saldo em aberto dos adiantamentos com natureza *Recebido*, somado dos agentes do grupo. Vem da consulta de Adiantamentos (`QUERY_ADIANTAMENTOS_GERAL.sql`), ligada ao grupo pelo código do agente. Agentes sem grupo de crédito não aparecem nessa tela (ficam disponíveis no relatório de Adiantamentos).

O painel traz também o card **Notas Pendentes de Validação**, colorido pela situação das notas dos clientes do grupo (Mercado Interno): **vermelho** = pendência bloqueante (prazo documental vencido), **azul** = validação manual (documento aguardando revisão), **verde** = nenhuma pendência, **cinza** = indisponível. O subtítulo mostra o "Prazo" (dd/mm/aaaa) e, quando há os dois tipos, as duas contagens (consulta `QUERY_PENDENCIAS_BLOQUEANTES.sql`, cache de 5 minutos). Só contam os documentos cuja regra na Gestão documental do SyncProcess está **ativa e marcada como "Bloqueia"** (hoje CNH do motorista, Nota fiscal com canhoto, Carta de temperatura, Aceite do Pedido de Venda e Pedido de Compra - Cliente; a consulta lê `IBA_DOCREGRA`, então acompanha mudanças feitas lá). É só informação: **não muda** o Status do Faturamento, que continua vindo do crédito. Se o banco não responder, o card mostra "—" e a tela abre normalmente.

O painel exibe ainda o card de **Status do Faturamento** (Liberado / Bloqueado) com base na situação de crédito consolidada do grupo, refletindo a mesma lógica usada em Situação Cliente.

#### ⚠️ Resumo Pendências *(só quem está no grupo fixo de mesmo nome)*
Acompanhamento por **quantidade** das pendências do Mercado Interno: quatro cartões no padrão do Descontos Contratuais Pendentes (**Descontos Contratuais Pendentes**, **Boletos Não Gerados** prontos para gerar, **Notas Pendentes de Validação** com bloqueantes e validação manual, e **Esperado e Recebido no banco** do dia, em títulos e em R$ (único cartão com valores); os três primeiros passam sozinhos de cliente em cliente, com pausa ao passar o mouse) e, embaixo, o gráfico das notas pendentes de todos os clientes (uma barra por nota, filtro Todas/Bloqueantes/Validação manual, rolagem, e a NF abre o controle de venda no SyncProcess pelo número do controle). Usa `QUERY_PENDENCIAS_NOTAS.sql` e as mesmas regras dos cartões e relatórios de origem. Além dos documentos que bloqueiam, o quadro mostra o **Pedido de venda** quando ele está válido (vem do checklist do controle: `IBA_DOCVINCULO` + `IBA_DOCVALIDACAO`). O nome do cliente abre no SyncProcess a lista de controles dele (`?q=NOME`) e a NF abre o controle. Ao lado de cada cliente vai um cadeado (vermelho fechado = crédito bloqueado, verde aberto = liberado, pela situação do grupo no Grupo de Crédito). O filtro **Para desbloquear** (e o bloco abaixo do quadro, em "Todas") lista os clientes bloqueados no crédito, com controle de venda aberto (`QUERY_CONTROLES_ABERTOS_MI.sql`) e sem pendência em documento que bloqueia em nenhum cliente do grupo: é uma lista de análise, o bloqueio pode ser de crédito (limite, inadimplência), não só documental. As notas **a vencer** (com NF e documento que bloqueia ainda sem anexo, com prazo aberto: sem anexo até o prazo, a nota passa a bloquear) também entram no quadro de notas (em Todas e no botão **A vencer (sem anexo)**, depois de Validação manual), com o documento "Pendente" e o prazo (só no quadro: o card Notas Pendentes e o gráfico da Situação Cliente continuam contando só bloqueante e validação manual). O botão **Excel** do painel gera 2 abas: Notas pendentes e Para desbloquear.

#### 🔍 Situação Cliente
Visão consolidada por cliente — cruza a base de Contas a Receber com o Grupo de Crédito. A busca inclui **todos os clientes conhecidos** (Contas a Receber, Grupo de Crédito e Total Faturado), inclusive quem **não tem título em aberto** — nesse caso a tela mostra os cards de faturamento/situação e uma mensagem no lugar da tabela e do aging. Busca por **código ou nome** do cliente (a lista mostra o nome primeiro e depois o código), card de **Status do Faturamento** (Liberado / Bloqueado) com base na situação de crédito, total faturado histórico, aging de vencimento em barras (empilhadas por moeda) e **faturamento por ano** (todo o histórico, ao lado do aging), tabela de títulos em aberto com colunas Prazo, Classificação e Dias Vencto. (negativo quando vencido). Filtros de **Vendedor** e **Mercado** (MI / ME) na sidebar. Os clientes do Mercado Interno têm o card **Notas Pendentes de Validação** (cores vermelho/azul/verde, ver acima), ao lado do Status, e, quando há nota pendente, um **gráfico "Notas pendentes de validação"** numa terceira coluna ao lado do aging: uma barra por nota (tamanho = documentos pendentes; vermelho = bloqueante, azul = validação manual), com barra de rolagem quando há muitas e, ao passar o mouse na linha, os nomes dos documentos (consulta `QUERY_PENDENCIAS_NOTAS.sql`). Para clientes do mercado externo, mostra também o **saldo em moeda** e as colunas Moeda, Cotação e Saldo em Aberto (Moeda) na tabela. A coluna **Complemento** fica por último, na tela e no Excel (cujo título é "Títulos do Cliente — código — agente").

#### 📈 Faturamento por Cliente ou Grupo
Visão detalhada de faturamento por agente ou grupo econômico. Os cards ficam em **no máximo 4 por linha**, em três grupos: limite de crédito; títulos em aberto (total, a vencer, vencido, inadimplência); e situação (documental, faturamento), adiantamento e **Perfil de pagamento**. O **Perfil de pagamento** classifica o pagador pelo histórico de baixas (Mercado Interno): compara cada pagamento com o **crédito esperado** (vencimento + 1 dia útil, sem fins de semana nem feriados bancários) e usa o atraso médio ponderado pelo valor e o % do valor pago no prazo: **Ótimo** (mais de 90% no prazo e atraso médio de até 1 dia), **Bom** (até 5 dias), **Regular** (até 15), **Atenção** (até 30) e **Mau** (acima disso); a cor de fundo do card indica o nível. A seção **Histórico de pagamentos** mostra o perfil (com a tendência dos últimos 12 meses), uma barra com as faixas de pagamento e a tabela de todas as parcelas, pagas e em aberto. O Excel traz as abas **Resumo** (com o perfil) e **Histórico de Pagamentos**. Limites em `config/pagador.py`. Botões de exportação (Excel / Imagem / Copiar) no rodapé.

#### 🗺️ Faturamento por UF (Mercado Interno)
Mapa do Brasil colorido por UF, com seletor de **métrica** (Faturado, Em aberto, Inadimplência e Variação) e de **período** do faturado (ano atual ou últimos 12 meses, sempre com **meses fechados**; a variação compara com o mesmo período do ano anterior ou com os 12 meses anteriores). Cada estado mostra a sigla e o % da métrica (os pequenos — DF, SE, AL, RN e PB — só no detalhe, ao clicar). Clicar no estado (ou escolhê-lo na lista) abre o detalhe (faturado, % do total, variação, em aberto, inadimplência, clientes e prazo médio), um top 8 da métrica e a **lista de clientes do estado**, ordenável, com exportação para Excel de todos os estados. O faturado vem do faturado mensal por cliente, o em aberto do Contas a Receber e o estado do cadastro de agentes; clientes do exterior ou sem estado ficam fora do mapa e aparecem em um aviso. O contorno dos estados está em `assets/brasil_estados.geojson` (malha pública do IBGE, simplificada).

### ✅ Relatórios

O item **Relatórios** do menu abre uma **página inicial de cartões**, organizada em colunas por área (Contas a Pagar, Movimento Financeiro, Contas a Receber), com campo de busca. As áreas com mais relatórios aparecem primeiro. Cada relatório é um botão com nome e descrição; dentro dele há o botão **← Voltar aos relatórios**.

Para incluir um relatório novo, basta registrá-lo em `PAGINAS_RELATORIOS` e em `CARTOES_RELATORIOS` (descrição e área) no `app.py`.

Todos os relatórios seguem o mesmo fluxo: **filtros na barra lateral + botão "📄 Gerar Relatório"**. O título do relatório aparece antes de gerar e, depois, passa a mostrar o período (ex.: "Contas a Pagar — 01/09/2026 a 24/09/2026"). O período (Data inicial / Data final, no formato dd/mm/aaaa) vem preenchido com o **mês vigente** (dia 1 até hoje) e é obrigatório; Organização (e Status, quando existir) são opcionais.

Nos relatórios pesados (**Contas a Pagar** e **Aprovadores**), o **Gerar Relatório** também renova os dados: se o que está em cache foi buscado no Oracle há mais de 1 minuto, ele consulta de novo; se foi há menos, reaproveita.

#### 💰 Contas a Pagar *(área Contas a Pagar)*
Movimentos de contas a pagar filtrados por Organização, Status e período (data de prorrogação). Não há coluna de vencimento original: status, dias, faixa e período usam o **Prorrogado**, a data real do pagamento. O **Status vem marcado em VENCIDO e A VENCER** por padrão (marque BAIXADO para incluí-los). Há também o filtro **Agente** (favorecido). A consulta tem **data de corte em 01/01/2026** (`{{DATA_CORTE}}` em `QUERY_CONTAS_APAGAR.sql`); ao escolher uma Data inicial anterior, o painel busca de novo no Oracle a partir dessa data. Cards **só de quantidade** (Qtd. Títulos Vencidos / a Vencer / APs com Erro), sem valor. O Detalhe mostra as colunas da consulta em **ordem fixa** (ORG, FILIAL, AP, aprovação, favorecido, valores, datas, rateios, anexos — com STATUS_DIAS e FAIXA_DIAS no final), sem coloração de linha na tela (custoso em volume grande). O Excel (`Contas a Pagar <período>.xlsx`) segue o padrão da planilha modelo: cabeçalho azul-marinho, bordas, larguras por coluna, valores em formato contábil, datas dd/mm/aaaa e cores em STATUS e APROVACAO — essa coloração só existe no Excel.

#### 👤 Aprovadores *(área Contas a Pagar)*
Relatório de aprovação de APs por período e organização. Inclui os títulos do tipo PC. Traz as colunas **Forma de pagamento** e **Complemento** e o filtro **Primeiro aprovador**, que mostra só as APs em que o aprovador escolhido é o primeiro do fluxo. Cards **só de quantidade** (Qtd. em Aprovação / Filiais), sem valor. A data do relatório é o **Prorrogado** (a data real do pagamento; o vencimento original não é usado), tanto na coluna quanto no filtro de período. Traz a **Classificação** do favorecido (**Produtor** ou **Fornecedor**, a mesma regra do Contas a Pagar: ações 323, 182 e 327 são Produtor; vale para a AP inteira, inclusive o INSS Funrural dela), com o filtro **Classificação** na barra lateral (começa vazio e traz tudo) e os cards **Produtores** e **Fornecedores**.

#### 📄 Contas a Receber - Exportação *(área Contas a Receber)*
Exportação completa dos títulos em aberto (MI + ME), reaproveitando a mesma consulta do painel de Contas a Receber. Filtros de Entrada, Vencimento, Mercado e Status são **opcionais** — sem nenhum preenchido, mostra tudo que está em aberto. Cards de quantidade separados por situação: **Qtd. A Vencer** e **Qtd. Vencidos** para MI e ME, mais **Qtd. Total MI + ME**. A tela mostra um resumo legível; o Excel traz as ~38 colunas da consulta inteira, com nomes legíveis, `Dias Vencto.` negativo quando vencido (única coluna que pode ser negativa) e os percentuais (`% Regra`, `% Aplic. NF`, `% Aplic. Financeiro`) exatamente como a consulta devolve (texto, ex. `10.00%`), sem virar número formatado.

#### 📄 Contas a Receber - MI *(área Contas a Receber)*
Títulos do **Mercado Interno** pagos, vencidos e a vencer, com data de pagamento, desconto e baixa de adiantamento. O **período de vencimento é obrigatório**; só ele vai ao banco (o banco lê a janela de emissão e o recorte por vencimento é feito em pandas, para a consulta responder em 2–3 s em qualquer período). Data de pagamento vem só das baixas 196/953; PAGO sai em azul no Excel (`Contas_a_Receber_MI dd-mm-aaaa a dd-mm-aaaa.xlsx`).

#### 📄 Boleto Não Gerado *(área Contas a Receber)*
Títulos do Mercado Interno sem boleto gerado, com status Liberado ou Bloqueado (desconto da regra ainda não aplicado). **Clientes que pagam por transferência** (cadastrados em Admin > Clientes por Transferência) não entram, e uma linha no topo informa quem foi deixado de fora.

#### 📄 Descontos Contratuais Pendentes MI *(área Contas a Receber)*
Mercado Interno, regra Financeiro: os descontos contratuais ainda não aplicados, com a classe de desconto a lançar.

#### 📄 Descontos Realizados *(área Movimento Financeiro)*
Descontos já realizados (ação 948) do Mercado Interno e do Externo, por período: contratuais, operacionais e concedidos.

#### 📄 Fretes Mot - Matriz x Filial *(área Contas a Pagar)*
Contas a pagar de fretes (classe Mot) da Demo à Filial e da Filial à Siderúrgica, por período de prorrogação, com o rateio por classe, centro de custo e projeto.

#### 💱 Variação Cambial ME *(área Contas a Receber)*
Variação cambial dos títulos do Mercado Externo com a PTAX do Banco Central escolhida.

#### 💳 Grupo de Crédito *(relatório, área Grupo de Crédito)*
Limite, disponível, % utilizado, documentação e status de faturamento por grupo econômico.

#### 📊 Boletos DDA *(área Contas a Pagar)*
Dashboard dos boletos recebidos via DDA, com filtros de período (dd/mm/aaaa), valor mínimo, status e sacados, e botão **Exportar para Excel** abaixo da tabela de detalhes.

#### 💰 Adiantamentos *(área Movimento Financeiro)*
Adiantamentos em aberto, com seletor **Todos / Efetuado / Recebido**, busca por agente e filtro de Organização. Cards de total lançado, saldo em aberto e agentes no período (no topo), tabela com organização, agente, natureza, documento, data, valor, saldo, situação e complemento, e exportação em Excel, imagem e cópia.

## 📤 Exportação e Compartilhamento (Excel / Imagem / Copiar)

Nas telas de **Contas a Receber**, **Limite de Crédito**, **Situação Cliente** e **Adiantamentos**, os dados podem ser compartilhados de 3 formas, sempre no mesmo padrão de botões:

| Botão | O que faz |
|---|---|
| ⬇️ **Excel** | Exporta a tabela em `.xlsx`, com as colunas já formatadas (moeda no padrão `R$ 1.350,00`) |
| 🖼️ **Imagem** | Gera um PNG com **fundo branco** (cards + tabela), pronto para anexar em e-mail — gerado via `Pillow`, sem depender de screenshot |
| 📋 **Copiar** | Copia a imagem PNG direto para a área de transferência (Clipboard API do navegador), bastando dar `Ctrl+V` no corpo do e-mail |

> ⚠️ O botão "Copiar" depende de suporte do navegador à Clipboard API (`ClipboardItem`) e geralmente exige contexto seguro (HTTPS ou `localhost`).

**Todas as planilhas exportadas pelo app** (`exportar_excel()` e `exportar_excel_contas_pagar()` em `utils/exporters.py`, inclusive o anexo do e-mail de Inconsistências) seguem o mesmo padrão: cabeçalho azul-marinho, **filtro automático (autofiltro) no cabeçalho** e **bordas finas em todas as células**, além de colunas identificadoras (`Cód. Cliente`, `Ano`, `Semana`, `Nosso Número` etc.) em formato Geral, sem separador de milhar.

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

## ⚡ Performance

> Na demonstração os dados são gerados em memória (sem Oracle); os tempos, caches e o acesso ao banco descritos abaixo são os do painel de produção.

Cada painel possui sua própria função de carregamento com cache independente (`@st.cache_data`):

| Painel | Função | TTL do cache |
|---|---|---|
| Grupo de Crédito (Geral e Saldo por Agente) | `carregar_grupo_credito_*()` | 1 minuto |
| Inconsistências | `carregar_aps_erro()` | 1 minuto |
| Contas a Receber | `carregar_contas_receber()` | 1 minuto |
| Adiantamentos (Geral e Total por Agente) | `carregar_adiantamento_*()` | 1 minuto |
| APs Vencidas *(painel fora do menu)* | `carregar_aps_vencidas()` | 10 minutos |
| Aprovadores | `carregar_relatorio_approvo()` | 10 minutos |
| Contas a Pagar | `carregar_contas_apagar()` (um cache por data de corte) | 10 minutos |
| Boletos DDA | `carregar_boletos_dda()` | 1 hora |
| Total Faturado por Cliente | `carregar_total_faturado_cliente()` | 6 horas |

O cache é **compartilhado entre todos os usuários** e é limpo ao reiniciar o Streamlit (ou com `C` → *Clear cache* — atenção: **Ctrl+C** para copiar texto também aciona esse atalho sem querer, pois o navegador não distingue o Ctrl; use os botões "📋 Copiar" das telas em vez de selecionar+copiar manualmente). Nos três relatórios pesados (Contas a Pagar, Aprovadores e APs Vencidas), o **Gerar Relatório** / **Filtrar** renova os dados quando o que está em cache tem mais de 1 minuto (`atualizar_se_antigo()` em `data_service.py`), sem forçar o Oracle a cada clique.

**Acesso ao Oracle:** as consultas usam um **pool de conexões** criado uma única vez (`_get_pool()`, com `st.cache_resource`) e buscam **5.000 linhas por vez** (`cursor.arraysize`/`prefetchrows`), o que reduz muito o tempo de abertura dos painéis.

Os dados de cada painel só são carregados quando o usuário acessa aquele painel — não há carregamento de todas as queries no início da aplicação. Todas as rotas que buscam dados mostram um indicador **"Carregando dados..."** (`st.spinner`) enquanto consultam o Oracle.

**Excel e imagem para e-mail também usam cache** (`exportar_excel()`, `exportar_excel_contas_pagar()` e as funções de `gerar_imagem_*` em `utils/imagem_email.py`, todas com `@st.cache_data`) — antes eram remontadas a cada interação da tela (qualquer clique, mesmo sem o usuário pedir o arquivo), o que pesava bastante em relatórios grandes; agora só são refeitas quando os dados de entrada mudam.

**Grupo de Crédito** usa `plotly.graph_objects.Pie` em vez de `plotly.express.pie` no gráfico de rosca — o `px` passa por uma camada de validação/template bem mais pesada; essa troca sozinha já respondia por boa parte do tempo de carregamento da tela.

> 💡 **Situação Cliente** usa a consulta **enxuta** de Contas a Receber (filtrada, rápida) para títulos/aging, e a consulta **leve e separada** (`QUERY_TOTAL_FATURADO_CLIENTE.sql`, sem `FIN_MOVIMENTO`) só para o card de "Total Faturado" e o faturamento por ano — evita que uma única tela precise de uma consulta pesada com histórico completo. Essa consulta soma o **total da nota fiscal** (`NOT_RE_VALORTOTAL`, o mesmo valor do financeiro), não a soma dos itens — em notas com desconto de rateio a soma dos itens pode divergir do total da nota; validado contra o sistema.

## 🏗️ Arquitetura

O projeto segue os princípios de **arquitetura limpa** com separação clara de responsabilidades:

| Camada | Responsabilidade |
|---|---|
| `views/` | Renderização da interface (Streamlit) |
| `services/` | Regras de negócio (conexão Oracle, autenticação, queries, filtros e e-mail) |
| `components/` | Elementos visuais reutilizáveis (cards padronizados) |
| `utils/` | Funções auxiliares sem dependência de UI (formatação, exportação, geração de imagem) |
| `config/` | Configurações globais da aplicação |
| `assets/` | Arquivos estáticos (CSS, logo) |
| `query/` | Consultas SQL executadas diretamente no Oracle |

## Observações

- A cotação PTAX do mercado externo é consultada na API pública do Banco Central (`olinda.bcb.gov.br`);
  sem internet, esse bloco fica vazio e o resto funciona normalmente.
- Tecnologias: Python, Streamlit, Pandas, Plotly e Pillow (imagens para e-mail).
