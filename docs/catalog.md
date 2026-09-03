# Cadastros editáveis

A camada `catalog.record` mantém os valores atuais dos cadastros criados ou
alterados no Fin2. `catalog.audit` guarda cada revisão, antes/depois e chave de
envio. Nenhuma gravação modifica `source_record` ou os documentos do Fin1.

As projeções de titulares, instituições, moedas, carteiras, contas, ativos,
aplicações e vínculos de carteira passam pela visão `catalog.effective_record`.
Os identificadores existentes são preservados. Novos identificadores numéricos
são alocados dentro do lote e tipo, acima do máximo existente.

As telas ficam em `/fin2/cadastros/`, no menu Dados e auditoria. Há listagem,
inclusão, edição, mensagens de validação, confirmação e histórico de revisões.
Referências são validadas no mesmo lote. Atualizações obsoletas são recusadas
por revisão e reenvios usam chave idempotente.

A moeda, o titular e demais vínculos estruturais de registros existentes não
podem ser trocados nesta primeira versão, para não reinterpretar o histórico.
Não há exclusão física. Nomes e campos descritivos podem ser corrigidos.

Ativos também oferecem ISIN, CNPJ, emissor, vencimento, indexador e taxa
contratada. São metadados cadastrais; não geram rendimentos, preços nem eventos
financeiros automaticamente. A validação de ISIN/CNPJ cobre formato, não
consulta externa nem dígitos verificadores.

Cadastros novos de contas e aplicações começam vazios. Saldos e posições
financeiras são formados pelos lançamentos, nunca digitados nesta tela.
# Imagens herdadas do Fin1

Os cadastros exibem as fotos e logotipos referenciados no campo `imagem`, com proporções preservadas nas miniaturas e na edição. Cópias locais ficam em `FIN2_DATA_DIR/catalog-images`, fora do repositório, inclusive para os logotipos originalmente externos. Inclua essa pasta nos backups e na transferência para produção.

O utilitário `scripts/import_catalog_images.py` recebe `--snapshot` (SQLite congelado), `--destination` e `--host`. Ele lê o Fin1 sem modificá-lo, valida formatos e tamanho e grava um manifesto por referência com hashes SHA-256. A rota privada verifica o hash e aplica CSP restritiva, inclusive para SVG. O navegador não consulta os sites externos.

Na carga inicial, 64 de 65 referências foram recuperadas. `conta_bancaria.png` não foi encontrado na origem; registros sem arquivo disponível permanecem sem miniatura. Os vínculos e dados financeiros não foram alterados.
