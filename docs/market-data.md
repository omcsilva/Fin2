# Identificadores e observações de preços

O inventário somente leitura está em `/fin2/cotacoes/`, com busca por nome,
abreviação, código ou CNPJ, filtro de integração legada e paginação. Os links
levam aos registros originais, preservando a navegação existente aos documentos.
O cabeçalho e sua textura permanecem inalterados.

## Escopo implementado

A migração `0005_market_inventory.sql` acrescenta três projeções:

- `market.asset_catalog`: ativo, moeda original, código, CNPJ, data original,
  integração e multiplicador configurados no Fin1, com referências de origem.
- `market.identifier_candidate`: valores originais não vazios dos campos
  `abrev`, `codigo` e `cnpj`. Todos permanecem `unverified`. Repetições são
  contadas por lote e campo após remoção de espaços nas extremidades, sem
  alterar o valor original. Isso não valida ticker, CNPJ ou identidade e não
  detecta todas as equivalências de formatação.
- `market.price_observation`: uma observação por cadastro de ativo em cada
  snapshot, inclusive preços ausentes ou inválidos. Identidade e proveniência
  são o registro de origem; fonte é `fin1_snapshot`. A captura corresponde à
  importação, não a uma consulta de mercado. O plugin configurado não comprova
  a fonte efetiva do preço. Datas futuras, ausentes e preços não positivos
  ficam sinalizados; idade é relativa ao corte do lote.

Reimportar o mesmo snapshot não duplica observações. Um snapshot diferente
preserva as observações anteriores em seu lote; escolher outro lote permite
consultá-las. Não há unificação automática de ativos entre lotes nem histórico
diário: o cadastro do Fin1 fornece apenas seu último preço salvo.

Não são aplicados multiplicadores nem conversão cambial. As moedas legadas
`REAL`, `DOL` e `EUR` não são renomeadas para códigos ISO. As projeções de
valorização e alocação existentes continuam inalteradas.

## Validação na cópia de desenvolvimento — 31/08/2026

- 156 ativos e observações, 217 identificadores candidatos, nenhuma repetição
  pelo critério limitado acima.
- 56 preços positivos antigos e 100 preços não positivos no inventário completo,
  que inclui ativos encerrados; esses números não são contagens de aplicações.
- 5.654 registros, 298 documentos e 729 vínculos preservados. Todas as linhas
  da valorização comparadas antes/depois permaneceram iguais.
- Backup privado `fin2-before-market.duckdb` e relatório privado
  `market-preparation.json`, fora do repositório.
- Testes cobrem repetição de importação, preservação entre snapshots, códigos
  com zeros à esquerda, duplicidade, fonte, moeda e ausência de multiplicação.

## Adaptador externo implementado

O [primeiro adaptador brapi](brapi.md) permite captura pontual offline com
validação e resposta original preservada, exibida separadamente no dashboard.
O inventário legado descrito acima permanece inalterado.

A migração `0025_asset_provider_overrides.sql` permite registrar mapeamentos
revisados sem alterar o cadastro importado. `market.asset_catalog_effective`
aplica o provedor, ticker e multiplicador decididos sobre o inventário legado e
mantém a justificativa. O INRD11 foi o primeiro caso: ticker e ISIN
`BRINRDCTF002` foram conferidos nos registros da B3, e uma captura brapi atual
foi aceita. A brapi recusou o endpoint histórico para esse ticker; portanto,
nenhuma série diária parcial ou sintética foi criada.

## Escopo restante

Continuar validando o mapeamento ativo/provedor e a unidade de cada cotação.
O Brasilprev Ciclo de Vida 2030 I ainda exige identificação inequívoca do fundo
e extrato do plano antes de receber preço. Não usar `fin1_tipo` como taxonomia de ativos: esse
cadastro descreve modalidades de remuneração. Cotações externas deverão ter
resposta original preservada, data efetiva, moeda e identidade verificadas,
deduplicação e armazenamento separado das observações legadas. Câmbio,
agendamento e uso de preços novos na alocação não foram ativados.
