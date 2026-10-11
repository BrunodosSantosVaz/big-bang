---
name: bb-rodar-sprint
description: Use para vamos rodar a sprint ou vamos encerrar a sprint. Seleciona épicos, roda bb sprint start e coordena testes, tarefas, documentação e retrospectiva no fluxo agrupador.
---

# Rodar ou encerrar sprint (v3)

## Quando usar

Ao iniciar, retomar ou encerrar uma sprint. A release é cortada da `develop` depois; não confunda sprint com release.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/pipeline/process/sprint.md`, `execution.md`, `bigbang.toml` e `flags.toml`. Use
`bb board show` para o estado e as pendências.

## Passos

1. Seleção: para cada épico em Ready escolhido pelo dono, registre `bb decision approved:selection N --quote "…"`.
   O controlador leva o cartão a Selected. Respeite o WIP (`epics_in_progress`, ou `wip` do contrato no
   autonomous). Confira também o token válido sem ler o valor, a CI verde na ponta da `develop` e nada pendente da
   sprint anterior.
2. Rode `bb sprint start` (ou o botão *Start sprint* com `dry_run=true`) e mostre o plano. Para cada épico ele cria
   como sub-issues o teste de aceite, as tarefas e a documentação, com as dependências nativas, e a branch
   `test/<n>-<slug>` a partir da `develop`. Depois rode de verdade e confira: o épico vai para In Progress.
3. Por épico: `bb-escrever-testes-aceite`. Depois do merge do teste, rode `bb branches` (botão *Create branches*)
   para as tarefas desbloqueadas; siga `bb-codar-tarefa` nelas e `bb-documentar-epico` por último. Trabalhe em
   paralelo as tarefas de épicos diferentes, até o limite de posses por agente.
4. Quando todas as sub-issues de um épico fecharem, ele está pronto para a release; siga `bb-entregar-epico`.
5. Encerrar: resuma o que foi publicado e o que segue em andamento e siga `bb-retrospectiva`. Trabalho incompleto
   continua na próxima sprint e nunca é declarado concluído.

## Pare e pergunte quando

Um portão recusar, a CI ficar vermelha ou faltar decisão, revisão ou homologação. Explique o motivo sem forçar.

## Nunca

Pule o teste do épico, crie branch de épico (o épico só agrupa), enfraqueça portões ou tome decisões do dono.

## Pronto quando

Na execução, cada épico selecionado está em In Progress com as sub-issues criadas e as tarefas andando. No
encerramento, a retrospectiva está registrada e as pendências estão explícitas.
