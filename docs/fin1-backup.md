# Cópia de trabalho do Fin1 — 31/08/2026

## Captura final congelada — 02/09/2026

O usuário confirmou que o Fin1 não recebe mais escritas. Uma nova captura foi
gerada em `C:\Users\mcsil\Fin2-private\snapshots\2026-09-02-final`, fora do
repositório. Os três bancos passaram novamente por `integrity_check`, verificação
de chaves estrangeiras e contagens; 301 arquivos foram verificados. SHA-256 do
TAR final:

```text
eb30810a4f007e396ffd500a0eaea70b42d38da768e5e13143e2714d624330bf
```

Os hashes e tamanhos de todos os bancos e anexos são idênticos aos da captura
de 31/08. A diferença entre os TARs decorre dos metadados da nova captura, não
dos dados financeiros. A importação final reconheceu o mesmo lote de conteúdo
`f3dce6df…` e retornou `reused: true`, validando novamente os 5.654 registros,
298 documentos e 729 vínculos sem criar duplicatas. A data de referência do
lote permanece 31/08/2026; ela não foi alterada silenciosamente apenas porque
a confirmação final ocorreu em 02/09.

Foi criado o backup privado `fin2-before-final-import.duckdb` antes da validação.
O relatório privado `final-migration-reconciliation-2026-09-02.json` registra
as contagens e divergências remanescentes.

## Resultado

Cópia recebida e restaurada com sucesso em:

```text
C:\Users\mcsil\Fin2-private\snapshots\2026-08-31-initial\
  snapshot.tar
  verification.json
  restored\
    manifest.json
    db.sqlite3
    dados.sqlite3
    docs.sqlite3
    ANEXOS\...
```

Os dados privados permanecem fora do repositório Fin2. O TAR tem 262.471.680 bytes e contém os três bancos, 298 anexos e o manifesto. Há 301 arquivos de dados verificados, além do manifesto.

SHA-256 do TAR:

```text
366532b4ea363c162ec1cec38e1e742a9bca2a3dbfa21c5757f034c61f70dbe3
```

## Fonte confirmada

O contêiner `django-docker`, com imagem `3010-django-fin1`, monta `/home/mcsil/dockhand/data/stacks/rpi5/3010-django/Fin1` em `/app`. O caminho do host resolve para `/home/mcsil/Fin1`. Caminhos resolvidos, dispositivos/inodes e hashes dos bancos e arquivos de código conferidos confirmaram que se trata da mesma árvore previamente analisada.

Os arquivos de serviço systemd existentes no projeto não representam o modo ativo de execução encontrado. Não foram modificados serviços nem contêineres.

## Verificação realizada

- Origem SQLite aberta com `mode=ro` e `query_only`.
- Cópia de cada banco pela API de backup SQLite.
- Hashes/metadados da origem sem mudanças detectadas durante a captura.
- SHA-256 e tamanho de todos os arquivos conferidos após a transferência.
- Restauração do TAR em diretório separado.
- `integrity_check` aprovado nos três bancos restaurados.
- Nenhuma violação de chave estrangeira nos três bancos restaurados.
- Contagens das tabelas `fin1_*` restauradas iguais às da cópia remota.

Não houve alteração dos dados originais pelo procedimento. A pasta temporária remota foi removida ao final. As tabelas e documentos não foram migrados para DuckDB.

## Consistência e próximo uso

A aplicação não foi parada. Cada banco foi copiado pela API SQLite e nenhuma mudança foi observada nos arquivos entre as verificações. Isso fornece uma base verificada para desenvolver e testar o importador, mas não é uma captura atômica coordenada dos três bancos e anexos.

A captura final acima encerra esta pendência. Ela continua não sendo um backup
completo da implantação: não inclui código, ambiente nem segredos.

Manter `snapshot.tar` preservado. O próximo passo é definir o esquema de destino e produzir um relatório de exceções usando os bancos locais somente leitura; qualquer teste de transformação deve usar outra cópia ou um DuckDB novo, fora do repositório.

Ferramentas e instruções: [scripts/README.md](../scripts/README.md).
