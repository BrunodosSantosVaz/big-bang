# ADR-0003: Branch de épico (`epico/*`)

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

O dono decidiu que a release e a homologação são **por épico**. No processo anterior (CNABLens), tarefas nasciam da
`develop` e se acumulavam lá; com vários épicos em andamento, a `develop` misturava trabalho de épicos diferentes e uma
release não conseguia levar só um épico sem feature flag.

## Fatores de decisão

- Release por épico, sem misturar épicos.
- Paralelismo entre IAs dentro do mesmo épico.
- Histórico completo (teste antes, tarefas, documentação) preservado.
- Feature flag só quando um épico depende de outro ainda não publicado.

## Opções consideradas

1. Uma branch `epico/<n>-<slug>` a partir da `develop`, que acumula teste, tarefas e documentação do épico.
2. Tarefas direto na `develop`, com feature flag para tudo que não está pronto.
3. Uma branch longa por tarefa, integrada direto na release.

## Decisão e justificativa

Escolhida: **opção 1**. Teste, tarefas e documentação vivem num `epico/*` e são mesclados com merge commit. A
`develop` nunca recebe código de artefato não publicado — **invariante**: *a `develop` nunca contém mudança nos
caminhos do artefato que não esteja em produção* (testada pela esteira). Assim a release a partir da `main` leva
exatamente o épico integrado, e *Publicar sem release* sempre pode avançar a `main` até a `develop`.

## Consequências

### Positivas

- Release por épico sem feature flag (salvo dependência entre épicos).
- Cada épico pode ser reprovado e corrigido sem afetar os outros.

### Negativas

- Épicos paralelos podem conflitar entre si. Tratamento: depois de cada publicação, a esteira devolve a `main` para
  a `develop` e para cada `epico/*` aberto; conflito vira a label `conflito` e um PR `sync/<épico>`.
- Mais branches abertas ao mesmo tempo; a esteira apaga as temporárias depois da publicação, com travas.

## Referências

- Especificação, seções 11.5 e 11.6, e Apêndice A, item 1.
