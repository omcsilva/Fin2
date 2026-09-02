# Análise inicial do Fin1

Inspeção realizada em 31/08/2026, via SSH, em `/home/mcsil/Fin1` no servidor informado pelo usuário. O código foi lido como texto; os bancos foram abertos com SQLite `mode=ro` e `query_only`. Não foram executados Django, importadores, recálculos ou migrações. Nenhum arquivo original foi alterado pelo procedimento de análise.

As contagens representam as consultas realizadas, não um backup consistente entre os três bancos e o diretório de anexos. Não foram copiados dados financeiros, credenciais ou documentos para este repositório. As referências de código abaixo são caminhos relativos à pasta remota inspecionada.

## Inventário observado

| Fonte | Conteúdo observado |
| --- | --- |
| `db.sqlite3` | Cadastros, lançamentos, movimentações e resultados materializados |
| `dados.sqlite3` | Tabela `fin1_dado`, atualmente vazia |
| `docs.sqlite3` | 21 registros HTML em `fin1_doc`; não contém os arquivos PDF |
| `ANEXOS/` | 298 arquivos, 260.323.600 bytes, distribuídos em nove subpastas |
| `config/__init__.py` | Configuração Django, roteamento dos bancos auxiliares e caminhos de mídia |
| `router.py` | Direciona `Doc` para `docs` e `Dado` para `dados` |
| `fin1/models.py` | Modelo de domínio e propriedades calculadas |
| `fin1/funcs.py` | Recálculos, associação de notas, migração do staging, importação/exportação genérica |
| `fin1/plugins_extratos.py` | Adaptadores Schwab, XP, B3 e Investing |
| `fin1/plugins_webscrap.py` | Código para Tesouro, BrAPI, CVM e MarketStack; disponibilidade externa não testada |
| `fin1/views.py`, `templates/`, `tables.py` | Interface Django, HTMX, tabelas e visualização de documentos |

Não foram encontradas instruções `AGENTS.md` na árvore inspecionada. Arquivos `.env`, logs financeiros e conteúdos dos documentos não foram lidos. A configuração efetiva do serviço em execução não foi auditada; o inventário refere-se aos arquivos presentes nessa pasta.

## Dimensão do domínio

| Entidade | Registros |
| --- | ---: |
| Titulares | 3 |
| Instituições | 10 |
| Contas | 16 |
| Carteiras | 7 |
| Ativos | 156 |
| Aplicações | 260 |
| Vínculos aplicação/carteira | 260 |
| Lançamentos de caixa | 2.428 |
| Movimentações de investimentos | 2.379 |
| Operações | 19 |
| Expressões de identificação | 34 |
| Classes / tipos / produtos / setores / índices / moedas | 6 / 4 / 13 / 13 / 6 / 3 |
| Configurações de web scraping | 15 |
| Staging de importação | 0 |

**Um usuário da aplicação não significa um único titular financeiro.** Os três titulares e as sete carteiras devem permanecer distintos no Fin2, mesmo sem autenticação.

`Aplicacao` representa um ativo em uma conta, com classificação em carteiras. Existem quatro grupos com mais de uma aplicação para o mesmo par conta/ativo. Não criar uma restrição de unicidade nesse par nem fundir aplicações automaticamente. A relação com carteiras é muitos-para-muitos no modelo, embora nenhum grupo observado tenha múltiplas carteiras.

## Documentos: comportamento confirmado

1. `Lancamento.nota_sinacor` e `nota_corretora` guardam nomes de arquivos.
2. O caminho é construído com `MEDIA_ROOT / Conta.abrev / nome_do_arquivo`.
3. `atuNotas`, em `fin1/funcs.py:664`, procura arquivos por conta e associa o prefixo anterior ao primeiro `_` ao número da nota. Arquivos com `B3_` alimentam o campo SINACOR; os demais, o campo da corretora.
4. `fin1/templates/obj_lancamento.html:33` mostra PDFs embutidos em abas B3 e corretora.
5. `NotaColumn`, em `fin1/tables.py:58`, permite abrir documentos a partir de lançamentos e movimentações. A movimentação herda o documento através do lançamento.
6. `Ativo.pdf` guarda outros PDFs associados ao ativo. O template usa uma construção de URL distinta da dos lançamentos; a existência em disco foi confirmada, mas o funcionamento dessas URLs no navegador não foi testado.
7. `Doc.item` identifica anotações HTML por URL da interface. Essas anotações devem ser migradas separadamente dos arquivos, remapeando as referências do Fin1 para o Fin2.

