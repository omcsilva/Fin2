# Interface do Fin2

O Fin2 usa Django, templates HTML, CSS e JavaScript local. Não há autenticação,
admin, sessões ou banco ORM. A interface consulta e grava o DuckDB por serviços
próprios, com CSRF e escrita serializada.

## Navegação

O cabeçalho possui seletores de Carteira e Ano. O lote final do Fin1 permanece
interno, pois não haverá outros lotes. O menu agrupa Carteira, Movimentações e
Dados e auditoria.

As tabelas têm tema claro, alto contraste, pesquisa e ordenação. Mantêm linhas
sem quebra, largura natural e rolagem horizontal. O conteúdo ocupa toda a
largura entre as margens responsivas.

## Recursos

- visão geral, posições, caixa, alocação e histórico;
- desempenho, rendimentos, fluxos e estimativas fiscais;
- lançamentos, transferências e correções compensatórias;
- importação CSV/XLSX com pré-visualização;
- cadastros, conciliação e revisão;
- registros e documentos vinculados;
- cotações em abas Cobertura completa e Capturas externas.

Consulte [modo de escrita](write-mode.md) e
[atualização de preços](price-updates.md).

## Barra de status

O botão à direita inicia a atualização de preços e permite cancelá-la durante o
trabalho. Cada resultado aparece imediatamente. A última mensagem permanece
visível e pode ser copiada por clique, Enter ou Espaço.

A data global só avança quando todos os ativos BRAPI estão atualizados. Ativos
NENHUM ficam fora do ciclo. A cobertura pode ser filtrada por mecanismo.

## Segurança e configuração

Operações de escrita exigem POST e CSRF. Documentos são verificados por tamanho
e SHA-256 e visualizados em sandbox. HTML legado é escapado. Produção usa um
único processo proprietário do DuckDB.

Variáveis principais: FIN2_DATA_DIR, FIN2_DEBUG, FIN2_SECRET_KEY,
FIN2_ALLOWED_HOSTS, FIN2_CSRF_TRUSTED_ORIGINS e BRAPI_TOKEN. Rotas e arquivos
estáticos preservam o prefixo /fin2/.

## Ledger atual e Histórico

As páginas principais representam o ledger Fin2: operações importadas aceitas
continuam compondo posições e caixa, somadas aos lançamentos manuais, estornos,
transferências e aportes vinculados. O menu Histórico reúne as conferências de
origem em `/fin2/historico/fin1/` (visão geral, posições, caixa, alocação,
cotações e relatórios), além da conciliação, registros e revisão da importação.
Essas conferências excluem eventos manuais e cotações externas posteriores;
não constituem uma cópia imutável do cadastro, pois decisões de conciliação e
correções de cadastro continuam preservadas nas projeções da origem.

A Visão geral deixa de apresentar contagens de migração. Posições e seu detalhe
mostram a quantidade do ledger; Saldos e extrato soma o caixa importado e manual,
incluindo o aporte automático da compra e seu estorno. Dividendos e vendas ficam
na conta de investimento. Moedas equivalentes REAL/BRL e DOL/USD são normalizadas
no extrato e nos fluxos. O saldo acumulado do extrato inclui movimentos anteriores
ao ano filtrado. Contas compartilhadas entre carteiras são mostradas integralmente.

O seletor de anos do ledger inclui liquidações manuais e o ano corrente. O
Histórico usa anos da origem e, sem filtro anual, o corte do lote importado.
Relatórios financeiros atuais limitam eventos ao lote e corte selecionados,
e incorporam os fluxos manuais também no retorno por aplicação.

## Incluir zerados?

O checkbox global `include_zeroed=1` é desmarcado por padrão e acompanha links,
filtros locais e paginação. Sem ele, as consultas de relatórios excluem cadastros
com status explícito ZERADO/ZERADA (incluindo a decisão ZERADA das contas).
Saldo ou quantidade zero, isoladamente, não definem status.

O campo Status de titulares, instituições, produtos e ativos é editável em
Cadastros e começa vazio, inclusive nas projeções de registros antigos. A
migração 0043 fornece esse padrão sem modificar os documentos ou registros de
origem. O campo existente de decisão das contas aparece como Status no cadastro.

A exclusão propaga os vínculos: titular/instituição → conta → aplicação;
produto → ativo → aplicação. `report_scope` aplica os mesmos predicados às
relações e projeções usadas em relatórios antes de agregar ou paginar, tanto no
ledger atual quanto no Histórico. A opção marcada usa as consultas integrais.
As telas de edição e os registros originais continuam acessíveis para permitir
revisão de status; o filtro não apaga dados nem altera lançamentos.


## Aprovação de extratos XP

O assistente destaca as etapas Carregar, Aprovar carga, Revisão e Concluído.
A aprovação tem tabela de leitura com pesquisa, ordenação e paginação; os
formulários de decisões por movimento ficam exclusivamente na revisão.
O formulário de aprovação usa observação opcional para ambas as ações, rejeição
vermelha e aprovação verde à direita. As regras de cor são específicas do
formulário para prevalecer sobre o estilo geral dos botões, inclusive no hover.
Veja o [fluxo de extratos XP](xp-account-statement-plan.md#fluxo-de-interface-em-11092026).

O cabeçalho utiliza o recurso `static/carbono.png`; os recursos antigos
`carbon.png` e `carbon3.png` foram substituídos. A coleta de estáticos deve ser
executada na implantação para publicar o CSS e os recursos com seus hashes.
