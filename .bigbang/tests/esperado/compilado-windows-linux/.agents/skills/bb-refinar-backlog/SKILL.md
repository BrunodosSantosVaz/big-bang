---
name: bb-refinar-backlog
description: Use para Ideia, vamos refinar o backlog ou refinar uma issue. Conduz um épico por vez até a Definition of Ready e registra refinamento-aprovado somente após decisão do dono.
---
<!-- Gerado pelo Big Bang v0.10.1 a partir de .bigbang/skills/bb-refinar-backlog/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Refinar backlog

## Quando usar

Ao registrar ideia ou refinar épico. Não inicia implementação.

## Antes de começar

Leia `AGENTS.md`, `PRODUTO.md`, RNs existentes, `.bigbang/processo/03-planejamento.md` e os painéis com `bb status`.

## Passos

1. Ideia: confira duplicata e crie épico em Brainstorm com problema em uma a três frases; pergunte se vai para Backlog.
2. Refinamento: liste Backlog e Backlog Refinement, peça ordem e trabalhe um épico por vez, com perguntas individuais.
3. Monte problema/objetivo, escopo dentro/fora, RNs confirmadas, critérios CA-n em Dado/Quando/Então e tarefas do tamanho
   de um PR com dependências; tarefas que tocam os mesmos arquivos devem ser dependentes.
4. Responda com o dono às cinco perguntas do formulário; faça STRIDE se sensível e marque revisao-humana se crítico
   (dinheiro, dados pessoais, autenticação). Confira a Definition of Ready inteira, não apenas as labels.
5. Mostre resumo e espere aprovação. Só então `bb decisao refinamento-aprovado N --frase "palavras do dono"`.
   Ofereça `bb-prototipar` se com-prototipo; caso contrário, siga ao próximo épico aprovado para refinamento.

## Pare e pergunte quando

Qualquer decisão de escopo/RN estiver ausente ou contraditória, inclusive nas cinco respostas do formulário.

## Nunca

Invente RN, crie tarefa sem critério, mova a ideia para Backlog sem decisão ou ponha label de aprovação diretamente.

## Pronto quando

Épico cumpre Definition of Ready e tem refinamento-aprovado com frase registrada; protótipo ainda pode estar pendente.
