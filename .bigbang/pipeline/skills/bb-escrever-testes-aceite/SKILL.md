---
name: bb-escrever-testes-aceite
description: Use para a sub-issue de teste de aceite de um épico. Escreve um teste por critério com RN e marca de pendente da tarefa implementadora, sem escrever implementação.
---

# Escrever testes de aceite (v3)

## Quando usar

Para a sub-issue `type:test` do épico, criada pelo `bb sprint start`, antes das branches de implementação.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, o épico com os CA-n, as RNs, `.bigbang/padroes/testes.md` e
`.bigbang/pipeline/process/execution.md`. Confira a marca de pendente configurada e a label `tests-review:*`.

## Passos

1. `bb claim N SEU-NOME`; espere a confirmação e trabalhe só na pasta própria informada, na branch `test/N-slug`
   criada da `develop`.
2. Escreva um teste por critério, com o ID da RN no nome, os cenários em português e a marca de pendente da tarefa
   responsável. Crie ou atualize os documentos RN-* com os critérios confirmados, sem inventar regra.
3. Mostre que o cenário não satisfaz o critério sem implementação e que a suíte passa com as marcas pendentes.
4. Abra o PR para a `develop` com `Refs #N` e o mapa critério → teste → tarefa. Peça a revisão independente, ou a do
   dono com `tests-review:human`. `approved:tests` só com a frase do dono, via `bb decision`.
5. Depois do merge, confira que a tarefa fechou e a trava foi liberada; se ela ficar, use `bb unclaim N` na pasta.

## Pare e pergunte quando

Um critério ou RN for ambíguo ou o teste exigir uma decisão não tomada. Exponha a dúvida antes de codificar.

## Nunca

Escreva implementação, faça teste que passa sem ela ou altere teste existente sem a aprovação prevista
(`approved:test-change`).

## Pronto quando

O PR de teste está aprovado e mesclado na `develop`; as tarefas desbloqueadas recebem as branches com `bb branches`.
