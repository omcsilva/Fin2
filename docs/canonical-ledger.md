# Ledger canônico e decisões de reconciliação

A migração `0008_canonical_ledger.sql` introduz o esquema `ledger`. Os registros
brutos em `source_record` continuam imutáveis e permanecem como evidência da
importação final do Fin1.

As projeções `ledger.event`, `ledger.position_component` e
`ledger.cash_component` expõem, respectivamente, os eventos de investimento,
seus efeitos sobre quantidade e os lançamentos de caixa. Um lançamento ligado a
uma movimentação é o componente de caixa autoritativo e não deve ser somado
novamente ao valor da movimentação.

`ledger.reconciliation_decision` guarda decisões revisadas sem reescrever a
fonte. `ledger.position_reconciliation` somente fornece `canonical_quantity`
quando a fonte coincide com os movimentos ou quando existe uma decisão resolvida
com quantidade explícita. Casos pendentes continuam com quantidade canônica nula.

## Revisão da importação final

O comando `python -m scripts.resolve_fin1_positions` é restrito ao lote informado
e valida as evidências antes de gravar qualquer decisão. Ele registrou:

- SPXI11, MSFT34, TSMC34 e AMER3 como posições encerradas, com quantidade
  canônica zero;
- “Reais em espécie” como instrumento monetário pendente. Seus cinco movimentos
  têm quantidade zero, enquanto os acumulados financeiros e de quantidade do
  Fin1 são incompatíveis entre si.

O banco privado foi copiado para `fin2-before-ledger.duckdb` antes da aplicação.
Após a migração há 2.379 eventos, 2.379 componentes de posição e 2.656 componentes
de caixa. Quatro divergências estão resolvidas e uma permanece pendente.

O próximo passo é reconciliar os seis saldos de conta divergentes e os quatro
lançamentos sem conta. Só depois as telas de patrimônio devem consumir saldos
canônicos em lugar dos agregados materializados do Fin1.

## Reconciliação de caixa

As migrações `0009_canonical_cash.sql` e `0010_cash_dashboard.sql` corrigem a
interpretação do extrato: `source_value` já contém o sinal efetivo. O campo
legado `credito` permanece disponível como evidência, mas não altera o sinal uma
segunda vez.

Cinco contas foram resolvidas: três não possuem lançamentos e recebem saldo
operacional zero; as duas contas Clear encerradas têm soma canônica e saldo final
iguais a zero. Quatro diferenças intermediárias na Clear Marcos são apenas a
ordem de lançamentos que compartilham a mesma data e não alteram o saldo após os
pares.

A conta APEX Marcos (Banco Inter) tinha 14 lançamentos importados somando
USD 12.666,49, enquanto o cadastro marcado como zerado guardava saldo zero.
Em 06/09/2026 foi corrigida uma associação documental indevida: os sete extratos
preservados pertencem à APEX Marcos (App XP), e todos os saldos conferem com
essa conta, já encerrada com saldo zero após a transferência para a Schwab.
Os vínculos e observações foram corrigidos com auditoria e backup. O ajuste
manual indevido de USD 2.171,70 no Banco Inter foi estornado, preservando o
lançamento original. A comparação anterior com USD 42.876,79 era entre contas
distintas e não deve fundamentar ajustes.

Ainda em 06/09/2026, o usuário informou as saídas de 16/04/2024: USD 10.000,00
para Banco Inter e USD 2.666,49 para Global Account. Foram registradas duas
retiradas auditáveis, com contrapartida na Conta de Resultado. O caixa do ledger
passou a zero e a decisão foi resolvida com vigência em 16/04/2024, explicitando
a declaração do usuário como fonte. Os lançamentos importados foram preservados;
a soma original continua disponível para conferência. A conciliação se refere ao
caixa histórico APEX, não às operações novas da Plataforma Global em 2025/2026.

Os quatro lançamentos sem conta são duplicatas dos lançamentos 945–948. As cópias
válidas têm mesma data, descrição e valor, estão associadas à conta 4 e possuem o
indicador correto de débito. Os órfãos 941–944 foram classificados como duplicatas
e são ignorados na contagem operacional do dashboard.

A página Caixa passou a usar as projeções canônicas e mostra separadamente o
saldo canônico e o estado da conciliação.
