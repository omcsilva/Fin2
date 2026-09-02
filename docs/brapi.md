# Primeiro adaptador externo: brapi v2

Implementado em `fin2/portfolio/brapi.py`, com o endpoint oficial
[stocks/quote](https://brapi.dev/docs/acoes/cotacao), consultado em 31/08/2026.
O Fin1 usa o campo `abrev` na função `atuBrAPI`; a inspeção foi somente leitura.

O comando exige um registro de ativo explícito e o ticker correspondente.
Aceita apenas abreviação exata e única no lote, plugin legado `atuBrAPI`,
moeda `REAL` ou `BRL` e multiplicador igual a 1. Isso confirma compatibilidade
com o cadastro legado, não uma identidade canônica ou equivalência econômica.
Renomes automáticos são recusados. Não há consulta em massa ou agendamento.

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
Redirecionamentos não são seguidos. Timeout de 20 segundos, limite de 1 MiB
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

Exige um único resultado, símbolos solicitado e retornado idênticos, `changed=false`,
moeda BRL, preço positivo finito que caiba exatamente em DECIMAL(28,10) e horário
com fuso não posterior à captura. Respostas HTTP bem-sucedidas mas incompatíveis
ficam `rejected`, sem preço utilizável; o comando termina com código 2.
Falhas de transporte, HTTP ou excesso de tamanho não gravam uma captura e
terminam com erro. Não existe ainda um diário persistente dessas falhas.

`accepted` significa validação técnica, não preço atual garantido. Cotações antigas
podem passar; data do provedor aparece no dashboard. Nenhuma captura substitui
dados do Fin1, alimenta a alocação ou altera o inventário de identificadores
não validados. Usar novos preços exige política posterior de data de referência,
frescor, revisão e associação canônica.

## Dashboard e verificação

`/fin2/cotacoes/` mostra as últimas 50 capturas do lote, separadas do inventário
legado e independentemente de seus filtros. Cada captura tem link ao cadastro
e download da resposta original, com conferência de hash, no-store e attachment.
O JSON nunca é renderizado como HTML. O cabeçalho permanece inalterado.

Uma consulta real de PETR4 foi aceita na cópia de desenvolvimento em 31/08/2026.
O backup privado é `fin2-before-brapi.duckdb`. Todas as linhas da valorização
foram comparadas antes/depois e permaneceram iguais. Os testes sintéticos
cobrem rejeições, deduplicação, preço decimal, mapeamento, multiplicador, HTTP
429, preservação do legado e download dos bytes originais.

Próxima etapa: ampliar a revisão dos mapeamentos e definir seleção de preços por
data/frescor antes de usar qualquer cotação externa na valorização.
