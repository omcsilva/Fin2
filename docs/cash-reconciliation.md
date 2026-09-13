# Conferência de caixa e investigação de quantidades

Entrega de 31/08/2026. As novas consultas são projeções somente leitura da migração `0003_cash_reconciliation.sql`. Não houve correção de registros nem escrita no Fin1.

## Caixa

Acesse [Caixa](http://127.0.0.1:8020/fin2/caixa/). As 16 contas aparecem separadas por moeda, com saldo salvo, saldo reconstruído, saldo na data de corte e diferença. Clique na conta para ver os lançamentos e saldos intermediários; cada linha permite abrir o registro original e seus documentos.

Regras aplicadas:

- Considerar somente `Lancamento`; não somar novamente `Movimentacao`.
- Normalizar o sinal para a conferência com `abs(valor)` em créditos e `-abs(valor)` em débitos. O valor original não é modificado.
- Começar em zero, reproduzindo a convenção do recálculo legado. Isso não comprova que o histórico esteja completo ou que exista um saldo inicial documentado.
- Reconstruir o acumulado por conta/lote, em ordem de timestamp de liquidação e ID, antes de paginar a lista.
- Comparar o saldo salvo com todo o histórico; apresentar separadamente a soma até a data de corte.
- Não converter moedas nem criar um total que misture BRL, USD e outras moedas.
- Valores ou indicadores crédito/débito ausentes tornam o resultado da conta indisponível. Datas ausentes impedem o resultado no corte.
- Lançamentos sem conta permanecem preservados e fora dos totais por conta.

O cálculo usa `DECIMAL(28,4)`, a escala monetária do legado, e igualdade exata, sem tolerância escondida. Valores são exibidos com quatro casas para não ocultar pequenas diferenças.

### Resultado na cópia atual

| Verificação | Resultado |
| --- | ---: |
| Contas com saldo final coincidente | 10 |
| Contas com diferença de saldo final | 3 |
| Contas sem saldo legado para comparação | 3 |
| Lançamentos sem conta, excluídos dos totais | 4 |
| Diferenças de saldo intermediário | 368 |
| Valores cujo sinal difere da convenção crédito/débito | 81 |

Diferenças intermediárias não equivalem a 368 erros independentes: uma divergência inicial pode se propagar pelas linhas seguintes. Saldos coincidentes tampouco provam reconciliação com extratos externos.

Relatório privado: `$HOME/Fin2-private/development/cash-report.json`. Ele inclui IDs de origem, saldos, diferenças e estatísticas; não deve entrar no Git. A cópia anterior à migração está em `fin2-before-cash.duckdb`, no mesmo diretório privado.

## Cinco diferenças de quantidade

Agora o nome do ativo em [Posições](http://127.0.0.1:8020/fin2/posicoes/) abre a trilha de conferência: movimentos, operações, quantidades originais, multiplicadores e acumulados salvos. Cada movimento liga ao registro de origem e seus documentos.

A inspeção da cópia constatou:

- Quatro aplicações possuem compras e vendas de quantidades equivalentes, cuja soma com os multiplicadores é zero. As quantidades materializadas das aplicações permanecem negativas. Em três delas, o último acumulado salvo em movimento já é zero; na outra, também existe divergência no acumulado salvo do último movimento.
- Uma aplicação tem cinco movimentos de compra com quantidade zero, mas uma quantidade não zero salva na aplicação. Um movimento também contém acumulado salvo não zero, apesar da quantidade individual zero.

Esses fatos demonstram inconsistência entre movimentos e campos materializados, mas não provam a causa histórica nem autorizam escolher qual valor corrigir. É preciso conferir documentos e possíveis alterações anteriores. Não foram excluídos movimentos ou recalculados campos do Fin1.

## Validação e próximos passos

Testes sintéticos cobrem crédito, débito com sinal divergente, data futura, acumulado, conta ausente e informação incompleta. As páginas de caixa, detalhe de conta e detalhe de quantidade responderam HTTP 200 usando a cópia real.

Ainda pendem a reconciliação com extratos externos, a revisão das divergências, as regras de custo médio e os cálculos de renda/valorização. Não há apuração fiscal nesta entrega.
