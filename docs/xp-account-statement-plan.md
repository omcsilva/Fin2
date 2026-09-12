# Plano: upload e processamento de extratos XP

Plano original: 10/09/2026. Fluxo de interface atualizado em 11/09/2026.
A confirmação financeira de cada extrato depende da revisão explícita do usuário.

## Amostra examinada

Arquivo: `Extrato 467887 JAN. 2025 a DEZ. 2025.xlsx`, conta XP 467887,
período declarado de 01/01/2025 a 31/12/2025, consulta em 10/09/2026 às 12:57.
Somente o arquivo de 2025 foi analisado. Nenhum conteúdo documental foi tratado
como instrução de execução.

- Uma aba, `Planilha1`, com 83 linhas e 14 colunas; cabeçalho dos movimentos
  na linha 14 e 49 movimentos nas linhas 15–63.
- Colunas úteis: movimentação, liquidação, lançamento, valor em reais e saldo.
- Ordem inversa da sequência de caixa. Inverter as linhas preserva a sequência
  dentro de cada dia; ordenar apenas pela data de movimentação não funciona.
  Há seis operações em bolsa com liquidação posterior à movimentação.
- Créditos: R$ 2.456.635,82; débitos: R$ 2.113.186,50;
  variação líquida: R$ 343.449,32.
- Saldo inicial **inferido** antes do primeiro movimento: R$ 955,25.
  Último saldo informado, em 30/12/2025: R$ 344.404,57.
  Os 49 movimentos encadeiam sem diferença em centavos.
- O saldo total projetado de R$ 39,52 no cabeçalho não representa o fechamento
  de 2025. Guardá-lo como metadado da consulta, fora da conciliação histórica.
- A seção de lançamentos futuros está vazia; rodapé e avisos não são movimentos.

| Família identificada | Linhas | Tratamento proposto |
| --- | ---: | --- |
| Juros sobre capital próprio | 15 | Provento, com subtipo JCP e vínculo ao ativo |
| Dividendos | 3 | Provento com vínculo ao ativo |
| Rendimentos | 7 | Preservar descrição e revisar natureza quando ambígua |
| Transferências da/para conta digital | 10 | Conciliar contraparte; não presumir aporte ou retirada externa |
| TED recebida/retirada | 5 | Identificar origem/destino e se já existe no sistema |
| Operações em bolsa | 6 | Conciliar liquidação líquida com a respectiva nota |
| Resgate de fundo | 1 | Vincular ao fundo e obter dados de cotas/custo ausentes |
| IRRF sobre resgate | 1 | Vincular ao resgate sem descontar o imposto duas vezes |
| Aplicação em previdência | 1 | Resolver produto e destino antes de gerar operação |

## Fluxo proposto

1. **Upload:** reutilizar a página Importações, com formato automático ou
   “Extrato XP — XLSX”. Selecionar carteira/conta e conferir a identificação
   extraída do documento. Bloquear conta incompatível ou moeda diferente de BRL.
   Caso falte o número da conta no cadastro, exigir associação explícita e
   auditável; nome do arquivo não basta para identificar a conta.
2. **Extração:** armazenar arquivo original e SHA-256, versão do adaptador,
   período, data da consulta e cada linha bruta com aba/linha/ordem de origem.
   Detectar cabeçalhos pelo conteúdo, admitindo deslocamento de linhas/colunas.
   Usar Decimal para valores, manter ambas as datas e o sinal original.
   Detectar seções de movimentos, futuros e rodapé. Linha desconhecida dentro
   da seção financeira vira pendência explícita, nunca desaparece silenciosamente.
3. **Conciliação:** validar o encadeamento do saldo pela sequência documental e
   liquidação; comparar saldo inicial/final e movimentos com o ledger da conta.
   Distinguir conciliação interna do arquivo e conciliação com o Fin2.
   Saldo inicial inferido deve aparecer assim na interface, sem criar aporte
   ou ajuste automático. Arquivo vazio ou sem saldo suficiente deve apresentar
   limitação explícita, sem inventar saldo zero.
4. **Prévia:** mostrar datas, descrição original, valor, saldo, categoria sugerida,
   aplicação, vínculo existente e situação: “Novo”, “Já registrado”, “Pendente”
   ou “Divergente”. Exibir totais, saldos, diferença e filtro por pendências.
   Permitir resolver aplicação, contraparte e vínculos sem alterar a fonte.
   Cada decisão deve registrar justificativa e histórico de revisão.
