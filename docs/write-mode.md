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

O dashboard expõe criação e reversão compensatória, sem edição destrutiva.
O comando de correção executa o estorno e o lançamento substituto em uma única
transação, preserva o evento original e replica seus vínculos documentais nos
dois eventos gerados. Repetições do formulário usam a mesma chave idempotente.
O formulário unificado aplica regras por operação: depósitos, vendas e
rendimentos e resgates usam valores positivos; retiradas, compras, taxas e impostos usam
valores negativos; compras, vendas e resgates exigem aplicação e quantidade positiva.
A moeda deve coincidir com a moeda da conta. A seleção de aplicações é filtrada
pela conta no navegador e novamente validada no serviço.

A migração `0027_manual_event_documents.sql` acrescenta o vínculo opcional entre
um evento novo e um documento já preservado. O documento deve pertencer ao
mesmo lote da conta, e o vínculo é confirmado na mesma transação do evento e do
registro de auditoria. O histórico mostra acesso direto ao comprovante.

O formulário também permite enviar um novo comprovante PDF, PNG, JPG ou WEBP de
até 10 MiB. O serviço confere a extensão e a assinatura do conteúdo, armazena o
arquivo pelo hash SHA-256, registra-o em `source_document` e cria o vínculo na
mesma transação do lançamento. Uma transferência vincula o mesmo comprovante
aos seus dois eventos. Não é permitido selecionar um documento existente e
enviar outro no mesmo lançamento.

A migração `0028_manual_transfers.sql` representa transferências por um cabeçalho
e dois eventos manuais vinculados: retirada na origem e depósito no destino. Os
dois lados, o vínculo documental opcional e a auditoria são confirmados na mesma
transação. A primeira versão exige contas distintas na mesma moeda. Um lado não
pode ser estornado isoladamente; o estorno da transferência cria atomicamente o
par inverso e impede repetição.

A migração `0029_write_idempotency.sql` adiciona uma chave única gerada no
formulário para lançamentos e transferências. Repetir exatamente o mesmo envio
retorna a operação já criada, em vez de gravar outra. Os formulários pedem
confirmação antes do POST, desabilitam o botão durante o envio e preservam os
campos e a mesma chave quando a validação falha. Erros de lançamento e de
transferência são apresentados na própria página. Falhas de reversão também
retornam à listagem com uma mensagem contextual, sem deixar o usuário em uma
resposta HTTP isolada.

Importações genéricas preservam o arquivo original, validam todas as linhas em
pré-visualização e somente confirmam o lote quando nenhuma linha possui erro.
Em produção, a escrita continuará serializada em um único processo.
