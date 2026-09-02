# Interface de consulta do Fin2

Primeira versão Django, sem autenticação, admin, sessões ou banco ORM. A interface lê a camada de auditoria DuckDB; não grava registros, não recalcula investimentos e não executa migrações.

## Executar localmente

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8020 --noreload
```

Abrir [Fin2 local](http://127.0.0.1:8020/fin2/). O servidor desta etapa foi iniciado nesse endereço. Se a sessão encerrar o processo, execute novamente o comando acima.

O diretório padrão é `~/Fin2-private/development`, contendo `fin2.duckdb` e `documents/`. Para usar outro diretório:

```powershell
$env:FIN2_DATA_DIR = 'C:\caminho\privado\development'
```

Não executar o importador enquanto o servidor usa o mesmo DuckDB. Pare o servidor antes de qualquer escrita offline. O comando `runserver` serve apenas para desenvolvimento local; não o exponha à rede.

## Telas

No alto à esquerda, o seletor **Carteira** limita as aplicações por sua relação
original em `fin1_aplicacao_carteira`; **Ano** define o período anual. O escopo
permanece nos links entre as telas. “Todas as carteiras” e “Todo o histórico”
reproduzem a visão agregada anterior. Valores inválidos ou inexistentes retornam
404 em vez de serem ignorados.

Em Posições e Alocação, o ano representa o corte em 31/12 e as quantidades são
reconstruídas pelos movimentos liquidados até essa data. A quantidade salva no
Fin1 continua visível, mas é atual e não serve como conferência histórica. Uma
cotação legada posterior ao corte é excluída, pois o snapshot contém apenas a
última cotação, não a série histórica necessária para valorar anos anteriores.

Em Caixa, o ano limita lançamentos e o fluxo de entradas/saídas. Os saldos Fin1
continuam atuais e aparecem apenas como referência. A carteira limita as contas
associadas às aplicações, mas lançamentos de uma conta compartilhada não podem
ser atribuídos com segurança a uma carteira. Registros, documentos e revisão
continuam como acervo completo do lote, embora preservem os seletores na navegação.

- **Visão geral:** lote selecionado, contagens de registros/documentos/sinalizações e tabelas de origem.
- **Registros:** filtro por tabela, busca no conteúdo e paginação de 50 linhas.
- **Posições:** cadastros por aplicação, titular/conta/ativo/moeda e conferência de quantidades; ver [critérios e limites](positions.md).
- **Caixa:** conferência de saldos por conta/moeda, com detalhe dos lançamentos e acumulados; ver [resultados e limites](cash-reconciliation.md).
- **Alocação:** valores indicativos e distribuição por moeda/classe, com cobertura e cotações antigas; ver [política de valorização](valuation.md).
- **Detalhe do registro:** campos originais, documentos vinculados e sinalizações.
- **Documentos:** busca por nome, tamanho, número de vínculos e detalhes.
- **Detalhe do documento:** visualização de PDF/JPG/PNG quando reconhecidos, download original e links para os registros relacionados.
- **Revisão:** filtro por tipo de sinalização, detalhes preservados e links para os registros.

## Atualização de preços em segundo plano

O botão **Atualizar preços** inicia um único trabalho em segundo plano para o
lote e a carteira selecionados. Ano não limita a consulta: o trabalho captura
preços atuais; a regra de corte decide depois se podem ser usados numa análise
histórica. Apenas ativos com ticker único, moeda REAL/BRL, plugin legado
`atuBrAPI` e multiplicador 1 são enviados em blocos de até 20 símbolos. Os
demais aparecem na contagem de ignorados. Não são enviados quantidades, saldos,
titulares, documentos ou nomes das carteiras.

A resposta de cada ativo é preservada e validada pelas regras descritas em
[brapi](brapi.md). A cotação externa aceita mais recente passa a ser usada nas
posições atuais e recebe a fonte `brapi_v2`. Para um ano selecionado, somente
uma cotação com data até 31/12 daquele ano é elegível; caso contrário, permanece
a referência legada compatível ou o valor fica indisponível. Uma cotação
rejeitada nunca entra na valorização.

O estado do trabalho é persistido em `price_update_job`; duas atualizações não
rodam simultaneamente. Reinicializar o serviço interrompe o trabalho em memória,
e a próxima tentativa registra o anterior como falho antes de começar. Não há
retomada do ponto interrompido. Falhas por bloco não desfazem capturas aceitas
em blocos anteriores, e o resumo informa aceitas, rejeitadas e falhas.

O navegador consulta o estado periodicamente sem recarregar a página. O rodapé
metálico mostra progresso, última captura aceita e uma notificação assíncrona
ao terminar. O endpoint de início aceita somente POST com CSRF. O JavaScript é
local e permitido pela CSP; respostas continuam `private, no-store`.

As consultas de lista se restringem a um lote. IDs de detalhes são únicos e exibem o lote ao qual pertencem. Não se somam lotes diferentes. Os valores exibidos são legados, ainda sem reconciliação financeira.

## Segurança e arquivos

O DuckDB é aberto com `read_only=True` por requisição. Banco ausente, indisponível ou sem lote resulta em uma tela 503; o dashboard nunca cria um banco automaticamente.

Os documentos são acessados por ID gerenciado. Caminhos fora do armazenamento são rejeitados; tamanho e SHA-256 são conferidos antes da entrega. Pré-visualização requer extensão e assinatura compatíveis com PDF, PNG ou JPEG. Outros formatos são entregues como download `application/octet-stream`, sem execução de HTML.

O quadro de visualização e a resposta de arquivo usam sandbox. O navegador pode não oferecer visualização embutida de todos os formatos; o download permanece disponível. A validação de assinatura não substitui antivírus ou sanitização completa de PDF. Mantenha o navegador atualizado e preserve a fronteira de rede confiável.

Textos HTML legados são apresentados escapados como texto, sem `safe` ou execução. As respostas privadas usam `Cache-Control: private, no-store`, `nosniff`, CSP e proteção de frames. CSRF permanece habilitado. Todas as rotas de consulta aceitam somente GET/HEAD; não há endpoints de alteração nesta versão.

## Configuração

| Variável | Uso |
| --- | --- |
| `FIN2_DATA_DIR` | Diretório privado contendo banco e documentos |
| `FIN2_DEBUG` | `1` por padrão local; usar `0` fora do desenvolvimento |
| `FIN2_SECRET_KEY` | Obrigatória quando debug está desabilitado; chave temporária gerada no modo local |
| `FIN2_ALLOWED_HOSTS` | Lista separada por vírgulas; padrão limitado a localhost/loopback |

O prefixo `/fin2/` é explícito nas rotas; o proxy futuro deve preservá-lo. Não configurar simultaneamente remoção do prefixo e outro prefixo via `FORCE_SCRIPT_NAME`. Assets locais usam `/fin2/static/`; produção ainda requer configuração própria de arquivos estáticos.

## Verificação desta entrega

- `manage.py check` sem problemas.
- 12 testes sintéticos aprovados, incluindo os seis testes anteriores de ingestão.
- Requisições HTTP reais às listas, detalhes, CSS e PDF retornaram 200.
- Navegação registro → documento → registro verificada nos links HTML.
- Um PDF real retornou `application/pdf`, assinatura PDF, disposição inline e `nosniff`.
- Nenhuma escrita no banco de produção Fin1 ou na camada importada pelo dashboard.

O controle automatizado do navegador não estava disponível nesta sessão. Portanto, layout, responsividade e renderização visual do PDF não foram inspecionados em um navegador; os testes verificam HTML, conteúdo e cabeçalhos HTTP.

Permanecem pendentes: modelo financeiro normalizado, reconciliação de valores, novas importações via interface, edição manual e implantação em Proxmox.
# Identificadores e cotações

`/fin2/cotacoes/` apresenta o inventário de ativos, identificadores não validados,
integrações configuradas e preços preservados por snapshot. Consulte
[escopo e limitações](market-data.md). Não executa consultas externas.
