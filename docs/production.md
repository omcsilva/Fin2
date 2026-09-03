# Produção — t1django.lan

Implantação realizada em 03/09/2026, Debian 12, 2 GB RAM, IP 10.0.0.17.
URL: http://t1django.lan/fin2/ . Escrita habilitada, DEBUG desligado.

Gunicorn 26.2.0 usa um worker e quatro threads, escutando somente em
127.0.0.1:8020. Nginx serve `/fin2/` sem remover o prefixo e permite apenas
127.0.0.1 e 10.0.0.0/24. HTTP ainda não é criptografado: HTTPS permanece pendente.
Apache, seu cache e MariaDB estão parados e desabilitados, sem remoção dos dados.

- Aplicação: `/opt/fin2`; ambiente Python: `/opt/fin2/.venv`.
- Dados ativos: `/var/lib/fin2/fin2.duckdb`, `documents/`, `catalog-images/`.
- Segredos: `/etc/fin2/fin2.env`, modo 600, excluído do etckeeper.
- Serviços: `fin2.service`, `nginx.service`, `fin2-backup.timer`.
- OCR Tesseract e idioma português instalados.

O computador de desenvolvimento não deve continuar recebendo lançamentos;
a base produtiva passa a ser a referência para novas operações.

## Operação

Use `sudo systemctl status fin2`, `sudo journalctl -u fin2 -n 50`, e
`sudo systemctl restart fin2`. Não use reload ou aumente o número de workers:
o DuckDB precisa de um único processo proprietário. Pare o serviço antes de
migrações ou acesso ao banco por ferramentas externas.

## Backup e restauração

Backup diário às 03:00 America/Sao_Paulo, em `/var/backups/fin2/`.
Execução manual: `sudo systemctl start fin2-backup.service`.
O serviço para o Fin2, copia os dados, verifica SHA-256, inclui configuração
protegida e reinicia o Fin2 se estava ativo. Há breve indisponibilidade.

Para restaurar, utilize como root:
`/opt/fin2/.venv/bin/python /opt/fin2/scripts/fin2_backup.py restore CAMINHO_BACKUP DESTINO_NOVO`.
O destino não pode existir. Faça primeiro uma restauração isolada; para promover
uma restauração, pare o serviço, preserve a base anterior e ajuste a propriedade
dos arquivos para fin2:fin2 antes de reiniciar. Confira também `config.sha256`
antes de recuperar o arquivo de configuração. Nunca imprima os segredos.

Validação executada: páginas principais e CSS responderam HTTP 200; primeiro
backup concluído; restauração isolada em `/var/backups/fin2-restore-check`
verificada por hashes e abertura do DuckDB (5.654 registros de origem e 298
documentos). Nenhum lançamento foi criado para testar produção.

Pendências: HTTPS, retenção de backups e cópia criptografada fora do container,
teste de carga/ciclo operacional completo. Backups não são apagados automaticamente;
monitorar espaço livre (aproximadamente 4,9 GB após a instalação e os testes).
