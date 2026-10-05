---
name: bb-escrever-testes-aceite
description: Use para a issue teste-aceite de um épico. Escreve um teste por critério com RN e marca de pendente da tarefa implementadora, sem escrever implementação.
---
<!-- Gerado pelo Big Bang v1.0.0 a partir de .bigbang/skills/bb-escrever-testes-aceite/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Escrever testes de aceite

## Quando usar

Para o PR de teste do épico, antes das branches de implementação.

## Antes de começar

Leia `AGENTS.md`, épico/CA-n, RNs, `.bigbang/padroes/testes.md` e `.bigbang/processo/06-execucao.md`.
Confira a configuração de marca de pendente e as labels testes-revisao-*.

## Passos

1. `bb assumir N SEU-NOME`; espere confirmação e trabalhe só na pasta própria informada, na branch teste/N-slug.
2. Escreva um teste por critério com ID da RN no nome, cenários em português e marca de pendente da tarefa responsável.
   Crie/atualize documentos RN-* com os critérios confirmados, sem inventar regra.
3. Demonstre que o cenário não satisfaz o critério sem implementação, além da execução com as marcas pendentes.
4. Abra PR para epico/N-slug com mapa critério/teste/tarefa, resultados e cenário em português.
   Peça revisão independente ou do dono conforme as labels; testes-aprovados só após a frase do dono, via bb decisao.
5. Confira merge e liberação da posse. Se precisar liberar manualmente, use `bb liberar N` na pasta da sessão.

## Pare e pergunte quando

Critério/RN for ambíguo ou o teste exigir decisão não tomada. Exponha a dúvida antes de codificar.

## Nunca

Escreva implementação, faça teste que passa sem ela ou altere teste existente sem aprovação prevista no processo.

## Pronto quando

PR de teste aprovado e mesclado no épico; tarefas podem receber suas branches pelo botão Criar branches.
