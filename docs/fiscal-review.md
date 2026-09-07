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
Nenhum lançamento, cadastro ou preço foi alterado nesta revalidação.