### Conferência dos arquivos

| Verificação | Resultado |
| --- | ---: |
| Referências SINACOR | 42; todas existentes |
| Referências de corretora | 222; todas existentes |
| Arquivos distintos cobertos por esses dois campos | 232 |
| Referências `Ativo.pdf` | 3; todas encontradas em `ANEXOS` |
| Arquivos fora dos dois campos de notas | 66 |
| Grupos de conteúdo idêntico por SHA-256 | 12, com 12 cópias adicionais |

Os 66 arquivos não são necessariamente órfãos: essa contagem exclui apenas os vínculos dos dois campos de notas, não os PDFs de ativos, links HTML ou associações externas. Não apagar ou deduplicar esses arquivos automaticamente.

O diretório contém 268 PDFs, 11 JPGs, 13 PNGs, quatro ZIPs, um TXT e um arquivo `.db`. Não foram abertos os ZIPs nem identificado o conteúdo do `.db`; não se deve presumir que seja outro banco financeiro. As 21 anotações HTML contêm oito atributos de link/imagem, ainda sem resolução individual.

### Limite da preservação encontrada

Nos fluxos de upload examinados, CSV/XLSX são entregues diretamente aos parsers e o nome pode ser registrado em `obs`; não foi encontrado arquivamento universal dos bytes originais. A importação de posição XP grava um relatório derivado em `posicao.txt`, sobrescrito na próxima execução, não o XLSX original.

Isso não descarta armazenamento manual ou em outros diretórios. O requisito informado pelo usuário continua válido: no Fin2, **todo arquivo importado deve ser preservado e vinculado**, inclusive quando o fluxo legado não possui essa rastreabilidade estruturada. Arquivos históricos ausentes não podem ser reconstruídos apenas a partir do nome em `obs`.

## Lançamentos e movimentações

O caixa e os investimentos têm representações relacionadas, mas não equivalentes:

- 470 movimentações não possuem lançamento vinculado.
- 747 lançamentos não possuem movimentações vinculadas.
- 93 lançamentos possuem mais de uma movimentação.
- Duas movimentações estão ligadas a lançamentos cuja conta difere da conta da aplicação.

Não somar as duas tabelas como eventos financeiros independentes. O modelo do Fin2 deve representar eventos e seus componentes de caixa/investimento, manter os IDs legados e preservar os vínculos documentais. Os casos sem vínculo podem ser legítimos; devem ser classificados antes da transformação.

## Importação e cálculo existentes

- Schwab CSV e XP XLSX alimentam `LancMovStage`; esses adaptadores limpam todo o staging antes de carregar outro arquivo (`plugins_extratos.py:71,119`). No Fin2, o staging deve pertencer a um lote.
- `migrarExtrato` usa expressões regulares e identificadores para gerar lançamentos e movimentações, depois elimina as linhas do staging (`funcs.py:713`). Preservar a linha original no Fin2.
- O `update_or_create` de lançamentos usa conta, data de liquidação e valor (`funcs.py:814`). Existem sete grupos com essa mesma chave no banco observado. Essa chave não é uma identidade segura para deduplicação.
- Os fluxos B3 de movimentação e posição incluem comparação com o banco; não equivalem todos a uma importação de novos eventos. O fluxo de eventos cria/atualiza movimentações previstas sem data de liquidação (`plugins_extratos.py:533`).
- `Operacao.multQuant` e `multValor` definem os sinais. As 19 operações abrangem compras, vendas, rendimentos, come-cotas, impostos, taxas, split, portabilidade, mudança de nome, estorno, resgate e bonificação, além de categorias ignoradas.
- `recalcularContaExtrato` normaliza sinais e regrava saldos (`funcs.py:480`).
- `recalcularAplicacao` altera quantidades, valores e, quando há lançamento, datas; grava acumulados e pode atualizar a cotação do ativo (`funcs.py:540`). A ordem usa apenas `dtliq`, sem desempate explícito.
- Movimentações sem liquidação são processadas depois de salvar os agregados da aplicação. Separar eventos previstos de liquidados explicitamente no Fin2.
- O preço médio e o campo `recebido` seguem algoritmos específicos do legado. Preservá-los como referência de reconciliação; não assumir que correspondam automaticamente ao custo fiscal ou a TWR/XIRR.
- A tabela histórica `Dado` está vazia. Cotações atuais e preços de operações não constituem uma série histórica completa; retornos históricos exigirão outras fontes.

