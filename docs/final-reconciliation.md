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

## Cobertura

Foram avaliadas 46 posições em BRL e 13 em USD. Duas posições BRL permanecem
fora do total por ausência de cotação válida: Brasilprev CICLO DE VIDA 2030 I
PGBL e INRD11. A interface lista ambas como avaliações pendentes e não presume
valor zero. Com **Incluir zerados?** desmarcado, itens marcados como ZERADO e
seus valores deixam de aparecer, conforme a regra global dos relatórios.

Não foram encontradas diferenças de avaliação ou rendimento no conjunto com
cobertura. As diferenças de caixa e fluxo encontradas são integralmente
explicadas pelos lançamentos corretivos do Fin2.

## Atualização de cobertura em 07/09/2026

O INRD11 deixou de ser uma pendência: a série aceita da brapi contém 60
fechamentos e fornece R$ 72,65 em 27/08/2026, último pregão disponível antes do
corte. Para 150 cotas, ele acrescenta R$ 10.897,50 à avaliação ativa em BRL.
A comparação congelada acima preserva o resultado conferido em 06/09; a tela
dinâmica de conciliação passa a mostrar esse acréscimo do Fin2 e apenas a
Brasilprev como bloqueio de avaliação.

Nenhum dos 286 documentos preservados contém cota ou saldo atualizado da
Brasilprev. Completar essa avaliação exige um extrato individual com data e
valor da cota; o custo médio não será usado como substituto de valor de mercado.
