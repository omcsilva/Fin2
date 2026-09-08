# Revisão fiscal dos dados reais

Revisão executada em 06/09/2026 sobre o lote canônico, com corte em 06/09/2026
e todas as aplicações, inclusive as marcadas como zeradas.

## Estado da apuração

A prévia reconstrói 45 combinações de mês, titular e modalidade entre junho de
2016 e maio de 2024. Esses resultados ainda não formam o relatório fiscal final:
33 aplicações brasileiras ou FII que possuem vendas foram excluídas porque seu
histórico contém portabilidade, desdobramento, bonificação, quantidade ausente
ou outra evidência insuficiente para transportar o custo com segurança.

Há também dois créditos de IRRF que não fecham a apuração. Um crédito de R$ 6,61
tem competência documental em abril de 2020, mas não encontra imposto calculado
na mesma modalidade. Outros R$ 2,42, liquidados em dezembro de 2017, continuam
sem evidência suficiente para determinar a competência.

Por isso, os valores exibidos continuam sendo uma prévia parcial. O relatório
agora identifica programaticamente aplicações excluídas que contêm vendas e só
considera a apuração completa quando o escopo inclui aplicações zeradas e não
restam exclusões nem IRRF sem correspondência.

## Condições para conclusão

- reconstruir o custo das 33 aplicações excluídas a partir das notas e eventos
  societários, preservando o custo nas portabilidades;
- resolver a competência e o aproveitamento dos dois grupos de IRRF;
- comparar os resultados mensais completos com informes, notas e declarações;
- registrar a aprovação dos valores antes de marcar esta tarefa como concluída.

## Revalidação local em 07/09/2026

Consulta somente leitura à base de desenvolvimento, com todas as carteiras,
sem filtro de ano e incluindo zerados, reproduziu 45 combinações mensais e
33 aplicações excluídas: 29 por operações que exigem decisão de custo e quatro
por compras/vendas sem quantidade ou valor. O relatório permanece incompleto.

Os grupos de IRRF sem correspondência nessa base totalizam R$ 6,57 e R$ 5,40,
ambos sem competência identificada. São 18 lançamentos sem documento diretamente
vinculado ao registro de caixa. Esses resultados diferem dos valores registrados
na revisão de 06/09 acima; não se deve assumir equivalência entre as bases ou
substituir os números de produção sem repetir a consulta naquele ambiente.

A inspeção da origem identificou uma venda sem quantidade cuja descrição é de
juros sobre capital, com outro movimento de rendimento ligado ao mesmo lançamento;
compras/vendas sem quantidade; e um fundo DI classificado como ações brasileiras.
Esses casos exigem revisão da classificação, duplicidade e documentos antes de
qualquer correção financeira. Cotações históricas não comprovam quantidades negociadas.

O inventário detalhado, IDs dos movimentos e evidências foram preservados fora
do Git em `Fin2-private/reviews/2026-09-07/review.md` e `evidence.json`.

## Correções documentadas em 07/09/2026

A migração `0049_cost_event_overrides.sql` preserva os movimentos importados e
aplica ajustes somente durante a reconstrução de custo. As notas XP 20009637 e
20508449 comprovam respectivamente a compra e a venda de 100 VALE3 nos movimentos
5120 e 5121. Os documentos foram vinculados aos registros correspondentes.

O movimento 3441 de ITUB4 é ignorado somente no custo médio porque duplica o JCP
ligado ao mesmo lançamento 213. Ele não foi reclassificado no ledger. O movimento
3245 de PETR4 permanece pendente: a descrição indica venda, mas quantidade e valor
estão zerados, e a observação da própria origem questiona a procedência das ações.

O escopo de renda variável passou a usar o nome do produto no cadastro: Ação,
ETF e Fundo Imobiliário. Assim, o PS FI Ref DI CP fica fora da apuração de bolsa
por ser Fundo Renda Fixa, sem depender de um ID numérico específico.

Splits, bonificações e transferências de custódia continuam excluídos até que o
custo seja reconstruído por titular e ativo com conservação comprovada entre
contas. O valor legado das portabilidades não é tratado como custo fiscal.

## Desdobramentos em 07/09/2026

Desdobramentos simples com quantidade adicional explícita e valor zero agora
preservam o custo total e aumentam somente a quantidade. Essa regra resolveu a
aplicação BBAS3 de Marcos, cujo desdobramento de 700 ações em 23/04/2024 ocorreu
depois da venda histórica, sem alterar o ganho já realizado.

A revalidação passou a produzir 50 combinações mensais e 31 aplicações
excluídas: 30 por portabilidade, bonificação ou outro evento que ainda exige
decisão de custo, e uma pela venda PETR4 sem quantidade e valor. Os dois grupos
de IRRF continuam sem competência documental. Desdobramentos combinados com
uma transferência anterior, como BTCI11 e GGRC11, permanecem excluídos pela
transferência.

## Portabilidades exatas em 07/09/2026

Foram pareadas 24 pernas de transferências de custódia de XP para Warren, Clear
para XP e entre contas XP do mesmo titular. O cálculo transporta o custo
reconstruído, sem registrar venda, somente quando ativo, titular, data,
quantidade e custo fecham exatamente. O valor de mercado legado não substitui o
custo.

Com XPML11, KNRI11, LUGG11, BBDC4, BERK34 e GGRC11 de Marcos, e BBPO11,
GGRC11, LUGG11 e SANB11 de Luciana, a revalidação passou a 53 combinações
mensais e 22 aplicações excluídas: 21 por operações ainda não comprovadas e uma
pela venda PETR4 sem detalhe. Pares com diferença de custo, conversões de ticker
e entradas sem saída identificada permanecem bloqueados.

Uma segunda rodada transportou o custo líquido reconstruído em outras 18 pernas
integrais, nas quais o valor patrimonial preservado divergia do custo fiscal.
Foram resolvidos BRCR11, DIVO11, ELET3, KNRI11, USIM3, VALE3 e LIGT3 nos pares
com origem identificada. A prévia passou a 59 combinações mensais e nove
aplicações excluídas: oito por operação sem cadeia completa e a PETR4 sem detalhe.