5. **Confirmação:** separar “Registrar documento e conciliação” de “Confirmar
   novos lançamentos”. O primeiro conserva evidências mesmo quando faltam notas
   ou cotas. O segundo exige todas as decisões financeiras do lote resolvidas,
   revalida duplicidades e confirma atomicamente apenas os eventos novos.
   Vínculos a registros existentes não movimentam novamente caixa ou posição.
6. **Resultado:** informar quantidades de linhas documentadas, conciliadas,
   pendentes e eventos criados, oferecendo acesso ao arquivo e aos registros.
   Rejeições conservam a evidência; correções financeiras posteriores usam
   reversões compensatórias, sem apagar eventos confirmados.

## Regras financeiras e prevenção de duplicidade

- O extrato é evidência de caixa. Não contém quantidade/preço dos negócios em
  bolsa: suas seis liquidações não podem ser convertidas em compras/vendas
  pelo sinal do valor. Extrair número da nota e data do pregão, vinculando
  cada liquidação ao conjunto de negócios, despesas e impostos correspondente.
  Divergência do líquido permanece pendente; a nota continua sendo a fonte dos
  detalhes de negociação. A ligação precisa aceitar vários eventos por linha.
- Valores recebidos de proventos são os valores de caixa documentados. Não
  presumir bruto, alíquota ou imposto retido não discriminado. O número após
  `S/` é informação da base do provento, não compra nem alteração de posição.
- Dividendos e vendas permanecem recursos da conta de investimento. Respeitar
  a Conta de Resultado para fluxos externos efetivos, sem criar aportes novos
  para movimentos históricos ou para cada transferência bancária.
- Transferências entre contas próprias devem formar um vínculo entre as duas
  pontas. Se a contraparte estiver ausente, manter pendência documental em vez
  de fabricar uma entrada/saída externa. TED também exige essa distinção.
- No resgate do Trend, guardar separadamente R$ 296.288,87 e o débito de IRRF
  de R$ 2.418,76. Não deduzir o imposto do evento e novamente como débito.
  Não reconstruir quantidade, custo ou resultado fiscal apenas com esses valores.
- A aplicação de R$ 40.000,00 em previdência não identifica o produto. Exigir
  vínculo documental/cadastral antes de alterar posição ou custo.
- SHA-256 impede repetir o mesmo arquivo, mas não resolve extratos de períodos
  sobrepostos, arquivos reexportados ou movimentos já presentes no histórico.
  Confrontar conta, moeda, datas, valor, descrição normalizada, referência de
  nota/ativo e sequência/saldo quando disponíveis. Preservar multiplicidade:
  duas linhas legítimas iguais não podem ser fundidas pela mesma impressão.
  Correspondência ambígua exige revisão; diferenças em reexportações devem
  gerar conflito auditável, nunca sobrescrever silenciosamente a versão anterior.
- Confrontar também eventos manuais, notas importadas e histórico já existente
  do Fin1. Não realizar nova importação do Fin1. A comparação efetiva com o banco
  ainda não foi executada neste planejamento.

## Integração técnica

O Fin2 já tem contrato `Adapter`, detecção por confiança, upload com limite de
5 MiB, documento original, prévia, confirmação transacional e rejeição. O
adaptador Clear/XP existente lê notas PDF; ele não cobre este extrato XLSX.

- Criar `fin2/imports/xp_statement.py`, identificador `xp-account-statement`,
  versão 1, tipo `account_statement`, e registrá-lo no carregamento dos adaptadores.
- Estender `fin2/imports/generic.py`: atualmente toda linha da prévia gera um
  `manual_event` e `file_import_event` exige evento único por linha. O novo fluxo
  precisa distinguir observações, vínculos existentes e eventos novos, incluindo
  relações entre uma linha e vários eventos e várias fontes para o mesmo evento.
- Adicionar migração nova para linhas documentais, decisões e vínculos de
  conciliação. Reutilizar `source_document`, `ledger.file_import` e
  `ledger.statement_balance_observation`, acrescentando proveniência XLSX e
  indicação de saldo inferido. Separar estado documental de estado financeiro
  para não chamar um lote com pendências de importação financeira concluída.
- Atualizar `fin2/dashboard/views.py` e
  `templates/dashboard/file_imports.html` para revisão e resumo da conciliação.
- Revalidar decisões dentro da transação de confirmação para impedir que duas
  prévias abertas criem o mesmo movimento. Respeitar a coordenação de escrita
  única do DuckDB. Para 49 linhas, processamento síncrono é suficiente como
  proposta inicial; medir duração antes de introduzir fila.
