# Problema Pendente: Layout da Tabela de Extrato XP (Scroll Horizontal)

## Status Atual
O usuário relatou que a tabela de revisão de extrato da XP (`xp_statement.html` e `xp_statement_approval.html`) está "extrapolando a largura da tela, com textos não sendo truncados e apresentando uma barra de rolagem horizontal".

## O que foi alterado nas tentativas de correção
Fizemos múltiplas iterações aplicando as melhores práticas e truques conhecidos de CSS para tabelas de largura fixa, mas **nenhuma delas surtiu o efeito esperado no navegador do usuário** (testado em Chrome e Firefox).

O que está atualmente no código (injetado via bloco `<style>` nos templates):
1. **Quebra de Herança:** O arquivo global `fin2.css` define `table { width: max-content; }` e `th, td { white-space: nowrap; }`. Nós tentamos sobrescrever isso usando `width: 100% !important; table-layout: fixed !important;` nas tabelas.
2. **Larguras Fixas (`<colgroup>`):** Adicionamos tags `<colgroup>` com larguras em `%` somando exatamente 100% para todas as colunas.
3. **Divs de Truncamento (`<div class="t">`):** Envelopamos o conteúdo de TODAS as células (`<td>` e `<th>`) em `<div class="t">`, que contém `overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important; min-width: 0 !important; max-width: 100% !important; display: block !important;`.
4. **Truque do max-width 0:** Configuramos `max-width: 0 !important;` nos próprios `<td>` e `<th>` para forçar o navegador a ignorar a largura do conteúdo (min-content) e obedecer estritamente às porcentagens do `colgroup`.
5. **Container Grid:** Transformamos a `.table-wrap` (que tem `overflow-x: auto`) em um container grid usando `display: grid !important; grid-template-columns: minmax(0, 1fr) !important;` para impedir que a tabela empurrasse o container pai além dos limites da tela.
6. **Quebra de Linha Global:** Injetamos `overflow-wrap: anywhere !important;` em `.panel` para caso o problema fosse um título ou texto longo fora da tabela forçando o layout inteiro a expandir.

## Próximos Passos Sugeridos para o Futuro Agente
1. **Inspecione o DOM Computado:** Como não foi possível usar o subagente de navegação para acessar a porta do Remote Debugging (falha na localização do `DevToolsActivePort`), não conseguimos confirmar as medidas computadas reais (`clientWidth`, `scrollWidth`) da tela do usuário. Se você conseguir acessar a porta 9222, faça isso primeiro.
2. **Descarte Tabelas HTML:** O CSS de tabelas é notoriamente inconsistente quando misturado com certos layouts pai flexíveis/grid e classes globais conflitantes. Pode ser mais eficiente refatorar o `<table class="table-wrap">` inteiro para um modelo baseado inteiramente em `CSS Grid` (`div`s).
3. **Investigue Elementos Ocultos:** É possível que as tabelas estejam sendo distendidas por algum `<input>` oculto, padding exagerado gerado por alguma regra global não percebida, ou quebra no escopo do bloco `<style>`.

