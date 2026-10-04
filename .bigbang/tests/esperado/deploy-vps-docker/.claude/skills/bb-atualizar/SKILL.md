---
name: bb-atualizar
description: Use para atualizar o Big Bang. Confere versão e migração, preserva a camada do projeto e prepara PR framework/vX.Y.Z para revisão humana; não atualiza dependências do sistema.
---
<!-- Gerado pelo Big Bang v0.10.0 a partir de .bigbang/skills/bb-atualizar/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Atualizar Big Bang

## Quando usar

Para atualizar o framework; dependências da aplicação seguem `bb-corrigir-bug` ou `bb-nova-tecnologia`.

## Antes de começar

Leia `AGENTS.md`, `bigbang.toml`, `.bigbang/processo/15-atualizacao-do-framework.md` e notas/MIGRACAO.md da versão alvo.

## Passos

1. Confira origem/versão atuais, árvore de trabalho e versão alvo publicada; mostre passos manuais da migração.
2. Siga a seção 5.7 da especificação via `bb atualizar [versao]`: tarball e SHA-256 da origem, hash obrigatório,
   branch framework/vX.Y.Z da develop, troca só do framework e atualização de bigbang.versao.
3. Se o CLI ainda não oferecer atualizar (entrega prevista no E10), pare com mensagem explícita e indique a pendência;
   não improvise download/substituição manual ou declare uma atualização inexistente.
4. Rode `bb gerar --simular`, mostre diff, `bb gerar`, `bb verificar` e testes; confira preservação da camada do projeto.
5. Abra PR para develop com revisao-humana e resumo da migração/diff/evidências.

## Pare e pergunte quando

MIGRACAO.md pedir ação manual, hash falhar, alterações do dono conflitarem ou comando/pacote ainda não existir.

## Nunca

Ignore hash, altere código/documentos do projeto sem pedido ou instale versão de origem não confirmada.

## Pronto quando

PR framework/vX.Y.Z aberto para revisão humana, com projeto preservado; sem CLI disponível, pendência informada.
