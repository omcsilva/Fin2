# Reconciliação final Fin2 × Fin1

Conferência concluída em 06/09/2026, usando como data comum o fechamento
congelado do Fin1 em 31/08/2026. A página **Conciliação** recalcula estes
números diretamente do ledger e mantém BRL e USD separados.

## Resultado

| Dimensão | BRL | USD | Conclusão |
| --- | ---: | ---: | --- |
| Avaliação Fin1 | 3.684.649,8860340494 | 155.818,1301850000 | Valores cobertos |
| Avaliação Fin2 | 3.684.649,8860340494 | 155.818,1301850000 | Diferença zero |
| Rendimentos Fin1 | 435.234,3550 | 13.272,1800 | Fluxos classificados como rendimento |
| Rendimentos Fin2 | 435.234,3550 | 13.272,1800 | Diferença zero |

Os saldos de investimento também coincidem por conta, exceto a APEX Marcos
(Banco Inter). O Fin1 terminou com USD 12.666,49 nessa conta. O Fin2 terminou
com zero depois dos saques documentados de USD 10.000,00 e USD 2.666,49 em
16/04/2024. Portanto, a diferença de USD -12.666,49 é uma correção auditada,
e não uma divergência sem origem.

Os fluxos brutos em USD também incluem o aporte de USD 2.171,70 depois
estornado. Por isso, comparados ao Fin1, o Fin2 mostra USD +2.171,70 em aportes
e USD -14.838,19 em retiradas. O efeito líquido é USD -12.666,49 e coincide
com o ajuste da conta APEX.

## Cobertura na conferência original

Foram avaliadas 46 posições em BRL e 13 em USD. Duas posições BRL permanecem
fora do total por ausência de cotação válida: Brasilprev CICLO DE VIDA 2030 I
PGBL e INRD11. A interface listava ambas como avaliações pendentes e não presumia
valor zero. Com **Incluir zerados?** desmarcado, itens marcados como ZERADO e
seus valores deixam de aparecer, conforme a regra global dos relatórios.

Não foram encontradas diferenças de avaliação ou rendimento no conjunto com
cobertura. As diferenças de caixa e fluxo encontradas são integralmente
explicadas pelos lançamentos corretivos do Fin2.

## Estado atual em produção em 07/09/2026

O INRD11 deixou de ser uma pendência: a série aceita da brapi contém 61
fechamentos e fornece R$ 72,65 em 27/08/2026, último pregão disponível antes do
corte. Para 150 cotas, ele acrescenta R$ 10.897,50 à avaliação ativa em BRL.
A migração `0053_historical_prices_in_valuation.sql` passou a usar a série
diária aceita nas avaliações por data de corte. Antes dela, os fechamentos
estavam preservados, mas a avaliação consultava apenas o último preço e a
referência importada.

A comparação congelada acima preserva o resultado conferido em 06/09. No escopo
padrão atual, que exclui entidades zeradas, a tela dinâmica apresenta 45
posições BRL e 13 USD avaliadas e nenhum bloqueio. A diferença de R$ 36.569,21
entre Fin2 e Fin1 em BRL decorre dos preços históricos aceitos no Fin2; não é
uma ausência de cobertura. Saldos e quantidades continuam sem pendências.

Nenhum dos 286 documentos preservados contém cota ou saldo atualizado da
Brasilprev. Completar essa avaliação exige um extrato individual com data e
valor da cota; o custo médio não será usado como substituto de valor de mercado.
Essa pendência continua aberta para os escopos em que a aplicação é incluída.

A aceitação final da reconciliação ainda não foi registrada.

## Revisão local da Brasilprev em 09/09/2026

A consulta somente leitura ao banco de desenvolvimento encontrou uma cotação
manual já registrada em 07/09/2026: R$ 4,638418, referência 02/09/2026, moeda BRL,
sem documento vinculado. A [fonte cadastrada no Gorila](https://gorila.com.br/produtos-de-investimento/fundos/brasilprev-renda-total-ciclo-de-vida-2030-e-fic-fim)
foi consultada e confirma valor e data para **BRASILPREV RENDA TOTAL CICLO DE
VIDA 2030 E FIC FIM**, CNPJ 09.272.869/0001-60.

O cadastro local tem nome **Brasilprev CICLO DE VIDA 2030 I PGBL** e CNPJ vazio.
Portanto, a correspondência entre o plano cadastrado e o fundo da fonte ainda
precisa de comprovação por extrato ou identificação documental do fundo.
A cotação de 02/09 também é posterior ao corte de 31/08/2026 e não pode ser
usada para fechar aquela conciliação.

Para concluir: identificar o fundo pelo CNPJ no extrato do plano e obter a cota
com data até 31/08/2026, registrando fonte e referência pelo mecanismo existente
de cotações manuais. O banco local agora contém 298 documentos; a contagem de
286 acima descreve a revisão anterior, não uma nova inspeção integral.
Nenhuma cotação foi alterada nesta revisão e a produção não foi consultada.
