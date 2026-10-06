---
name: bb-rodar-sprint
description: Use para vamos rodar a sprint ou vamos encerrar a sprint. Confere portões, usa os botões da esteira e coordena testes, tarefas, documentação e retrospectiva.
---
<!-- Gerado pelo Big Bang v1.4.0 a partir de .bigbang/skills/bb-rodar-sprint/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Rodar ou encerrar sprint

## Quando usar

Ao iniciar, retomar ou encerrar sprint; não confunda sprint com release de épico.

Consulte `projeto.modo`. No Flash, reutilize a autorização do plano sem pedir outro sim por tarefa. A ordem
teste → tarefas continua: escreva os testes antes e execute os afetados após concluir o código (`bb testes`).
Use a CI do mesmo SHA e não repita tudo por hábito. Estrutura, major/minor e produção exigem suíte completa.
Veja `.bigbang/processo/17-flash.md`.

## Antes de começar

Leia `AGENTS.md`, `.bigbang/processo/05-sprint.md`, `06-execucao.md`, `14-automacoes.md` e `bigbang.toml`.
Use `bb status` para conferir estado e pendências.

## Passos

1. Iniciar: confira Definition of Ready de cada épico em Próxima sprint, token válido sem ler seu valor,
   CI verde na ponta da develop e nada pendente da sprint anterior. Pergunte ao dono como entregar: **por sprint**
   (uma release com todos os épicos prontos, `epico=sprint`) ou **por épico**; registre a resposta no comentário de
   início da sprint. Trabalhe em paralelo as tarefas desbloqueadas de épicos diferentes, até `ias.tarefas_por_ia`.
2. Execute Iniciar sprint por `gh workflow run`, com os inputs do workflow existente e simular=true; mostre o plano.
   Só então execute de verdade e acompanhe o resultado. Não recrie branches/issues previstas pelo script.
3. Por épico, `bb-escrever-testes-aceite`; após o PR do teste mesclado, Criar branches; `bb-codar-tarefa` nas tarefas
   desbloqueadas; `bb-documentar-epico`. Leia cada skill ao entrar na etapa e liste pendências do dono a cada pausa.
4. Encerrar: resuma publicado/em andamento, registre data de fim pelo botão Encerrar (primeiro simulação),
   siga `bb-retrospectiva`; trabalho incompleto segue para próxima sprint, não é declarado concluído.

## Pare e pergunte quando

Um portão recusar, CI ficar vermelha ou faltar decisão/revisão/homologação. Explique o motivo, sem forçar o avanço.

## Nunca

Pule o teste do épico, enfraqueça portões ou tome decisões humanas para destravar a sprint.

## Pronto quando

Na execução, épicos em Homologação ou adiante; no encerramento, data e retrospectiva registradas com pendências explícitas.
