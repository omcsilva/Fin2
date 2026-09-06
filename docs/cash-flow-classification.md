# Classificação de fluxos de caixa

A migração `0018_cash_flow_classification.sql` acrescenta a projeção
`ledger.cash_flow_classification`. Ela não altera os lançamentos importados.

Movimentos ligados a uma operação usam esse vínculo para identificar
investimentos, rendimentos, impostos e taxas. Lançamentos avulsos usam padrões
de descrição. Transferências de mesmo valor absoluto, moeda e data, com sinais
opostos, são marcadas como internas; esta é uma correspondência heurística e a
base da decisão permanece visível em `classification_basis`.

TEDs, depósitos e saques sem par são classificados como aportes ou retiradas
externas. Descrições que não satisfazem uma regra ficam em `unclassified` e não
devem ser usadas no cálculo de rentabilidade pessoal até revisão.

A migração `0019_refine_cash_flow_classification.sql` registra a segunda revisão:
compras, vendas, resgates, liquidações, notas de bolsa, câmbio, portabilidades,
IR, IOF e cobranças de plataforma recebem classificação por padrões explícitos.
Descrições genéricas como “ajuste” e lançamentos pessoais continuam sem classe.

A migração `0020_finalize_clear_cash_flow_patterns.sql` expõe a projeção final
`ledger.cash_flow_classification_final` e conclui os casos claros
da segunda revisão: acordos comerciais são receitas, e “Dízimo” e retirada para
o Nubank são fluxos externos conforme o sinal. Ajustes e erro operacional
continuam pendentes, sem valor financeiro inferido.

A migração `0021_cash_flow_decisions.sql` cria decisões imutáveis e a projeção
`ledger.cash_flow_effective`. A tela de relatórios permite classificar cada caso
pendente com justificativa. Uma decisão nova substitui a anterior apenas na
projeção vigente; todas as versões continuam preservadas na tabela de decisões.

## Rentabilidade pessoal

O relatório calcula XIRR anualizada desde o início, separadamente por aplicação.
Entradas e saídas usam somente componentes de caixa vinculados à aplicação, e o
valor de mercado conciliado no corte é acrescentado como fluxo terminal. O
cálculo exige fluxos dos dois sinais e omite posições sem quantidade ou preço
aceitável. O filtro anual não apresenta XIRR enquanto não houver patrimônio de
abertura confiável para todas as classes de ativo.

## Correção do sinal e rateio

A migração `0022_correct_and_allocate_cash_flows.sql` passa a usar o sinal
canônico de `ledger.cash_entry_canonical`. Quando uma nota de corretagem está
ligada a vários movimentos, seu caixa total é distribuído proporcionalmente ao
valor bruto de cada movimento. Assim o total da nota aparece uma única vez nos
relatórios e cada aplicação recebe somente sua parcela no XIRR. A origem da
regra fica marcada como `source_link_allocated`.

A migração `0023_exact_cash_allocation.sql` converte as parcelas para
`DECIMAL(28,4)`. O eventual resíduo de arredondamento é atribuído à última
operação vinculada, fazendo a soma das parcelas coincidir exatamente com o
lançamento de caixa original.

## Conta-corrente única e resultado acumulado

A migração `0041_current_account.sql` cria `ledger.current_account_entry`, a
conta lógica única de contrapartida do investidor. Aportes e retiradas externos
importados e manuais convergem para `current_account`, mantendo a origem e as
contas operacionais intactas. Transferências internas e operações de compra,
venda ou resgate dentro da custódia não constituem novos aportes ou saques.
Estornos manuais cancelam o movimento original a partir da data do estorno.

Relatórios apresenta, por moeda, total investido, total sacado, valor das posições
e resultado = sacado + valor das posições − investido. REAL/BRL e DOL/USD são
normalizados sem conversão cambial. A conta abrange todas as carteiras e acumula
desde o início até o corte selecionado, inclusive quando há filtro anual.
Na versão inicial, o valor apresentado abrangia somente posições; a migração
0042 abaixo passa a incluir os saldos das contas de investimento. Fluxos sem classe, sinais contraditórios e posições sem
avaliação impedem a publicação de um resultado completo. Cotações antigas são
indicadas. A versão inicial deixava quantidades manuais pendentes; a avaliação foi
atualizada conforme a seção abaixo.

## Conta de Resultado e recursos em custódia

A migração `0042_result_account_funding.sql` introduz o nome Conta de Resultado
(`ledger.result_account_entry`) e a origem explícita de cada nova compra manual.
Por padrão, a compra gera um aporte vinculado de mesmo valor: saída da Conta de
Resultado e entrada na conta de investimento, consumida pela compra. Não se deve
registrar outro depósito para esse mesmo aporte. Quando o depósito já foi
registrado, escolha saldo disponível.

Dividendos, vendas e portabilidade usam recursos já presentes na conta de
investimento e não geram aporte. A entrada desses recursos deve estar registrada
como rendimento, venda ou transferência interna, respectivamente. A opção de
origem identifica o financiamento da compra; não cria uma transferência de
ativos entre custodiantes. Resgates permanecem em custódia até uma retirada
explícita para a Conta de Resultado.

O resultado passa a incluir posições e saldos de investimento, inclusive dinheiro
de vendas e dividendos ainda não reinvestido. A visão geral apresenta os saldos
por conta. A avaliação incorpora compras, vendas, resgates e estornos manuais;
ajustes de quantidade sem direção definida permanecem pendentes.

Correções preservam a origem dos recursos e estornos cancelam o aporte vinculado.
O histórico importado mantém suas classificações e seus aportes já registrados,
para não duplicar entradas inferindo um aporte em cada compra antiga.
