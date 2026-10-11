---
name: bb-atualizar
description: Use para atualizar o Big Bang. Confere versão e migração, preserva a camada do projeto e prepara o PR framework/vX.Y.Z para revisão independente; não atualiza dependências do sistema.
---

# Atualizar o Big Bang (v3)

## Quando usar

Para atualizar o framework. Dependências da aplicação seguem `bb-corrigir-bug` ou `bb-nova-tecnologia`.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `bigbang.toml`, `.bigbang/processo/15-atualizacao-do-framework.md` e o MIGRACAO.md da versão alvo.

## Passos

1. Com a árvore limpa, rode `bb update [versão] --dry-run`. Ele baixa o pacote da origem, confere o SHA-256 e a
   atestação de origem e mostra o MIGRACAO.md entre as versões, sem gravar nada.
2. Mostre ao dono o que muda. Se "O que o projeto precisa fazer" não for "Nada.", pergunte e registre a resposta.
   Só com o sim dele use `--confirm-migration`.
3. Rode `bb update [versão]`: ele cria `framework/vX.Y.Z` da `develop`, troca `.bigbang/`, roda `bb generate` e
   `bb verify` da versão nova e abre o PR.
4. Rode os testes do projeto na branch e confira no diff que só mudaram `.bigbang/`, a camada gerada e a versão.
   Faça os passos manuais confirmados em commits seguintes, na mesma branch, e peça a revisão independente.

## Pare e pergunte quando

O MIGRACAO.md pedir ação manual, o hash ou a atestação falhar, alterações do dono conflitarem ou `bb verify` falhar.

## Nunca

Ignore o hash, dispense a atestação sem o dono pedir, altere código ou documentos do projeto sem pedido ou instale
uma versão de origem não confirmada.

## Pronto quando

O PR `framework/vX.Y.Z` está aberto para revisão, com a camada do projeto preservada.
