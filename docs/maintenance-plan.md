# Backup, retenção e manutenção

Estado atualizado em 05/09/2026.

## Backup ativo

fin2-backup.timer executa diariamente às 03:00 em America/Sao_Paulo. O serviço
usa o lock da implantação, para o Fin2, cria e verifica o snapshot em
/var/backups/fin2/ e reinicia a aplicação antes da etapa de rede.

A exportação externa está habilitada. O snapshot é cifrado com chave pública
GPG, enviado por SSH ao rpi5 e publicado após confirmação do SHA-256. A chave
privada não fica no container nem no NAS. A pasta
//rpi5.lan/mergerfs/Backup/Fin2 já participa do backup do usuário no Backblaze;
o Fin2 não administra nem comprova essa etapa posterior.

## Restauração e retenção

A restauração deve ocorrer primeiro em diretório novo, com verificação do
manifesto, hashes, banco, documentos e imagens. Uma restauração isolada já foi
testada; o teste deve ser repetido periodicamente com uma cópia externa.

A retenção automática roda diariamente às 03:30 em America/Sao_Paulo, depois
do backup. Ela preserva os 7 backups regulares mais recentes, os 3 snapshots
pré-atualização mais recentes, a referência mais recente validada por restauração
e as releases ativa e anterior. Somente itens fora dessas janelas, íntegros e com
hash externo novamente confirmado podem ser removidos.

retention_plan.py calcula o estado e apply_retention.py recusa planos que tenham
mudado entre a inspeção e a execução. Itens incompletos, desconhecidos ou sem
confirmação externa permanecem para inspeção.

## HTTPS e pendências

O acesso ativo é <https://django.lmnet.dpdns.org/fin2/> pelo proxy no t1docker.
Gunicorn continua restrito a 127.0.0.1:8020 no t1django.

Faltam monitorar espaço e duração, testar periodicamente a cópia externa e
medir recursos durante importações e atualizações.
