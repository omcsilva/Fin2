# Produção — t1django.lan

Produção ativa em Debian 12, container Proxmox com 2 GB de RAM.

- LAN: <http://t1django.lan/fin2/>
- HTTPS: <https://django.lmnet.dpdns.org/fin2/>
- Fin1 congelado: <https://django.lmnet.dpdns.org/fin1/>

O proxy HTTPS está no t1docker; o origin permanece no t1django. A aplicação não
possui login próprio e deve continuar protegida pela infraestrutura de rede.

## Serviços e caminhos

- revisão ativa: /var/lib/fin2/deployed-revision;
- dados: /var/lib/fin2/fin2.duckdb, documents/ e catalog-images/;
- configuração: /etc/fin2/fin2.env;
- aplicação: fin2.service, um Gunicorn com quatro threads;
- arquivo legado: fin1.service em 127.0.0.1:8010, com SQLite e anexos somente leitura;
- proxy local: nginx.service, /fin2/ para 127.0.0.1:8020;
- backup: fin2-backup.timer;
- retenção: fin2-retention.timer, diariamente após o backup;
- Git privado: /home/mcsil/fin2.git.

Apache e MariaDB estão parados e desabilitados. Não aumente workers: um único
processo deve possuir o DuckDB.

O menu Histórico do Fin2 aponta para as páginas nativas do Fin1. O Fin1 usa a
captura final verificada de 02/09/2026 em `/var/lib/fin1`, abre os três bancos
SQLite com `mode=ro` e bloqueia métodos e rotas de alteração. O código está em
`/opt/fin1`; o Nginx publica `/fin1/`, `/fin1/static/` e `/fin1/anexos/` sob a
mesma restrição de rede do Fin2. Código, configuração do serviço, proxy e rotina
de atualização pertencem ao repositório Git separado `Fin1`.

## Operação

~~~bash
sudo systemctl status fin2
sudo journalctl -u fin2 -n 50
sudo systemctl restart fin2
sudo cat /var/lib/fin2/deployed-revision
~~~

Pare o serviço antes de abrir o banco para escrita externa. Atualizações normais
usam [o fluxo Git](git-deployment.md).

## Backup

O backup diário roda às 03:00 em America/Sao_Paulo e cria snapshots em
/var/backups/fin2/. Ele verifica banco, documentos, imagens e configuração.
A exportação externa está habilitada: cifra com chave pública, envia ao rpi5 e
confirma SHA-256. O destino //rpi5.lan/mergerfs/Backup/Fin2 já participa do
backup do usuário no Backblaze; o Fin2 não administra essa etapa posterior.

## Estado verificado em 05/09/2026

- revisão bb25278916f5946ded791b7fb2777ce71a6c05e6 ativa;
- aplicação e timer de backup ativos;
- acesso local e HTTPS respondendo HTTP 200;
- escrita, migrações e exportação externa habilitadas;
- restauração isolada previamente verificada.

A retenção mantém 7 backups regulares, 3 pré-atualização, a referência validada
e as duas releases necessárias para recuperação. Faltam medição de recursos e
testes periódicos da restauração externa.
