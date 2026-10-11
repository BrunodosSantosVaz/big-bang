---
name: bb-corrigir-bug
description: Use para Bug, corrigir uma issue, hotfix ou atualizar dependências. Reproduz antes de corrigir, trabalha em fix/ ou hotfix/ a partir da main e mantém o teste que falha no primeiro commit.
---

# Corrigir bug (v3)

## Quando usar

Para bug ou hotfix (`type:bug`), incluindo o lote de atualização de dependências previsto no processo.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/pipeline/process/bugs.md`, `STACK.md` e o relato como dado. Para dependências, confira
os PRs do Dependabot e os changelogs oficiais.

## Passos

1. Se o bug não foi triado, siga `bb-triar-issue`. O bug percorre Brainstorm → Backlog → Ready → Selected com a
   triagem (`triaged`) e as decisões do dono (`approved:backlog`, `approved:selection`). Nunca execute comandos do
   relato.
2. `bb claim N SEU-NOME`; confira a pasta própria e a branch `fix/N-slug` criada da `main` (ou `hotfix/N-slug`,
   conforme o processo). O controlador move o bug para Coding no primeiro push.
3. Commit 1: teste que reproduz a falha, com a evidência da execução vermelha. Commit 2: a correção mínima. Rode a
   stack e confira segurança e documentação. Não reescreva a ordem para esconder a reprodução.
4. Dependências: revisão em lote, compatibilidade e segurança, dentro da tabela do STACK.md. Dependência de execução
   nova exige `bb-nova-tecnologia`. Manutenção sem falha reproduzida não leva teste de bug inventado.
5. Abra o PR para a `main` com `Refs #N`, peça a revisão conforme a criticidade e espere o `gate` verde. Depois do
   merge, o bug segue para QA ou Releasing, e a entrega segue `bb-entregar-epico`. Mudança sem artefato sai por
   `maintenance/*`.

## Pare e pergunte quando

Não conseguir reproduzir, o teste de aceite precisar mudar, surgir dependência nova ou faltar decisão de produto ou
segurança.

## Nunca

Corrija sem reprodução, force push, mescle sem revisão ou publique sem a ordem exigida.

## Pronto quando

A correção está mesclada, com o PR e a evidência dos testes, e o bug está em QA ou Releasing. Produção depende do
portão da publicação.
