# Roteiro de implementação

Atualizado em 05/09/2026. O corte do Fin1 já foi concluído; ele está congelado
e não serão importados mais dados de lá. O Fin2 está em produção e é a base de escrita.

## Concluído

- [x] Arquitetura Django + DuckDB mono-usuário e multi-carteiras.
- [x] Captura final do Fin1, proveniência, documentos, imagens e vínculos.
- [x] Corte definitivo do Fin1, sem novas importações de dados do sistema legado.
- [x] Ledger, lançamentos manuais, transferências e reversões compensatórias.
- [x] Compra, venda, aporte, retirada, resgate, rendimento, imposto e taxa.
- [x] Validação, confirmação, erros e idempotência contra duplicidade.
- [x] Importador genérico CSV/XLSX e adaptadores Clear/XP e APEX.
- [x] Cadastros auditáveis e seletores globais de carteira e ano.
- [x] Posições, caixa, alocação, histórico, desempenho, rendimentos e fluxos.
- [x] Correções auditadas das cinco divergências originais de quantidade.
- [x] Custo médio, taxas, isenção mensal, prejuízos e candidatos a IRRF.
- [x] Histórico disponível de ativos e referências oficiais do BCB.
- [x] Atualização brapi individual, intervalo de cinco segundos, janela recente,
  cancelamento, mecanismo BRAPI/NENHUM e progresso assíncrono.
- [x] Produção Proxmox, Git privado, releases, Nginx, systemd e HTTPS.
- [x] Backup diário, restauração isolada e exportação cifrada ao rpi5.
- [x] Interface compacta em Geist, tabelas funcionais e largura total.

## Pendências financeiras e de dados

- [x] Conciliar a APEX Banco Inter: saídas de 16/04/2024 informadas pelo usuário registradas em 06/09/2026; saldo do ledger zerado. Extratos XP reassociados à conta correta.
- [x] [Conferir saldos, rendimentos, fluxos e avaliações finais contra o Fin1](final-reconciliation.md); comparação dinâmica disponível em Conciliação na data do corte, com ajustes posteriores do Fin2 destacados.
- [x] Classificar fluxos que exigem decisão documental; o ledger não possui fluxos na categoria `unclassified`, inclusive considerando entidades zeradas.
- [x] Validar competência de IRRF e separar operações day trade.
- [ ] [Revisar resultados fiscais reais e emitir relatório fiscal final](fiscal-review.md).
- [x] Normalizar REAL, DOL e EUR para códigos ISO, preservando os valores originais no payload importado.
- [x] Completar o histórico dos ativos anterior aos três meses da brapi; 183.218 fechamentos oficiais da B3 cobrem os 78 ativos mapeados desde a primeira compra registrada.
- [ ] Complementar o Ibovespa com arquivos oficiais da B3.
- [x] Disponibilizar cotações e avaliações manuais com fonte, data, moeda e auditoria para ativos NENHUM.
- [ ] Criar outros adaptadores apenas para instituições ainda utilizadas.

## Pendências operacionais

- [ ] Decidir se preços e índices receberão agendamento.
- [x] Aprovar e ativar retenção automática: 7 backups regulares, 3 pré-atualização e a referência restaurada.
- [ ] Monitorar banco, backups e espaço livre.
- [ ] Medir CPU, memória e duração das atualizações.
- [ ] Documentar um ciclo produtivo completo, incluindo restauração.
- [ ] Obter aceitação final da reconciliação dos dados já importados.

A pasta no rpi5 já participa do backup do usuário no Backblaze. O Fin2 comprova
somente a exportação cifrada até o rpi5.
