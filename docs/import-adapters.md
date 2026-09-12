# Adaptadores de importação

Todo formato de instituição implementa o contrato de `fin2.imports.base.Adapter`.
O adaptador declara identificador estável, versão e tipo documental, e oferece
três etapas: detectar o conteúdo, extrair linhas com localização na origem e
normalizar cada linha para o ledger canônico.

O registro em `fin2.imports.registry` escolhe o adaptador pela maior confiança e
recusa empates, arquivos desconhecidos e extensões sem conteúdo compatível. O
resultado da detecção fica gravado em `ledger.file_import`, junto com a versão
do adaptador. Cada evento confirmado registra um localizador JSON, como linha do
CSV ou planilha e linha do XLSX.

O primeiro adaptador registrado é `generic-ledger` versão 1, responsável pelo
layout CSV/XLSX documentado na tela de importação. Novos adaptadores devem ser
registrados explicitamente, manter testes com amostras sanitizadas e nunca
confirmar eventos antes de toda a prévia passar pela validação.

Uma prévia pode ser aprovada ou descartada na etapa de aprovação da carga. O
descarte remove a carga, as linhas, as decisões, o documento e o arquivo
armazenado, devolvendo o processo à etapa de carregamento; nada sobre a decisão
de aprovar ou rejeitar é registrado.

`clear-brokerage-note` versão 1 reconhece notas PDF da Clear/XP pelo conteúdo,
extrai negócios à vista, data do pregão, ativo, lado, quantidade, preço e valor,
taxas, emolumentos e IRRF, e registra página e item. A conta é escolhida na prévia e cada ativo precisa
corresponder de forma única a uma aplicação dessa conta. Negócios não resolvidos
permanecem com erro e bloqueiam a confirmação integral da nota.

Taxas e emolumentos são eventos próprios e são rateados entre as negociações da
nota pelo valor bruto, com o rateio persistido em
`ledger.file_import_event_allocation`. Compras incorporam a despesa ao custo e
vendas a deduzem do valor realizado. IRRF permanece como evento fiscal separado
e não é incorporado ao custo do ativo.

`apex-account-statement` versão 1 reconhece extratos mensais da Apex Clearing
em USD. Ele extrai aportes e retiradas (`JOURNAL`), juros (`INTEREST`) e compras
ou vendas de títulos, sempre com página e linha de origem. A conta selecionada
deve usar USD e cada título negociado deve corresponder de forma única a uma
aplicação dessa conta. Os saldos de abertura e fechamento ainda não são
confirmados como eventos financeiros: são gravados em
`ledger.statement_balance_observation` como evidências históricas de
conciliação, vinculadas ao PDF e à conta.

Todo arquivo aceito pelo fluxo recebe também uma entrada em `source_document`.
Os eventos confirmados apontam para esse documento por
`ledger.manual_event_document`, permitindo abrir a fonte a partir do registro.

`bb-tesouro-receipt` versão 1 lê imagens PNG/JPEG de comprovantes do Tesouro
Direto emitidos pelo Banco do Brasil. A extração usa o executável Tesseract com
o idioma português e conserva protocolo, produto, vencimento, quantidade,
valor unitário, rentabilidade textual e valor bruto. Cada produto gera uma
compra somente quando corresponde a uma aplicação da conta escolhida. Os termos
ficam em `ledger.file_import_investment_term` e o comprovante permanece ligado
ao evento. A seleção explícita do formato permite informar que uma imagem é um
comprovante BB; sem Tesseract, a prévia é recusada com uma mensagem operacional.

`xp-account-statement` versão 1 lê extratos XLSX de conta XP em BRL, incluindo
movimentação, liquidação, descrição, valor e saldo. O primeiro upload exige
associação explícita e justificada do número XP ao cadastro e ao titular;
associações posteriores são verificadas. Nomes curtos do cadastro são aceitos
quando seus termos constam do nome documental. Contas de titulares diferentes
usam associações independentes; nenhum número ou titular está fixado no código.

A prévia XP permite registrar a evidência sem gerar eventos, revisar linhas e
vincular uma liquidação a vários movimentos existentes. A confirmação financeira
exige resolver todas as linhas; extratos sobrepostos reutilizam vínculos já
confirmados. Correspondências por data/valor são sugestões para revisão, não
confirmação automática. Proventos, transferências próprias, fluxos externos,
resgates documentados e impostos têm validações específicas. Operações de bolsa
não geram compras ou vendas pelo sinal da liquidação. Resgate/previdência exigem
quantidade e documento complementar já disponível em Documentos. IRRF exige
vínculo à linha de resgate. O original e as revisões ficam preservados.

Veja [plano e validação XP](xp-account-statement-plan.md) para as regras e a
auditoria isolada da amostra. O teste `tests/test_xp_statement.py` produz XLSX
sintéticos; extratos pessoais não integram as fixtures versionadas.

A prévia XP oferece **Aceitar sugestões em lote**: apresenta todas as sugestões
do arquivo, inclusive de outras páginas, e permite desmarcar linhas. Sugere
vínculo somente quando existe um único candidato de mesma conta, liquidação,
valor e descrição normalizada; sugere novo provento somente com uma aplicação
única pelo ativo e sem candidato de mesma data/valor. Casos ambíguos, revisões
individuais já salvas e operações sem dados suficientes permanecem fora do lote.
A aceitação revalida a prévia, salva decisões e auditoria em uma transação e não
cria eventos financeiros. A confirmação financeira segue separada e exige que
as demais pendências estejam resolvidas.
