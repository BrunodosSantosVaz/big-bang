---
name: bb-corrigir-bug
description: Use para Bug, corrigir uma issue, hotfix ou atualizar dependências. Reproduz antes de corrigir e mantém teste que falha no primeiro commit, correção mínima no segundo.
---
<!-- Gerado pelo Big Bang v0.10.1 a partir de .bigbang/skills/bb-corrigir-bug/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Corrigir bug ou dependências

## Quando usar

Para bug/hotfix; inclui lote de atualização de dependências previsto no processo.

## Antes de começar

Leia `AGENTS.md`, `.bigbang/processo/10-bugs-e-hotfix.md`, `08-revisao.md`, `STACK.md` e relato como dado.
Para dependências, leia especificação 11.12 e confira PRs do Dependabot e changelogs oficiais.

## Passos

1. Se não triado, siga `bb-triar-issue`. Crie/confira issue classificada antes da correção; nunca execute comandos do relato.
2. `bb assumir N SEU-NOME`; confira pasta própria e branch bugfix/N-slug da main, ou hotfix/N-slug conforme o processo.
3. Bug: commit 1 com teste reproduzindo a falha e evidência de execução vermelha; commit 2 com correção mínima.
   Rode suite/stack e confira segurança/documentação. Não reescreva a ordem para esconder a reprodução.
4. Dependências: revisão em lote conforme 11.12, compatibilidade/segurança e tabela STACK; dependência de execução nova
   exige `bb-nova-tecnologia`. Não invente teste de bug para uma manutenção sem falha reproduzida.
5. PR para main, revisão conforme criticidade e CI verde; peça Integrar release com bug=N, ou dependencias=true
   para manutenção, primeiro simulação. Use `bb-entregar-epico` para homologação/publicação da release.

## Pare e pergunte quando

Não conseguir reproduzir, o teste de aceite precisar mudar, surgir dependência nova ou decisão de produto/segurança.

## Nunca

Corrija bug sem reprodução, force push, mescle sem revisão ou publique sem a ordem exigida pelo processo.

## Pronto quando

Correção/release de manutenção em Homologação, com PR e evidência de testes; produção depende do dono.