## Exceções e integridade

`PRAGMA foreign_key_check` não apontou violações nos três bancos. `PRAGMA quick_check` retornou `ok` para `db.sqlite3`. Isso não valida as regras financeiras nem vínculos textuais.

| Ponto observado | Tratamento proposto |
| --- | --- |
| Quatro lançamentos sem conta | Preservar e sinalizar; não atribuir conta por suposição |
| Duas divergências de conta entre lançamento/movimentação | Revisar antes de herdar documento ou consolidar caixa |
| Seis movimentações sem liquidação | Distinguir previstas de realizadas |
| Uma movimentação com data posterior a 31/08/2026 | Revisar contexto; não corrigir automaticamente |
| Datas de movimentação/liquidação entre 2000-08-09 e 2027-03-07 | Confirmar datas de abertura e eventos futuros |
| Valores SQLite armazenados como INTEGER e REAL | Converter com política explícita de Decimal e arredondamento |
| Quatro grupos repetidos de conta/ativo | Preservar identidade das aplicações |
| Notas dependentes de abreviatura e nome do arquivo | Migrar para IDs de documentos com caminhos gerenciados |

Apesar de `DecimalField` no Django, 1.460 valores de movimentações usam armazenamento SQLite REAL e 919 INTEGER. A migração não deve alegar precisão decimal original recuperada: é necessário definir conversão e comparar com documentos e valores apresentados pelo legado.

## Mapeamento inicial para Fin2

| Fin1 | Destino/conceito proposto |
| --- | --- |
| `Titular` | `investor`, independente de autenticação |
| `Carteira`, `Aplicacao.carteira` | Carteiras e vínculos de classificação preservados |
| `Instituicao`, `Conta` | Instituições e contas |
| `Ativo`, `Classe`, `Tipo`, `Produto`, `Setor`, `Indice`, `Moeda` | Ativos e dimensões distintas; não colapsar classificações |
| `Aplicacao` | Identidade de posição/agrupamento legado por conta e ativo |
| `Lancamento`, `Movimentacao`, `Operacao` | Eventos e componentes relacionados, com regra explícita contra dupla contagem |
| Campos calculados | Valores legados de reconciliação, separados dos novos resultados |
| `nota_sinacor`, `nota_corretora`, `Ativo.pdf` | Documentos e vínculos tipados aos registros |
| `Doc` | Anotações HTML preservadas, com referências remapeadas e renderização segura |
| `ExpRegular`, identificadores, nomes de plugins | Configuração versionada de adaptadores |
| `Params` | Preferências locais sem usuário autenticado; não importar credenciais de autenticação |
| `Dado` | Série histórica somente se houver dados em outra fonte validada |

## Próximos passos

1. Preparar backup consistente dos três SQLite e dos anexos antes de qualquer migração, coordenando com o serviço existente.
2. Gerar inventário privado detalhado de documentos, IDs legados e exceções; não publicar caminhos pessoais no repositório.
3. Definir o esquema DuckDB a partir do mapeamento acima, incluindo titulares, carteiras, aplicações, anotações e documentos.
4. Construir importador somente de cópias, com lote, IDs estáveis, relatório de exceções e nenhuma correção silenciosa.
5. Implementar a primeira tela com posições e acesso aos documentos; reconciliar antes de habilitar alterações.

Esta etapa não executou a aplicação no navegador, não verificou APIs, não abriu conteúdos de PDFs, não reconciliou totais financeiros e não implementou a migração. Não é uma auditoria completa do Fin1.
