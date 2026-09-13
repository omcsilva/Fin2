# Importação inicial Fin1 → DuckDB

## O que está implementado

Esta etapa cria uma camada de ingestão e auditoria. **Ainda não é o ledger financeiro normalizado nem um dashboard funcional.** Não altera sinais, datas, saldos ou relações do Fin1 e não calcula rentabilidade ou impostos.

- Migrações SQL versionadas, com checksum e execução transacional.
- Importação das tabelas `fin1_*` dos três SQLite verificados.
- Registro do banco, tabela, ID original, esquema das colunas e conteúdo de cada linha.
- Preservação dos textos HTML de `Doc`, sem renderizá-los nesta etapa.
- Cópia de todos os anexos para armazenamento próprio fora do repositório.
- Vínculos de documentos a lançamentos, ativos e movimentações (através do lançamento quando as contas coincidem).
- Relatório privado de exceções com IDs legados.
- Identificação do lote pelo conteúdo do manifesto; repetir a mesma origem não duplica registros.
- Rollback do lote em caso de falha e rejeição de arquivo com hash divergente.

## Modelo implementado

Execução verificada em 31/08/2026 na cópia privada: **5.654 registros, 298 documentos e 729 vínculos**, num único lote. Uma segunda execução retornou `reused: true` com as mesmas contagens. O relatório privado foi gravado em `$HOME/Fin2-private/development/import-report.json`.

Foram registradas 546 sinalizações: 470 movimentações sem caixa vinculado, 63 documentos não classificados, seis movimentações sem liquidação, quatro lançamentos sem conta, duas divergências de conta e uma movimentação futura. Um mesmo registro pode ter mais de uma sinalização. Os 63 documentos permanecem armazenados, não são descartados.

| Tabela | Responsabilidade |
| --- | --- |
| `schema_migration` | Versões SQL aplicadas e hashes |
| `import_batch` | Manifesto de origem, data de referência e momento da importação |
| `source_table` | Esquema SQLite original e contagem esperada |
| `source_record` | Identidade estável da origem e payload JSON do registro |
| `source_document` | Nome e caminho de origem, hash, tamanho e chave de armazenamento |
| `document_record_link` | Vínculos tipados, com chaves estrangeiras para documento e registro |
| `import_issue` | Exceções para revisão, sem correção automática |

O payload JSON conserva os valores lidos pelo cliente SQLite sem conversão para Decimal ou normalização de datas. Valores REAL continuam representações de ponto flutuante do legado; não há alegação de recuperar precisão decimal perdida. Os bancos originais permanecem no snapshot para auditoria. A camada financeira posterior deverá aplicar regras explícitas de conversão e reconciliação.

Somente tabelas `fin1_*` são importadas. Usuários, senhas, sessões e tabelas administrativas do Django não são transferidos; `Params` é preservado como registro legado e seu `user_id` não representa autenticação no Fin2.

## Execução local

> **Documento histórico.** Descreve a etapa de ingestão inicial do Fin1. A
> captura original foi feita em Windows/PowerShell; os comandos abaixo foram
> convertidos para o ambiente Linux/WSL atual. Django já está instalado e o
> projeto está em produção — ver [desenvolvimento](development.md) e
> [produção](production.md).

Dependência testada: DuckDB 1.5.5; ambiente local usado: Python 3.14.7. O código requer Python 3.11+ para a importação.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest tests.test_fin1_import -v
.venv/bin/python -m fin2.imports.fin1 --snapshot "$HOME/Fin2-private/snapshots/2026-08-31-initial/restored" --database "$HOME/Fin2-private/development/fin2.duckdb" --as-of 2026-08-31
.venv/bin/python -m fin2.imports.report --database "$HOME/Fin2-private/development/fin2.duckdb" --output "$HOME/Fin2-private/development/import-report.json"
```

O relatório exige um arquivo de saída novo. O importador exige um destino fora do repositório e fora do snapshot. O DuckDB é acompanhado por `documents/`, com caminhos baseados em SHA-256; manter ambos juntos. Arquivos de conteúdo igual compartilham bytes, mas cada caminho de origem preserva sua identidade documental.

## Exceções verificadas automaticamente

- Lançamento sem conta resolvida.
- Movimentação sem lançamento correspondente.
- Divergência de conta entre lançamento e aplicação.
- Movimentação sem liquidação ou com data futura em relação a `--as-of`.
- Referência documental ausente no inventário.
- Documento ainda não ligado pelos campos de notas/PDF de ativos.

Uma exceção não significa necessariamente dado incorreto. Casos sem classificação são preservados. Grupos repetidos de conta/ativo, chaves ambíguas de importação e links em anotações HTML ainda exigem revisão antes da normalização. Não inferir vínculos documentais através das duas divergências de conta conhecidas.

## Garantias e limites

O lote e suas linhas são confirmados numa transação. Arquivos são verificados antes de publicar vínculos. Como o filesystem não participa da transação DuckDB, uma falha pode deixar arquivos por hash sem vínculo; eles podem ser reutilizados numa nova tentativa e não são removidos automaticamente.

O comando destina-se a execução offline, em um único processo. Não executar enquanto outro serviço usa o DuckDB. A trava Python serializa somente operações do mesmo processo; não coordena serviços externos.

Snapshots diferentes criam lotes separados. Isso preserva revisões históricas, mas não faz merge de registros entre snapshots. Consultas futuras devem selecionar o lote desejado, nunca somar lotes como se fossem eventos independentes. A data de revisão de um lote existente não pode ser alterada silenciosamente.

Não há visualizador de documentos, normalização financeira, importação incremental entre snapshots, recuperação automática de falhas do filesystem ou migração de produção nesta etapa.

Referências de implementação: [cliente Python oficial](https://duckdb.org/docs/current/clients/python/overview) e [transações DuckDB](https://duckdb.org/docs/current/sql/statements/transactions).
