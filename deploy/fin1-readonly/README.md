# Fin1 somente leitura

O Fin1 congelado roda em `/fin1/`, separado do Fin2. A implantação usa o código
legado preservado e os dados da captura final verificada de 02/09/2026.

Barreiras de escrita:

- SQLite aberto com URI `mode=ro` nos três bancos;
- arquivos pertencem a `root` e o serviço não possui diretório gravável;
- systemd usa `ProtectSystem=strict` e demais restrições;
- middleware aceita apenas GET, HEAD e OPTIONS e bloqueia as rotas legadas de
  criação, edição, exclusão, importação, atualização, migração e recálculo;
- sessões usam cookies assinados e não gravam no banco congelado.

O Nginx entrega os arquivos estáticos e anexos diretamente. O serviço Gunicorn
escuta apenas em `127.0.0.1:8010`. A proteção de rede é a mesma aplicada ao
Fin2 no servidor `django.lmnet.dpdns.org`.
