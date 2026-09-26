# Testes

Os testes ficam separados por domínio em `test_*.py`. Execute o menor escopo que
cobre a alteração e rode a suíte completa antes de integrar.

Um caso específico:

~~~bash
.venv/bin/python -m unittest tests.test_xp_statement.XPFlowTests.test_brokerage_review_shows_preledger_events_not_statement_line -q
~~~

Um módulo ou conjunto relacionado:

~~~bash
.venv/bin/python -m unittest tests.test_xp_statement tests.test_clear_brokerage -q
~~~

Buscar casos pelo nome, sem executar os demais:

~~~bash
.venv/bin/python -m unittest discover -s tests -k brokerage -q
~~~

Suíte completa:

~~~bash
.venv/bin/python -m unittest discover -s tests -q
~~~

`test_fin1_import.py` cobre reimportação, vínculos, preservação de payload,
rejeição de corrupção, rollback e checksums de migração com snapshots sintéticos.
`test_dashboard.py` cobre rotas, HTML escapado, downloads, recursos inválidos,
ausência de banco, CSRF e integridade de documentos. Mantenha dados reais do
Fin1 fora do checkout.
