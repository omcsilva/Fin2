# Fin2

Fin2 é um dashboard de investimentos mono-usuário e multi-carteiras construído
com Django e DuckDB. Ele substituiu o Fin1, que foi congelado e permanece apenas
como fonte histórica de conferência.

## Estado atual

O Fin2 está em produção no container t1django.lan, com escrita habilitada. A
base DuckDB reúne o acervo importado, documentos, cadastros, ledger auditável,
preços, séries históricas e metadados das integrações.

Estão implementados: migração final e rastreável do Fin1; preservação dos
documentos e imagens; seletores de carteira e ano; posições, caixa, alocação,
desempenho, rendimentos e fluxos; lançamentos, transferências e correções
compensatórias; importação CSV/XLSX; cadastros auditáveis; histórico de mercado;
e atualização assíncrona de preços pela brapi.

Dados financeiros, documentos, banco DuckDB e segredos ficam fora do Git.

## Arquitetura

- Django 5.2, templates HTML, CSS e JavaScript local.
- DuckDB pelo cliente oficial Python, sem ORM para os dados financeiros.
- Sem autenticação, admin, sessões, Celery, Redis ou servidor SQL separado.
- CSRF ativo em todas as operações de escrita.
- Um processo Gunicorn com quatro threads.
- Nginx serve /fin2/; o proxy da rede fornece HTTPS.
- Interface em Geist, com tabelas claras e rolagem horizontal.

## Estrutura

~~~text
config/                 Configuração, rotas e WSGI
fin2/dashboard/         Views e apresentação
fin2/portfolio/         Ledger, cadastros, preços e cálculos
fin2/imports/           Importadores e proveniência
warehouse/migrations/   Migrações SQL versionadas
templates/              Templates Django
static/                 CSS, JavaScript, fontes e imagens
tests/                  Testes sintéticos
deploy/                 systemd, Nginx, backup e atualização
docs/                   Projeto, operação e decisões
~~~

## Documentação principal

- [Roteiro e pendências](docs/roadmap.md)
- [Interface](docs/dashboard.md)
- [Modo de escrita](docs/write-mode.md)
- [Atualização de preços](docs/price-updates.md)
- [Produção](docs/production.md)
- [Atualizações por Git](docs/git-deployment.md)
- [Backup e manutenção](docs/maintenance-plan.md)
- [Migração do Fin1](docs/fin1-migration.md)
- [Desenvolvimento](docs/development.md)

Produção: <https://django.lmnet.dpdns.org/fin2/>
