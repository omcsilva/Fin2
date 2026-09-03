# Série histórica de fechamentos

A migração `0013_daily_close_history.sql` cria `market.daily_close`, com uma linha
por ativo, provedor e data de pregão. A série guarda moeda, fechamento,
fechamento ajustado, captura de origem e instante de captura. Não são criadas
linhas para fins de semana ou feriados.

O importador usa o endpoint oficial `GET /api/v2/stocks/historical`, sempre com
intervalo diário. Para cada ativo, `startDate` é a data da primeira compra com
quantidade positiva e liquidação confirmada no Fin1. Ele não converte cotações instantâneas em fechamento. A resposta
bruta é preservada em `market.history_capture` com SHA-256; pontos repetidos para
o mesmo pregão são atualizados somente por uma captura posterior.

`market.daily_close_series` acrescenta ticker e nome do ativo para consultas de
gráficos. Para comparações de retorno deve-se preferir `adjusted_close`; para
gráficos do preço efetivamente fechado usa-se `close`.

## Carga

```powershell
$env:BRAPI_TOKEN = "TOKEN_PRIVADO"
.\.venv\Scripts\python.exe -m scripts.update_price_history `
  --database C:\Users\mcsil\Fin2-private\development\fin2.duckdb `
  --batch ID_DO_LOTE
```

O token é lido apenas do ambiente e enviado no cabeçalho Authorization. O
comando consulta cada ticker com sua data inicial própria, valida ticker, moeda e provedor e
grava cada resposta e seus pontos na mesma transação. Para manutenção diária,
a mesma política pode ser repetida: a chave única impede duplicação e preenche
eventuais pregões ausentes.

## Índices de comparação

`market.benchmark_catalog` mapeia os seis índices legados: CDI (`cdi`), dólar
(`USD-BRL`), euro (`EUR-BRL`), Ibovespa (`^BVSP`), inflação (`ipca`) e Selic
(`selic`). Todos são solicitados desde `2000-01-01`. As respostas brutas ficam em
`market.benchmark_capture` e os valores em `market.benchmark_value`.

O comando `python -m scripts.update_benchmark_history` usa os endpoints adequados
de ações, câmbio e macroeconomia. A view `market.comparison_series` reúne ativos e
índices para os futuros gráficos, preservando unidade e frequência; IPCA não é
artificialmente convertido de mensal para diário.

O `.env` da raiz é carregado sem sobrescrever variáveis do processo e permanece
ignorado pelo Git. Na carga inicial de 02/09/2026, o plano associado ao token
permitiu quatro ativos: 9.191 fechamentos foram gravados desde 21/06/2016. Os
demais tickers foram recusados pelo provedor.

As três famílias de índices não foram gravadas: macroeconomia e câmbio receberam
HTTP 403, e `^BVSP` recebeu HTTP 400 no endpoint v2. Essas recusas não geraram
pontos parciais ou sintéticos. Para completar as séries, será necessário ampliar
o plano da brapi ou configurar fontes oficiais alternativas para BCB/B3.

## Fontes oficiais

A migração `0015_bcb_benchmarks.sql` e o adaptador `bcb_history.py` substituem a
brapi nos benchmarks. O SGS do Banco Central fornece CDI (12), Selic (11), IPCA
(433), USD/BRL (1), EUR/BRL (21619) e a série histórica 7 do Ibovespa. As
consultas são divididas em janelas de até nove anos e mantêm cada resposta bruta.

Foram carregadas desde 01/01/2000: 6.698 observações de CDI, 6.698 de Selic,
319 de IPCA, 6.699 de dólar e 6.695 de euro. A série SGS 7 do Ibovespa devolveu
apenas 432 observações entre 02/01/2018 e 30/09/2019; ela está descontinuada e
permanece marcada como incompleta. O restante do Ibovespa deverá vir dos arquivos
históricos oficiais da B3, sem preenchimento por interpolação.
