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

Uma prévia pode ser confirmada ou rejeitada com justificativa. A rejeição não
remove o arquivo armazenado e impede sua confirmação posterior, preservando a
evidência e o estado do processamento.

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