- Validar estrutura real do XLSX e limites de tamanho descompactado/linhas;
  não executar fórmulas ou vínculos externos. Células financeiras com fórmulas
  devem ser sinalizadas, evitando aceitar resultados em cache sem evidência.

## Entregas e aceitação

1. **Leitura e evidência:** adaptador, metadados, linhas e saldos, com amostra
   sanitizada de testes. Aceite: exatamente 49 movimentos no exemplo, totais
   acima e diferença interna de R$ 0,00, sem usar saldo projetado ou rodapé.
2. **Conciliação e revisão:** vínculos ao histórico, notas e contrapartes;
   resolução de pendências pela interface. Aceite: nenhuma duplicação em
   reupload, sobreposição ou confronto com evento já registrado, preservando
   movimentos distintos com campos iguais.
3. **Confirmação financeira:** geração apenas de eventos documentados e
   resolvidos. Aceite: falha causa rollback integral; repetição/concorrência não
   duplica; liquidação vinculada à nota não soma caixa novamente; transferência
   própria não aumenta aportes; resgate e imposto não duplicam desconto.
4. **Validação em desenvolvimento:** usar cópia do banco para conferir os 49
   movimentos contra os dados existentes, sem alterar a fonte histórica.
   Testar cabeçalho deslocado, datas distintas, ordem intradia, descrição
   desconhecida, saldo quebrado, conta incompatível, futuros e XLSX inválido.
   Executar checks Django, suíte e `git diff --check` na implementação.

A primeira entrega já permite carregar o extrato completo e conservar suas
evidências. A criação de operações sem detalhes suficientes fica condicionada
à conciliação com notas, comprovantes ou dados existentes, sem preenchimentos
financeiros presumidos.

## Validação da implementação em 10/09/2026

- Adaptador reutilizável: número XP extraído do documento, vínculo persistente
  por conta, titular conferido contra o cadastro e confirmação explícita inicial.
  O número presente no nome cadastral também é confrontado quando disponível.
  Nomes curtos (por exemplo, Marcos) são aceitos apenas com associação explícita
  e quando todos os termos constam do nome documental.
- Testes sintéticos cobrem titulares diferentes, layouts deslocados, datas de
  liquidação, futuros, fórmulas, arquivo inválido, saldo quebrado, reexportação,
  multiplicidade, nota com vários movimentos, rollback e resgate/IRRF separado.
- A amostra real foi carregada somente em uma cópia isolada do banco de
  desenvolvimento. Extração/prévia e consulta de conciliação levaram 2,43 s
  nessa execução; 49 linhas, nenhuma quebra de saldo e oito linhas com
  candidatos de mesma data e valor. Os candidatos ainda exigem decisão.
- Saldo inicial do Fin2 e do extrato: R$ 955,25. Saldo final no Fin2 da cópia:
  R$ 2.972,13; saldo final do extrato: R$ 344.404,57. Diferença: R$ 341.432,44.
  Essa é uma divergência com o banco, distinta da consistência interna do XLSX.
- A página de revisão respondeu HTTP 200 sobre a cópia. Os formulários mantêm
  CSRF e a restrição de escrita; os movimentos são paginados de 20 em 20.
- Nenhuma decisão ou lançamento do extrato real foi confirmado no banco em uso.
  O saldo divergente não foi corrigido automaticamente.

Para usar: abrir Importações, selecionar a conta, carregar o XLSX e, no primeiro
upload, confirmar a associação com justificativa. Registrar o documento se
necessário, revisar as linhas pendentes e confirmar apenas depois de resolver
todas. Para uma nota ainda ausente, importar a nota primeiro e voltar à prévia;
os candidatos são consultados novamente a cada abertura. Contraparte própria
já lançada exige conciliar a transferência existente para evitar uma segunda
perna duplicada. Descrições desconhecidas permanecem pendentes até receberem
vínculo documental com registros válidos.

### Estado local após validação

A suíte completa executada passou com 109 testes. Após os ajustes finais, os
12 testes específicos XP também passaram. `manage.py check` e `git diff --check`
passaram. O POST documental com CSRF retornou 302 e não criou eventos; sem CSRF,
retornou 403.

A migração `0054_xp_statement.sql` foi aplicada no banco de desenvolvimento após
backup em `backups/pre-xp-statement-20260910T132627.duckdb`. A contagem de eventos
financeiros permaneceu igual, e não há uploads XP no banco em uso. A prévia real
permanece apenas na cópia isolada de auditoria. Não houve commit, push ou
implantação em produção nesta execução.


## Fluxo de interface em 12/09/2026

