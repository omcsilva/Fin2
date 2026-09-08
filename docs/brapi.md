# Primeiro adaptador externo: brapi v2

Implementado em `fin2/portfolio/brapi.py`, usando o histórico diário da brapi
somente para selecionar o fechamento da data de pregão mais recente.
O Fin1 usa o campo `abrev` na função `atuBrAPI`; a inspeção foi somente leitura.

O comando exige um registro de ativo explícito e o ticker correspondente.
Aceita apenas abreviação exata e única no lote, plugin legado `atuBrAPI`,
moeda `REAL` ou `BRL` e multiplicador igual a 1. Isso confirma compatibilidade
com o cadastro legado, não uma identidade canônica ou equivalência econômica.
Renomes automáticos são recusados. Não há consulta em massa ou agendamento. A
atualização pelo dashboard consulta o último fechamento diário de um ativo por
chamada, espera um segundo entre chamadas e não repete, no mesmo dia, uma
consulta já concluída com sucesso.
Os demais pregões presentes na resposta de três meses completam apenas datas
ausentes; fechamentos já armazenados não são alterados.
Ao cancelar, nenhuma nova chamada é iniciada. A resposta de uma chamada já em
andamento ainda é processada, e o timeout dessa chamada é de cinco segundos.

## Uso offline

Pare o servidor Fin2 antes de executar com `--fetch` e faça backup do DuckDB.
Sem a opção `--fetch`, o comando apenas verifica o mapeamento em modo leitura.
Use o identificador do registro obtido no link do ativo no dashboard:

```powershell
.\.venv\Scripts\python.exe -m fin2.portfolio.brapi --database C:\Users\mcsil\Fin2-private\development\fin2.duckdb --record ID_DO_REGISTRO --symbol PETR4
.\.venv\Scripts\python.exe -m fin2.portfolio.brapi --database C:\Users\mcsil\Fin2-private\development\fin2.duckdb --record ID_DO_REGISTRO --symbol PETR4 --fetch
```

Quando necessário, forneça `BRAPI_TOKEN` pelo ambiente privado. Ele é enviado
somente em Authorization, não no URL, banco, relatório ou logs do adaptador.
Redirecionamentos não são seguidos. Timeout de 5 segundos, limite de 1 MiB
e erros HTTP explícitos, sem tentativas automáticas. Apenas o ticker é enviado:
não são enviados saldos, quantidades, documentos ou dados dos titulares.

## Evidência e validação

A migração 0006 cria `external_quote_capture` no schema principal para manter
a chave estrangeira ao registro de origem (DuckDB não permite FK entre schemas).
A view `market.quote_capture` oferece acesso às capturas.

Uma inserção atômica conserva bytes exatos, SHA-256, endpoint, ticker, captura,
status e interpretação. Respostas repetidas para o mesmo registro, provedor e
ticker são reutilizadas; o horário da primeira captura é preservado. Respostas
diferentes permanecem como evidências distintas, inclusive revisões de preço.

Exige um único resultado, símbolos solicitado e retornado idênticos,
`changed=false`, intervalo diário e fechamento positivo finito que caiba
exatamente em DECIMAL(28,10). O ponto com a data mais recente é selecionado e a
moeda BRL vem do mapeamento validado do ativo. Respostas HTTP bem-sucedidas mas incompatíveis
ficam `rejected`, sem preço utilizável; o comando termina com código 2.
Falhas de transporte, HTTP ou excesso de tamanho não gravam uma captura e
terminam com erro. Não existe ainda um diário persistente dessas falhas.

`accepted` significa validação técnica, não preço atual garantido. Fechamentos
antigos podem passar; a data do pregão e o horário da consulta aparecem no
dashboard. O preço aceito mais recente alimenta a alocação sem alterar o dado
original do Fin1 nem o inventário de identificadores não validados.

A migração 0037 registra cada sucesso em
`market.asset_price_query_success`. Isso permite suprimir outra chamada para o
mesmo ativo no mesmo dia e registra uma nova consulta mesmo quando a resposta
é idêntica à captura anterior.

## Dashboard e verificação

`/fin2/cotacoes/` mostra as últimas 50 capturas do lote e respeita o filtro de
carteira. Cada captura tem link ao cadastro
e download da resposta original, com conferência de hash, no-store e attachment.
O JSON nunca é renderizado como HTML. O cabeçalho permanece inalterado.

Uma consulta real de PETR4 confirmou o contrato do endpoint em 04/09/2026. Os
testes cobrem rejeições, deduplicação da evidência, diário de consultas, preço
decimal, mapeamento, multiplicador, HTTP 429, preservação do legado e download
dos bytes originais.
