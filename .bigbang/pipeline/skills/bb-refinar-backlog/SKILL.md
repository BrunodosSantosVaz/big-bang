---
name: bb-refinar-backlog
description: Use para Ideia, vamos refinar o backlog ou refinar uma issue. Conduz um épico por vez no quadro único (Brainstorm → Backlog → Refinement → Prototyping → Ready) e registra as decisões do dono com bb decision.
---

# Refinar backlog (v3)

## Quando usar

Ao registrar uma ideia ou refinar um épico. Não inicia implementação.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `PRODUTO.md`, as RNs existentes e `.bigbang/pipeline/process/planning.md`. Veja o quadro com
`bb board show`.

## Passos

1. Ideia: confira se já existe e crie o épico pelo formulário (label `type:epic`) com o problema em uma a três frases.
   Ele nasce em Brainstorm. A entrada no Backlog é decisão do dono: `bb decision approved:backlog N --quote "…"`, e
   então `bb move N Backlog` (no Flash e no autonomous, conforme o risco, você mesmo move).
2. Refinamento: `bb claim N SEU-NOME` (a etapa de refinamento também tem posse) e `bb move N Refinement`. Trabalhe um
   épico por vez, com perguntas individuais.
3. Monte problema e objetivo, escopo dentro e fora, RNs confirmadas, critérios CA-n em Dado/Quando/Então e as tarefas
   previstas, cada uma do tamanho de um PR, com dependências. Tarefas que tocam os mesmos arquivos são dependentes.
4. Registre com o dono as decisões do cartão:
   - protótipo: `prototype:required` ou `prototype:waived`;
   - feature flag: `flag:required` quando o épico muda o comportamento do artefato, senão `flag:waived`;
   - homologação: `qa:human`, `qa:agent` ou `qa:not-applicable`;
   - revisão: `review:ai` ou `review:human` e `tests-review:*`;
   - áreas (`area:*`) e risco (`risk:*`, que só sobe).
   Faça STRIDE se tocar zona sensível. Confira a Definition of Ready inteira.
5. Mostre o resumo e espere a aprovação. Registre `bb decision approved:refinement N --quote "palavras do dono"`.
   O controlador leva o cartão a Prototyping (com `prototype:required`, siga `bb-prototipar`) ou a Ready.
6. Libere a posse com `bb unclaim N` e siga para o próximo épico.

## Pare e pergunte quando

Faltar ou se contradisser qualquer decisão de escopo, RN, flag, protótipo ou homologação.

## Nunca

Invente RN, crie tarefa sem critério, arraste o cartão no quadro (a reconciliação desfaz), ponha label de decisão
sem a frase do dono ou abaixe o risco de um cartão.

## Pronto quando

O épico está em Ready (ou em Prototyping), cumpre a Definition of Ready e tem `approved:refinement` registrado com a
frase do dono.