1. **Carregar:** selecionar o XLSX e a conta. A associação inicial de número e
   titular continua exigindo confirmação explícita.
2. **Aprovar carga:** ler o arquivo e gravar os lançamentos em tabela temporária,
   listando-os integralmente **sem classificá-los**, com Linha, Movimentação,
   Liquidação, Lançamento, Valor e Saldo. Linha contém somente o número
   original; Lançamento preserva apenas a descrição. Datas aparecem em DD/MM/AA,
   valores em `R$ 1.234,56`; números, datas e valores ficam alinhados à direita.
   Problemas de leitura aparecem em coluna adicional somente quando existem
   erros no arquivo.
   A pesquisa e a ordenação pelos cabeçalhos abrangem todas as linhas antes da
   paginação de 20 itens; os controles permanecem ao trocar de página.
   Aprovar vale para o arquivo inteiro, mesmo com pesquisa ativa, e não cria
   eventos financeiros. **Rejeitar descarta a carga** — linhas, decisões,
   documento e arquivo — e devolve o processo à etapa 1, sem registro algum da
   decisão.
3. **Revisão:** após aprovar a carga, abrir a rota própria
   `/fin2/importar/<identificador>/revisao/`, que tenta conciliar cada lançamento
   com aplicações ou outros lançamentos existentes da mesma conta.
   - Cada lançamento tem um botão de revisão manual; dentro dela é possível
     **excluir o lançamento**, que sai da carga sem ir para o ledger e fica
     registrado no histórico.
   - Lançamento com informação insuficiente para incorporação fica **Pendente**;
     o resolvido fica **Pronto**; o excluído fica **Excluído**. O estado é
     derivado da decisão registrada, sem coluna própria.
   - Abaixo da tabela fica o botão que lança no ledger os lançamentos **Pronto**.
     Ele aparece quando não resta nenhum lançamento **Pendente**; nesse momento o
     processo segue para a próxima etapa.
   - Cada registro criado guarda a referência do extrato de origem e o histórico
     de revisões: o evento em `ledger.manual_event` recebe uma entrada em
     `ledger.audit_log` (`entity_type='manual_event'`) com `import_id`,
     `line_number` e a decisão aplicada, e cada decisão também fica em
     `ledger.xp_statement_decision`. Não foi criada tabela nova para isso.
4. **Concluído:** depois das validações financeiras, o botão lança no ledger os
   lançamentos **Pronto** e o processo termina. A tela informa quantos
   lançamentos novos foram gerados e os lista, já que permanecem vinculados ao
   extrato de origem. Neste momento a tabela temporária de revisão é apagada:
   `xp_statement`, `xp_statement_line` e `xp_statement_decision` deixam de
   existir. Permanecem `xp_statement_link` (vínculo entre extrato e ledger) e
   `xp_statement_claim` (deduplicação), que as cargas seguintes consultam.

O reenvio de um arquivo ainda em prévia reutiliza o registro documental, mas
volta a **Aprovar carga**, mesmo quando já existe aprovação documental anterior.
Não apaga decisões anteriores nem duplica movimentos; arquivos financeiramente
confirmados continuam no resultado da importação.

A aprovação da carga não grava registro de decisão: ela registra a evidência do
extrato, marcando `ledger.xp_statement.documented_at` e gravando a observação de
saldo em `ledger.statement_balance_observation`. A rejeição descarta tudo e não
grava auditoria. As colunas `ledger.file_import.rejection_reason` e `rejected_at`
foram removidas pelas migrações `0056_drop_import_document_index.sql` e
`0057_drop_import_rejection.sql` — a primeira existe porque o DuckDB não remove
uma coluna enquanto um índice referencia coluna posterior.

### Evidência preservada após o descarte

`xp_statement_line` sustentava duas verificações de integridade em `_validate`.
Para que o descarte da etapa 4 não as desligue, a evidência passou para
`ledger.xp_statement_claim` (`0058_claim_keeps_line_evidence.sql`), que já
guardava o fingerprint e agora guarda também `description` e `settlement_date`,
com backfill das cargas já confirmadas:

- a verificação de extrato sobreposto lê `description` e `settlement_date` do
  claim, em vez do `raw` da linha;
- a verificação de movimento conciliado com duas linhas cruza
  `xp_statement_link` com o `fingerprint` do claim.

As duas passaram a ter teste próprio, que as exercita depois da carga
concluída: `test_overlap_check_survives_the_concluded_load` e
`test_entry_linked_twice_is_refused_after_the_load_concludes`.
