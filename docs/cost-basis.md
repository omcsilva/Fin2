# Custo médio e ganhos realizados

O relatório reconstrói uma média móvel separada por aplicação, em ordem de data.
Compras aumentam quantidade e custo; vendas baixam o custo médio vigente e a
diferença para o valor da venda é exibida como ganho realizado no período.

O cálculo só aceita compras e vendas com quantidade e valor explícitos. A
quantidade final reconstruída deve coincidir com a posição canônica. Aplicações
com portabilidade, bonificação, venda sem posição suficiente ou dados incompletos
ficam listadas como excluídas. Um desdobramento com quantidade adicional
explícita e valor zero aumenta a quantidade e conserva o custo total; qualquer
outro formato de evento societário continua bloqueado.

O caixa líquido de uma nota com vários ativos é rateado proporcionalmente ao
valor bruto, com fechamento decimal exato. A parcela líquida aumenta o custo da
compra ou reduz o produto da venda. Operações sem caixa vinculado usam o valor
bruto e são contadas como “sem caixa”. Os números continuam sendo uma memória
preliminar e não constituem apuração fiscal sem conferência das regras aplicáveis.

## Prévia mensal

A prévia agrega vendas e resultados por mês, titular e grupo fiscal. Para ações
brasileiras em operações comuns, marca como potencialmente isento o ganho em
mês com vendas de até R$ 20.000. Para FII, aplica 20% sobre ganho positivo. Nos
demais ganhos tributáveis de ações, aplica 15%. A quantidade comprada e vendida
da mesma aplicação no mesmo pregão é separada como day trade, sem consumir o
estoque anterior. O resultado recebe alíquota de 20% e controle próprio de
prejuízos; eventual quantidade excedente permanece na modalidade comum.

A prévia transporta prejuízos cronologicamente por titular, mantendo um saldo
para operações comuns (ações e ETFs), outro para FII e outro para day trade.
Ganhos isentos com ações não consomem o saldo de prejuízo; perdas em operações
comuns continuam no controle.

Lançamentos cuja descrição identifica IRRF sobre operações em bolsa só são
deduzidos quando a competência pode ser obtida da operação relacionada ou do
único mês de negociação encontrado na nota de corretagem vinculada. A modalidade
day trade é identificada pela descrição do IRRF e não se mistura ao crédito de
operações comuns. Registros sem essa evidência ficam listados separadamente pela
data de liquidação e não reduzem a estimativa.

O cálculo depende da classificação correta dos ativos. Fontes oficiais consultadas em
06/09/2026:

- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/bolsa-de-valores-1/isencoes
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/bolsa-de-valores-1/calculo-e-pagamento-do-imposto
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/fundos-de-investimento-no-brasil
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/bolsa-de-valores-1/compensacoes
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/pagamento/renda-variavel/bolsa-de-valores-1/retencoes
- https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf/p-r-irpf-2026-v1-00-2026-04-23.pdf
