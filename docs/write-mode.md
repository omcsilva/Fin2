# Modo de escrita

A migração `0011_writable_ledger.sql` cria a primeira superfície editável do
Fin2. Ela não altera nem mistura registros importados do Fin1.

`ledger.manual_event` recebe novos eventos manuais. Cada gravação exige uma conta
existente, tipo permitido, data de liquidação, moeda, valor `DECIMAL(28,4)` e
descrição. Quantidade é opcional e usa `DECIMAL(28,10)`. Quando uma aplicação é
informada, ela deve pertencer à conta selecionada.

`ledger.audit_log` registra a criação na mesma transação. O serviço
`fin2.portfolio.manual_ledger.create` usa o bloqueio de escrita compartilhado,
valida todas as referências antes do `BEGIN` e confirma evento e auditoria
atomicamente. Falhas executam rollback.

`ledger.all_event` reúne eventos preservados do Fin1 e eventos manuais, mantendo
a origem explícita. A base foi migrada com as tabelas vazias: nenhum lançamento
financeiro foi criado automaticamente.

Antes de expor a gravação no dashboard ainda serão implementados reversão (sem
edição destrutiva), vínculo de documentos e formulário com pré-visualização. Em
produção, a escrita continuará serializada em um único processo.
