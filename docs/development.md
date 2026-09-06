# Desenvolvimento

O desenvolvimento oficial usa Debian no WSL2, aproximando o runtime local do
Debian de produção. O repositório fica em /home/mcsil/projects/Fin2.

## Execução

~~~bash
cd /home/mcsil/projects/Fin2
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 0.0.0.0:8020 --noreload
~~~

Acesse <http://127.0.0.1:8020/fin2/>. O ambiente local usa favicon-DEV.ico;
produção usa favicon-PRD.ico.

Na rede local, acesse <http://micro.lan:8020/fin2/>. Inclua `micro.lan` em
`FIN2_ALLOWED_HOSTS` no `.env` e mantenha o servidor em `0.0.0.0:8020`.

FIN2_DATA_DIR aponta para o diretório privado com fin2.duckdb, documents/ e
catalog-images/. O arquivo .env pode fornecer BRAPI_TOKEN e não é versionado.

## Regras

- Não criar SQLite nem executar migrações do ORM Django.
- Manter SQL parametrizado e escritas transacionais.
- Não abrir o mesmo DuckDB para escrita em processos independentes.
- Validar todo arquivo antes da confirmação da importação.
- Manter extratos, bancos, documentos, tokens e dados pessoais fora do Git.
- Não introduzir autenticação, Celery, Redis ou outro banco sem rever a arquitetura.

## Verificação

~~~bash
.venv/bin/python manage.py check
.venv/bin/python -m unittest discover -s tests -q
git diff --check
~~~

Mudanças visuais devem ser verificadas no navegador local. A promoção usa o
procedimento de [atualização por Git](git-deployment.md), que cria uma release,
faz backup, aplica migrações e ativa o commit exato.
