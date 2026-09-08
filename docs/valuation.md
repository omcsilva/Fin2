# Valorização de referência e alocação por moeda

Acesse [Alocação](http://127.0.0.1:8020/fin2/alocacao/). Implementação em `0004_reference_valuation.sql`; consultas somente leitura sobre a cópia legada.

## Critérios

O valor indicativo é a quantidade reconstruída na data de corte multiplicada pela cotação preservada do ativo. Não é preço atual nem uma série histórica de patrimônio. Cada cotação mantém sua própria data, que pode anteceder bastante o corte.

Uma posição entra no subtotal apenas quando:

- A quantidade reconstruída com todos os movimentos liquidados coincide com a quantidade salva; nenhum multiplicador ou quantidade necessário está ausente.
- A quantidade na data de corte é positiva.
- Existe uma moeda identificada.
- A cotação é positiva e tem data não posterior ao corte.

Quantidades divergentes/negativas, moedas ausentes, preços ausentes/inválidos e preços futuros permanecem visíveis, mas sem valor no subtotal. Posições zeradas não aparecem na lista ativa. Não se assume valor zero para uma posição sem cotação.

Cotações com mais de **30 dias em relação ao corte** são consideradas antigas para sinalização nesta versão. Elas entram no subtotal indicativo, acompanhadas de contagem de cobertura e aviso explícito. Esse limiar é uma convenção de interface, não um critério de validade financeira por tipo de ativo.

## Moedas e percentuais

Subtotais e alocação por classe são calculados separadamente para cada moeda. Não há taxa de câmbio nem soma entre moedas. As moedas foram normalizadas para códigos ISO; as abreviaturas da origem são preservadas no payload importado.

Os percentuais têm como denominador apenas o subtotal das posições com valor disponível naquela moeda. Portanto, não representam a distribuição de todo o patrimônio quando existem exclusões. Classes ausentes ficam identificadas como “Sem classe”. Carteiras muitos-para-muitos não são usadas para multiplicar linhas; cada aplicação contribui uma única vez dentro do seu lote.

O valor monetário é mantido em DECIMAL, com projeção `DECIMAL(38,10)` e apresentação de duas casas. A porcentagem é usada apenas para exibição da participação. Caixa das contas não é adicionado aos valores das aplicações.

## Resultado em 31/08/2026

| Moeda legada | Não zeradas ou em revisão | Com valor | Excluídas | Com cotação antiga |
| --- | ---: | ---: | ---: | ---: |
| REAL | 54 | 46 | 8 | 46 |
| DOL | 13 | 13 | 0 | 13 |

Das 260 aplicações, 193 estão zeradas. As oito exclusões correspondem a cinco diferenças de quantidade e três cotações ausentes/inválidas. **Todas as 59 posições com valor disponível usam cotação antiga.** Nenhum preço externo foi consultado ou atualizado.

Foram produzidos oito grupos de alocação por moeda/classe. Esses valores não estão reconciliados com extratos externos nem constituem apuração de retorno, renda ou impostos.

## Verificação e operação

17 testes passaram. A cobertura sintética inclui cotação ausente, futura, antiga, divergência de quantidade e segregação de moedas. A página real e seus filtros responderam HTTP 200.

A atualização foi aplicada após parar a árvore do servidor local e preservar `fin2-before-valuation.duckdb` no diretório privado. O servidor foi reiniciado em `127.0.0.1:8020`. O cabeçalho aprovado foi preservado e nenhum dado do Fin1 foi corrigido.

Estado atual: as cinco divergências de quantidade foram resolvidas por decisões auditadas. A brapi atualiza os ativos configurados para esse mecanismo; ativos NENHUM podem receber cotações e avaliações manuais com fonte e data. A normalização das moedas está concluída. A [reconciliação final](final-reconciliation.md) conferiu os valores com cobertura. O INRD11 passou a ter fechamento válido de R$ 72,65 em 27/08/2026; somente Brasilprev CICLO DE VIDA 2030 I PGBL continua sem avaliação. A aceitação final permanece pendente. Não há conversão cambial implementada.
