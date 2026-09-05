# Interface do Fin2

O Fin2 usa Django, templates HTML, CSS e JavaScript local. Não há autenticação,
admin, sessões ou banco ORM. A interface consulta e grava o DuckDB por serviços
próprios, com CSRF e escrita serializada.

## Navegação

O cabeçalho possui seletores de Carteira e Ano. O lote final do Fin1 permanece
interno, pois não haverá outros lotes. O menu agrupa Carteira, Movimentações e
Dados e auditoria.

As tabelas têm tema claro, alto contraste, pesquisa e ordenação. Mantêm linhas
sem quebra, largura natural e rolagem horizontal. O conteúdo ocupa toda a
largura entre as margens responsivas.

## Recursos

- visão geral, posições, caixa, alocação e histórico;
- desempenho, rendimentos, fluxos e estimativas fiscais;
- lançamentos, transferências e correções compensatórias;
- importação CSV/XLSX com pré-visualização;
- cadastros, conciliação e revisão;
- registros e documentos vinculados;
- cotações em abas Cobertura completa e Capturas externas.

Consulte [modo de escrita](write-mode.md) e
[atualização de preços](price-updates.md).

## Barra de status

O botão à direita inicia a atualização de preços e permite cancelá-la durante o
trabalho. Cada resultado aparece imediatamente. A última mensagem permanece
visível e pode ser copiada por clique, Enter ou Espaço.

A data global só avança quando todos os ativos BRAPI estão atualizados. Ativos
NENHUM ficam fora do ciclo. A cobertura pode ser filtrada por mecanismo.

## Segurança e configuração

Operações de escrita exigem POST e CSRF. Documentos são verificados por tamanho
e SHA-256 e visualizados em sandbox. HTML legado é escapado. Produção usa um
único processo proprietário do DuckDB.

Variáveis principais: FIN2_DATA_DIR, FIN2_DEBUG, FIN2_SECRET_KEY,
FIN2_ALLOWED_HOSTS, FIN2_CSRF_TRUSTED_ORIGINS e BRAPI_TOKEN. Rotas e arquivos
estáticos preservam o prefixo /fin2/.
