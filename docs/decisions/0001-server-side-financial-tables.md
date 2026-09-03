# ADR 0001 — Tabelas financeiras processadas no servidor

## Decisão

O Fin2 fará pesquisa, filtros, classificação, paginação e totais por consultas
parametrizadas no DuckDB. O navegador enviará apenas o estado dos controles e
apresentará o resultado. Colunas classificáveis serão vinculadas a uma lista
fechada de expressões SQL; nomes recebidos pela URL nunca serão interpolados.

## Contexto

O Fin1 combina django-tables2 com TableFilter. TableFilter classifica, filtra
e soma as linhas já presentes no HTML. Como o Fin2 pagina os conjuntos grandes
no servidor, aplicar a mesma operação no DOM produziria pesquisa e totais apenas
da página visível. django-tables2 também traria pouco benefício sem o ORM.

## Consequências

- totais representam todas as linhas filtradas, não somente a página atual;
- DuckDB executa operações de dados e o JavaScript permanece pequeno;
- paginação preserva pesquisa, filtros e ordem na URL;
- tabelas pequenas podem permanecer estáticas quando não houver operação útil;
- cada total deve ter significado financeiro explícito; quantidades de ativos
  distintos não serão somadas apenas porque compartilham uma coluna.
