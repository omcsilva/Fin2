# Roteiro de implementação

Atualizado em 05/09/2026. O Fin1 está congelado; não haverá novos lotes de
migração. O Fin2 está em produção e é a base de escrita.

## Concluído

- [x] Arquitetura Django + DuckDB mono-usuário e multi-carteiras.
- [x] Captura final do Fin1, proveniência, documentos, imagens e vínculos.
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

- [ ] Resolver a divergência de caixa APEX; os extratos terminam em fevereiro de 2024.
- [ ] Conferir saldos, rendimentos, fluxos e avaliações finais contra o Fin1.
- [ ] Classificar fluxos que ainda exigem decisão documental.
- [ ] Validar competência de IRRF e separar operações day trade.
- [ ] Revisar resultados fiscais reais e emitir relatório fiscal final.
- [ ] Normalizar REAL, DOL e EUR para códigos ISO.
- [ ] Completar o histórico dos ativos anterior aos três meses da brapi.
- [ ] Complementar o Ibovespa com arquivos oficiais da B3.
- [ ] Definir fonte ou entrada manual para ativos NENHUM.
- [ ] Criar outros adaptadores apenas para instituições ainda utilizadas.

## Pendências operacionais

- [ ] Decidir se preços e índices receberão agendamento.
- [x] Aprovar e ativar retenção automática: 7 backups regulares, 3 pré-atualização e a referência restaurada.
- [ ] Monitorar banco, backups e espaço livre.
- [ ] Medir CPU, memória e duração das atualizações.
- [ ] Documentar um ciclo produtivo completo, incluindo restauração.
- [ ] Obter aceitação final da reconciliação e do corte do Fin1.

A pasta no rpi5 já participa do backup do usuário no Backblaze. O Fin2 comprova
somente a exportação cifrada até o rpi5.
