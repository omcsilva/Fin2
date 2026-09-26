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

Há dois formatos de nota de corretagem que devem ser distinguidos:

- **SINACOR/B3**: formato legado, geralmente PDF de uma página, com a seção
	`Negócios realizados` e descrições como `SANEPAR ON N2`.
- **XP**: formato próprio da XP, geralmente PDF de duas páginas, com `Nota de
	Negociação`, data da consulta, ticker explícito como `SAPR3` e resumo
	financeiro separado.

O formato **XP** é preferencial para a importação por preservar melhor o ticker
e a estrutura financeira. O formato **SINACOR/B3** permanece como fallback
compatível.

`clear-brokerage-note` versão 4 reconhece notas PDF da Clear/XP pelo conteúdo,
extrai negócios à vista, data do pregão, ativo, lado, quantidade, preço e valor,
taxa de liquidação, corretagem, ISS, taxa Bovespa, emolumentos e IRRF, e registra página e item. A conta é escolhida na prévia e cada ativo precisa
corresponder de forma única a uma aplicação dessa conta. Negócios não resolvidos
permanecem com erro e bloqueiam a confirmação integral da nota.

Taxas, emolumentos e IRRF são eventos próprios e são associados aos ativos pelas
negociações identificadas. As parcelas são rateadas pelo valor bruto e persistidas
em `ledger.file_import_event_allocation`, com método distinto para despesas e
retenções; os eventos mantêm vínculo ao documento e ao localizador da linha da
nota. Somente despesas (`gross_value_pro_rata`) entram no custo da compra ou são
deduzidas do valor realizado da venda. O rateio do IRRF (`withholding_gross_value_pro_rata`)
preserva a atribuição fiscal por ativo, mas não altera custo nem resultado da
operação.

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

Na revisão, o Fin2 apresenta os registros do pré-ledger que serão gravados ou
vinculados a movimentos existentes. Cada operação extraída de uma nota de
corretagem aparece separadamente, com ativo, quantidade, tipo e valor; a linha
líquida correspondente do extrato permanece como referência de conciliação, não
como uma segunda operação. Taxas são rateadas entre as negociações pelo valor
bruto. O total dos itens da nota precisa coincidir com o valor líquido relacionado.

Para os demais lançamentos, o Fin2 **identifica cada linha sozinho** a partir do
extrato e do banco: categoria/tipo, aplicação e vínculo com movimentos já
existentes da conta. A identificação só vincula quando existe um único candidato
de mesma conta, liquidação, valor e descrição normalizada, e só cria lançamento
novo quando o tipo decorrente da categoria passa nas validações. O registro fica
**Pronto** quando a identificação basta para gravar e **Pendente** quando falta
dado; a coluna **Detalhe** informa o que falta. A identificação é só prévia:
nada é gravado antes do botão de gravação, que fica desabilitado enquanto nenhum
registro estiver Pronto. A decisão manual do revisor sempre prevalece. A confirmação
financeira só conclui a importação quando nenhum registro permanece Pendente;
nesse caso a etapa seguinte lista os registros criados.
