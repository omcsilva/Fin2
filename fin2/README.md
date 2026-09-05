# Pacotes da aplicação

| Pacote | Responsabilidade |
| --- | --- |
| dashboard | Views, filtros, formulários e apresentação |
| portfolio | Cadastros, ledger, preços, cálculos e trabalhos assíncronos |
| transactions | Limites reservados para serviços de eventos |
| imports | Fin1, arquivos genéricos, adaptadores e proveniência |
| market_data | Limites reservados para normalização de provedores |
| analytics | Limites reservados para serviços analíticos |
| tax | Limites reservados para regras fiscais versionadas |

A implementação atual concentra parte dos serviços financeiros em
fin2/portfolio e as consultas HTTP em fin2/dashboard/views.py. O ledger
editável, os cálculos, a atualização de preços e a implantação estão ativos.

Consulte [modo de escrita](../docs/write-mode.md),
[preços](../docs/price-updates.md), [interface](../docs/dashboard.md) e
[roteiro](../docs/roadmap.md).
