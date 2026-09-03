# Custo médio e ganhos realizados

O relatório reconstrói uma média móvel separada por aplicação, em ordem de data.
Compras aumentam quantidade e custo; vendas baixam o custo médio vigente e a
diferença para o valor da venda é exibida como ganho realizado no período.

O cálculo só aceita compras e vendas com quantidade e valor explícitos. A
quantidade final reconstruída deve coincidir com a posição canônica. Aplicações
com portabilidade, split, bonificação, venda sem posição suficiente ou dados
incompletos ficam listadas como excluídas.

O caixa líquido de uma nota com vários ativos é rateado proporcionalmente ao
valor bruto, com fechamento decimal exato. A parcela líquida aumenta o custo da
compra ou reduz o produto da venda. Operações sem caixa vinculado usam o valor
bruto e são contadas como “sem caixa”. Os números continuam sendo uma memória
preliminar e não constituem apuração fiscal sem conferência das regras aplicáveis.

## Prévia mensal

A prévia agrega vendas e resultados por mês, titular e grupo fiscal. Para ações
brasileiras em operações comuns, marca como potencialmente isento o ganho em
mês com vendas de até R$ 20.000. Para FII, aplica 20% sobre ganho positivo. Nos
demais ganhos tributáveis de ações, aplica 15%. Meses com compra e venda da mesma
aplicação no mesmo dia são sinalizados como possível day trade e não recebem
estimativa automática.

A prévia transporta prejuízos cronologicamente por titular, mantendo um saldo
para operações comuns (ações e ETFs) e outro para FII. Ganhos isentos com ações
não consomem o saldo de prejuízo; perdas em operações comuns continuam no
controle. Possíveis day trades são isolados e não alteram os saldos.

Lançamentos cuja descrição identifica IRRF sobre operações em bolsa são
agregados por titular e mês de liquidação. A tela os deduz como crédito candidato
e mostra um imposto líquido provisório. A data do extrato pode pertencer ao mês
seguinte ao pregão; créditos sem competência calculada correspondente ficam
listados separadamente. Não deve ser tratado como DARF sem essa conferência.

O cálculo depende da classificação correta dos ativos. Fontes oficiais consultadas em
03/09/2026:

- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/bolsa-de-valores-1/isencoes
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/bolsa-de-valores-1/calculo-e-pagamento-do-imposto
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/fundos-de-investimento-no-brasil
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/bolsa-de-valores-1/compensacoes
