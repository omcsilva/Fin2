# Cadastros financeiros e conferência de posições

Implementado em 31/08/2026 na migração `0002_portfolio_projections.sql`.

## Modelo desta etapa

O schema `portfolio` contém projeções SQL tipadas sobre os registros de origem. Elas não reescrevem o histórico e não constituem ainda um ledger editável. Cada aplicação conserva seu ID de origem, mesmo quando outra aplicação usa a mesma conta e ativo.

Cadastros disponíveis: titulares, instituições, moedas, carteiras, contas, ativos, classificações e vínculos aplicação/carteira. Operações, movimentações e lançamentos de caixa permanecem separados; não são somados como fatos independentes.

Na base atual: 3 titulares, 10 instituições, 3 moedas, 7 carteiras, 16 contas, 156 ativos e 260 aplicações, com 260 vínculos a carteiras. As projeções também cobrem as 19 operações, 2.379 movimentações e 2.428 lançamentos. Todas as consultas relacionam registros dentro do mesmo lote.

## Quantidades

- **Qtd. Fin1:** quantidade materializada preservada na aplicação legada.
- **Reconstruída:** soma de `abs(quantidade) × multQuant` das movimentações com data de liquidação preenchida, incluindo datas posteriores ao corte. É a comparação compatível com o conjunto liquidado usado pelo código legado inspecionado, não uma reconstrução histórica perfeita de execuções passadas.
- **No corte:** mesma soma, limitada à data de referência do lote.
- **Diferença:** reconstruída menos quantidade salva, sem tolerância implícita.

Movimentações sem liquidação não entram nas somas. Movimentações futuras são contadas e mostradas separadamente. Quantidade ou multiplicador ausente torna o resultado reconstruído indisponível, em vez de transformá-lo silenciosamente em zero. Aplicações sem movimentos são preservadas e sinalizadas na tela.

Quantidades usam `DECIMAL(28,10)`; valores monetários legados usam `DECIMAL(28,4)`. A conversão parte da representação JSON preservada do SQLite e não recupera precisão que o SQLite REAL já tenha perdido. Casts inválidos causam erro de validação, sem substituição silenciosa.

## Resultado da base atual

Das 260 aplicações, 255 coincidiram exatamente na comparação de quantidade reconstruída versus salva. Cinco diferiram. Nenhuma foi corrigida. O relatório privado detalhado está em:

```text
$HOME/Fin2-private/development/quantity-report.json
```

Isso **não valida saldos, custo médio, renda, impostos, preços ou rentabilidade**. Campos monetários e preços disponíveis nas projeções são referências legadas; não há total consolidado entre moedas nem conversão cambial nesta etapa.

## Interface

Acesse [Posições](http://127.0.0.1:8020/fin2/posicoes/). A tela tem filtros por conta e ativo, paginação, identificação do titular/moeda e links para a aplicação original. A navegação para documentos permanece no detalhe dos registros. O cabeçalho aprovado não foi alterado.

## Preparação offline

Pare o servidor antes de executar:

```bash
.venv/bin/python -m fin2.portfolio.prepare --database "$HOME/Fin2-private/development/fin2.duckdb" --report "$HOME/Fin2-private/development/NOVO-RELATORIO.json"
```

O relatório deve ser um arquivo novo. A preparação valida todas as colunas tipadas e aplica migrações versionadas. Existe uma cópia anterior à migração em `fin2-before-portfolio.duckdb`, no mesmo diretório privado; ela contém apenas a primeira versão do schema. Nenhuma alteração foi feita no Fin1.

Próximos passos: revisar as cinco diferenças com seus movimentos, reconciliar caixa e valores por moeda, definir regras de custo e tratamento dos eventos antes de construir o ledger de operações novas.
