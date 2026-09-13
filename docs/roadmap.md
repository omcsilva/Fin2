# Roteiro de implementação

Atualizado em 13/09/2026 após a revisão da produção. O corte do Fin1 já foi concluído; ele está congelado
e não serão importados mais dados de lá. O Fin2 está em produção e é a base de escrita.

## Concluído

- [x] Arquitetura Django + DuckDB mono-usuário e multi-carteiras.
- [x] Captura final do Fin1, proveniência, documentos, imagens e vínculos.
- [x] Corte definitivo do Fin1, sem novas importações de dados do sistema legado.
- [x] Ledger, lançamentos manuais, transferências e reversões compensatórias.
- [x] Compra, venda, aporte, retirada, resgate, rendimento, imposto e taxa.
- [x] Validação, confirmação, erros e idempotência contra duplicidade.
- [x] Importador genérico CSV/XLSX e adaptadores Clear/XP e APEX.
- [x] Extrato de conta XP (`xp-account-statement`): upload XLSX, aprovação da
  carga, identificação automática das linhas e revisão — implementado, com
  migração `0054_xp_statement.sql` e testes próprios.
- [x] Cadastros auditáveis e seletores globais de carteira e ano.
- [x] Posições, caixa, alocação, histórico, desempenho, rendimentos e fluxos.
- [x] Correções auditadas das cinco divergências originais de quantidade.
- [x] Custo médio, taxas, isenção mensal, prejuízos e candidatos a IRRF.
- [x] Histórico disponível de ativos e referências oficiais do BCB.
- [x] Uso dos fechamentos diários aceitos nas avaliações históricas; o INRD11
  possui preço válido no último pregão anterior ao corte do Fin1.
- [x] Atualização brapi individual, intervalo de um segundo, janela recente,
  cancelamento, mecanismo BRAPI/NENHUM e progresso assíncrono.
- [x] Produção Proxmox, Git privado, releases, Nginx, systemd e HTTPS.
- [x] Backup diário, restauração isolada e exportação cifrada ao rpi5.
- [x] Interface compacta em Geist e tabelas funcionais; o extrato XP usa layout
  fixo com truncamento e não gera rolagem horizontal.

## Pendências financeiras e de dados

- [x] Conciliar a APEX Banco Inter: saídas de 16/04/2024 informadas pelo usuário registradas em 06/09/2026; saldo do ledger zerado. Extratos XP reassociados à conta correta.
- [x] [Conferir saldos, rendimentos, fluxos e avaliações finais contra o Fin1](final-reconciliation.md); comparação dinâmica disponível em Conciliação na data do corte, com ajustes posteriores do Fin2 destacados.
- [x] Classificar fluxos que exigem decisão documental; o ledger não possui fluxos na categoria `unclassified`, inclusive considerando entidades zeradas.
- [x] Separar operações day trade e usar na apuração somente IRRF com
  competência comprovada.
- [ ] [Revisar resultados fiscais reais e emitir relatório fiscal final](fiscal-review.md);
  quantidades documentadas de VALE3, escopo por produto e desdobramento BBAS3
  foram corrigidos, e 24 pernas exatas de custódia transportam o custo sem venda;
  outras 18 pernas integrais usam o custo líquido reconstruído na origem;
  seis aplicações com cadeia anterior incompleta ou origem de aquisição ausente,
  além de dois grupos de IRRF, continuam pendentes. Eventos posteriores à última
  venda não descartam mais ganhos já reconstruídos.
- [ ] Completar a avaliação de Brasilprev CICLO DE VIDA 2030 I PGBL com fonte e
  data; [revisão local de 09/09/2026](final-reconciliation.md#revisão-local-da-brasilprev-em-09092026)
  encontrou cota manual de 02/09/2026, mas falta comprovar a identidade do fundo
  (cadastro 2030 I versus fonte 2030 E) e obter cota válida até 31/08/2026.
  O INRD11 foi resolvido pela brapi, com fechamento de R$ 72,65 em 27/08/2026
  para o corte de 31/08/2026, e deixou de bloquear a conciliação em produção.
- [x] Normalizar REAL, DOL e EUR para códigos ISO, preservando os valores originais no payload importado.
- [x] Completar o histórico dos ativos anterior aos três meses da brapi; 183.218 fechamentos oficiais da B3 cobrem os 78 ativos mapeados desde a primeira compra registrada.
- [x] Complementar o Ibovespa com arquivos oficiais da B3; 6.614 fechamentos diários cobrem 03/01/2000 a 04/09/2026.
- [x] Disponibilizar cotações e avaliações manuais com fonte, data, moeda e auditoria para ativos NENHUM.
- [ ] Criar outros adaptadores apenas para instituições ainda utilizadas.

## Pendências operacionais

- [x] [Decidir sobre agendamento de preços e índices](price-updates.md#decisão-de-agendamento):
  manter atualizações manuais enquanto não houver coordenação entre escritores.
- [x] Aprovar e ativar retenção automática: 7 backups regulares, 3 pré-atualização e a referência restaurada.
- [x] Monitorar diariamente serviço, HTTP, banco, backups e espaço livre por
  `fin2-health.timer`, com falhas registradas no journal.
- [ ] Medir picos de CPU, memória e duração durante importações; serviço, backup,
  implantação e uma atualização completa de 66 preços já foram medidos.
- [x] Eliminar a rolagem horizontal das tabelas genéricas: elas passaram a
  preencher a largura do painel, com o texto descritivo quebrando linha e as
  células numéricas (`class="number"`) mantidas sem quebra, para não ocultar
  dígitos. As tabelas do extrato XP mantêm layout fixo (`table-fixed`) com
  truncamento. Em telas muito estreitas, `.table-wrap` ainda rola se o conteúdo
  numérico não puder caber; resta o menu de navegação, que estoura a largura em
  viewports pequenos.
- [x] [Documentar um ciclo produtivo completo, incluindo restauração](production-cycle.md).
- [ ] Obter aceitação final da reconciliação dos dados já importados.

## Estado verificado em produção

A verificação de produção registrada na revisão `cb19e52` mostra a página de
conciliação respondendo HTTP 200, com 45 posições BRL e 13 USD avaliadas no
escopo padrão, sem bloqueios de avaliação, saldo ou quantidade. O `main` local
avançou para `b2baad6` (dois commits à frente de `origin/main`) com o fluxo do
extrato XP. `tests/` reúne 147 métodos de teste; a contagem anterior de 89
aprovados estava desatualizada e a suíte não foi reexecutada nesta revisão.
Permanecem abertos o relatório fiscal final, a avaliação documental da
Brasilprev, a medição de importações, a eliminação da rolagem horizontal nas
tabelas genéricas e a aceitação final.

A pasta no rpi5 já participa do backup do usuário no Backblaze. O Fin2 comprova
somente a exportação cifrada até o rpi5.
