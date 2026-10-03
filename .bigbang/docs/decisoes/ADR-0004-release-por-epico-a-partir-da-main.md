# ADR-0004: Release por épico a partir da `main`

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

O dono decidiu (decisões 5 e 6) que a release e a homologação acontecem por épico pronto. O Manual Projeto-GIT e o
processo do CNABLens divergiam no gatilho de release (sprint versus versão informada) e no tipo de merge.

## Fatores de decisão

- O artefato homologado é exatamente o publicado.
- Uma release leva uma unidade (um épico ou um bug), para a homologação ser objetiva.
- Bugs e hotfixes não podem esperar épicos em andamento.

## Opções consideradas

1. `release/x.y.z` criada a partir da `main`, recebendo o `epico/…` (ou o `bugfix`/`hotfix`) com `--no-ff`.
2. `release/x.y.z` criada a partir da `develop` (modelo GitFlow clássico).
3. Release por sprint, com tudo que estiver pronto.

## Decisão e justificativa

Escolhida: **opção 1**. Com a invariante do ADR-0003, a `main` é sempre "produção atual"; criar a release a partir
dela e mesclar só o épico garante que a candidata contém exatamente esse épico. A versão sai dos títulos dos PRs
(Conventional Commits). A release é disparada pela conclusão do épico, não pela sprint (que tem duração livre e não é
versão). Merge commit em todas as branches de integração, nunca squash.

Bugs seguem o mesmo caminho: `bugfix/*` nasce da `main` e entra numa `release/x.y.z` própria (sobe o último número).

## Consequências

### Positivas

- Homologação por épico, uma vez, sobre o artefato que será publicado.
- Hotfix nunca espera épico.

### Negativas

- Dois épicos prontos ao mesmo tempo geram duas releases em sequência; a segunda precisa receber a `main` atualizada
  (devolução automática).
- Épicos que dependem de outro não publicado precisam de feature flag (decisão 5).

## Referências

- Especificação, seções 11.5, 11.6, 11.10 e 11.12, e Apêndice A, itens 4 e 12.
