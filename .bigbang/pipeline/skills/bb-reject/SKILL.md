---
name: bb-reject
description: Use quando uma validação reprova um cartão (refinamento, protótipo, revisão, QA ou release). Registra a reprovação com motivo e retorno pelo bb move, respeitando as decisões do dono e o limite de tentativas.
---

# Reprovar e retornar (v3)

## Quando usar

Quando uma validação reprova um cartão do quadro: refinamento, protótipo, revisão do PR, QA ou release. A reprovação
de QA de uma release tem passos próprios em `bb-entregar-epico` (`bb qa reject`).

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Leia `AGENTS.md` e `.bigbang/pipeline/process/board.md` (estados, reprovação e retornos permitidos).

## Passos

1. Confirme quem reprovou e por quê. A reprovação de um portão do dono exige a decisão registrada dele (por exemplo,
   `bb decision qa:rejected N --quote "…"`). No Flash e no autonomous, você reprova o trabalho comum com evidência.
2. Escolha o motivo (`requirements`, `prototype`, `tests`, `code`, `security`, `docs`, `qa`, `release`) e o retorno
   permitido para a etapa:
   - Refinement → Refinement;
   - Prototyping → Prototyping ou Refinement;
   - QA → In Progress;
   - Releasing → Releasing ou In Progress;
   - tarefa em In Review → Todo ou Coding (Coding só com posse válida).
3. Rode `bb move N Rejected --reason <motivo> --return-to <estado>`. O recibo grava o motivo, o retorno e a
   evidência. As decisões do dono da etapa de retorno em diante são retiradas: a aprovação de um ciclo nunca aprova
   o seguinte.
4. Quando o impedimento for resolvido, `bb move N <retorno>` retoma o trabalho. Se o limite de tentativas for
   atingido, o cartão fica em Rejected com `blocked` até o dono decidir.

## Pare e pergunte quando

O motivo não couber na lista, o retorno desejado não for permitido ou faltar a decisão do dono.

## Nunca

Reprove para contornar um portão, apague recibos ou labels de decisão à mão ou retome um cartão `blocked` sem o dono.

## Pronto quando

O cartão está em Rejected com motivo e retorno registrados, ou já voltou à etapa de retorno com o impedimento
resolvido.
