# Atualizações por Git

O remoto `origin` aponta para o repositório bare privado
`mcsil@t1django.lan:/home/mcsil/fin2.git`. Não há GitHub nem publicação externa.
Push apenas transfere commits; não dispara implantação automática.

No desenvolvimento, revise `git status` e `git diff`, execute os testes e faça
commit dos arquivos desejados. `.env`, bancos, documentos e `tmp/` não devem ser
versionados. Depois:

```powershell
git push origin main
git rev-parse HEAD
ssh mcsil@t1django.lan "sudo /usr/local/sbin/update-fin2 COMMIT_COMPLETO"
```

Substitua COMMIT_COMPLETO pelo hash de 40 caracteres. A implantação cria uma
release isolada, instala dependências, verifica Django, coleta arquivos estáticos,
para o serviço, faz backup, aplica migrações e ativa o commit com um worker.
Não modifica os dados locais de desenvolvimento nem substitui a base produtiva.

Falhas após a parada deixam o serviço parado para recuperação explícita. Não
reverta apenas o código após uma migração: preserve o estado atual e restaure o
backup de banco compatível. Os snapshots pre-update incluem a configuração do
serviço anterior e os arquivos estáticos. A rotina não instala automaticamente
novos serviços, timers ou mudanças no proxy; revise essas alterações separadamente.

A instalação inicial foi copiada antes deste fluxo. A primeira versão completa
inclui a base funcional instalada e as ferramentas de implantação. As migrações
SQL preservam os bytes originais no Git, pois os checksums do banco dependem deles.
Nunca implante o commit antigo b96f850 sobre a base atual.
