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
