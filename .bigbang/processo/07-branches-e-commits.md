# 07 · Branches, commits e PRs

## Modelo de branches

| Branch | Nasce de | Recebe | Destino |
| --- | --- | --- | --- |
| `main` | — | releases e hotfixes | produção |
| `develop` | `main` | Fundação, épicos `sem-release`, retorno da `main` após cada publicação, atualizações do framework | base dos épicos |
| `epico/<n>-<slug>` | `develop` (criada pelo *Iniciar sprint*) | PRs de teste, tarefas e documentação do épico (merge commit) | `release/x.y.z` (épico com release) ou `develop` (épico `sem-release`) |
| `teste/<n>-<slug>`, `feature/<n>-<slug>`, `docs/<n>-<slug>` | `epico/…` | commits da IA | PR para o `epico/…` |
| `bugfix/<n>-<slug>`, `hotfix/<n>-<slug>` | `main` | commits da correção | PR para a `main` (mesclado via release) |
| `release/x.y.z` | `main` (criada pelo *Integrar release*) | o `epico/…` ou o `bugfix`/`hotfix` | PR para a `main` |
| `fundacao/<n>-<slug>`, `framework/vX.Y.Z` | `develop` | — | PR para a `develop` |
| `sync/<épico>` | `epico/…` | a `main` com o conflito resolvido | PR para o `epico/…` |

`<n>` é o número da issue; `<slug>` é o título em minúsculas, sem acento, com hífen.

### Invariante (testada pela esteira)

**A `develop` nunca contém mudança nos caminhos do artefato que não esteja em produção.** Código de artefato só chega
à `develop` pela volta da `main` depois de publicado. Consequências:

- uma release a partir da `main` leva exatamente o épico (ou o bug) integrado;
- *Publicar sem release* sempre pode avançar a `main` até a `develop`.

Depois de cada publicação, a esteira devolve a `main` para a `develop` e para cada `epico/*` aberto. Se houver
conflito, o épico ganha a label `conflito` e um comentário; uma IA resolve num PR `sync/<épico>`.

### Em repouso

Existem só `main`, `develop` e os `epico/*` em andamento. As demais são apagadas pela esteira no fim, com travas: nome
exato, tag e Release existentes, branch contida na tag e na `main`. **Tags nunca são apagadas nem movidas.**

## Commits

- Em **inglês**, no padrão [Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/):
  `feat(orders): block order without stock`.
- Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`, `chore`, `perf`, `style`, `revert`.
  `!` ou rodapé `BREAKING CHANGE:` para quebra de compatibilidade.
- Pequenos e frequentes. Bug: primeiro o commit com o teste de regressão que falha, depois o da correção.

## PRs

- Uma tarefa = uma branch = um PR.
- Título: prefixo Conventional Commits + descrição em **português**: `feat(pedidos): bloqueia pedido sem estoque`.
  É do título que sai a versão e o changelog.
- Corpo no modelo de PR, com `Refs #<n>` (**nunca** `Closes`: quem fecha as issues é a publicação).
- Seção *Alegações e evidências*: cada afirmação do PR aponta para arquivo:linha ou teste.

## Tipo de merge

**Merge commit** em todas as branches de integração (`epico/*`, `release/*`, `develop`, `main`). **Nunca squash**:
o histórico de cada tarefa e a ordem dos commits de bug (teste antes da correção) precisam ser preservados.

## O que a automação faz sozinha

Cria as branches `epico/*`, `teste/*`, `feature/*`, `docs/*` e `release/*`; mescla os PRs aprovados e verdes; devolve
a `main` às branches abertas; apaga as branches temporárias depois da publicação. O check *Regras do PR* reprova
nome de branch, destino, título ou `Refs` fora do padrão.
