# ADR-0006: CI do próprio Big Bang

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

O repositório do Big Bang é público e é, ao mesmo tempo, o template de todo sistema novo. A CI dele precisa rodar os
testes (`unittest`), o `shellcheck` dos scripts Bash, a checagem de Markdown e links, e o Gitleaks — sem nunca rodar
num sistema criado a partir do template, e seguindo as mesmas regras que o framework impõe aos workflows gerados
(SEG-18): actions por SHA, runner fixo, permissões mínimas.

## Fatores de decisão

- Mesmas regras de esteira que o Big Bang cobra dos projetos.
- Ferramentas fixadas por versão e hash, sem `latest`.
- O mínimo de actions de terceiros.

## Opções consideradas

1. Actions oficiais (`actions/checkout`, `actions/setup-python`) fixadas por SHA; `shellcheck` do próprio runner;
   checagem de Markdown e links em Python (biblioteca padrão), como teste `unittest`; Gitleaks baixado da Release
   oficial com o SHA-256 conferido.
2. Actions de terceiros para cada ferramenta (markdownlint, lychee, gitleaks-action).

## Decisão e justificativa

Escolhida: **opção 1**.

- **Escopo:** todos os jobs têm `if: github.repository == 'BrunodosSantosVaz/big-bang'`; a Fundação (F5) remove os
  workflows `bb-framework-*` do projeto.
- **Actions fixadas** (consultadas em 2026-10-03): `actions/checkout` v7.0.1
  (`3d3c42e5aac5ba805825da76410c181273ba90b1`) e `actions/setup-python` v7.0.0
  (`5fda3b95a4ea91299a34e894583c3862153e4b97`).
- **Runner:** `ubuntu-24.04`.
- **Gitleaks:** v8.30.1, binário `gitleaks_8.30.1_linux_x64.tar.gz` com SHA-256
  `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`, varrendo o histórico completo. Evita a
  `gitleaks-action`, que exige licença em contas de organização e acrescenta uma action de terceiro.
- **Markdown e links:** teste em Python que confere blocos de código fechados e que todo link relativo (arquivo e
  âncora) existe. Links externos não são checados na CI (dependeriam de rede e seriam instáveis, contra TST-04). Os
  modelos em `.bigbang/modelos/` ficam fora da checagem de links, porque seus links são relativos ao destino no projeto.
- **Regras dos workflows:** um teste reprova workflow com action sem SHA completo, sem comentário de versão, com
  runner `*-latest`, sem `permissions:` no topo, com `pull_request_target` ou com job sem a restrição de repositório.

## Consequências

### Positivas

- O Big Bang cumpre as próprias regras desde o primeiro commit.
- Nenhuma ferramenta nova para instalar localmente além de Python (o `shellcheck` é opcional fora da CI).

### Negativas

- Atualizar versões e SHAs é manual (com o Dependabot de actions a partir do E4) e o hash do Gitleaks é atualizado à
  mão, conferindo o arquivo de checksums da Release oficial.

## Referências

- Especificação, seções 0.2 (itens 6 e 8), 5.2, 14.1 e 17 (E1).
- Gitleaks: https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1
