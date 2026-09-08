# Cotações e séries de mercado

A página /fin2/cotacoes/ possui as abas Cobertura completa e Capturas externas.
A cobertura mostra ativo, mecanismo, último preço/data e validação. A busca usa
nome, ticker, código ou CNPJ e o filtro oferece BRAPI e NENHUM.

## Camadas

O Fin2 mantém separadamente o snapshot do Fin1, as capturas externas, o último
fechamento aceito, o histórico diário e as referências oficiais. Correções de
ticker, provedor e multiplicador são auditadas sem alterar o registro importado.
Respostas externas guardam bytes, SHA-256, horário, moeda, preço, data e validação.

## Atualização brapi

O botão consulta ativos BRAPI um por vez. Consulta bem-sucedida no dia impede
nova chamada; há intervalo de cinco segundos. A resposta atualiza o fechamento e
pode preencher lacunas dos três meses recentes, sem sobrescrever pontos existentes.

Cada resultado aparece na barra. Cancelar interrompe novas consultas e ainda
processa a resposta em curso. Ticker incompatível passa para NENHUM. Consulte
[atualização de preços](price-updates.md).

## Histórico e pendências

CDI, Selic, IPCA, dólar e euro vêm do SGS/BCB desde 01/01/2000. O histórico
antigo dos ativos vem dos arquivos anuais COTAHIST da B3, importados com
preservação do ZIP e validação do layout oficial. O Ibovespa usa os arquivos
anuais oficiais da B3 desde 03/01/2000; a série descontinuada do SGS permanece
como evidência, mas a B3 prevalece nas datas coincidentes. O Fin2 não interpola dados
nem cria valores sintéticos.

Não há agendamento automático de escritores. A [decisão de agendamento](price-updates.md#decisão-de-agendamento)
mantém a brapi sob comando manual no processo web e reserva BCB/B3 para janelas
explícitas de manutenção, evitando concorrência entre processos no DuckDB.
