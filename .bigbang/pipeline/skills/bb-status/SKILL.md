---
name: bb-status
description: Use para como está o projeto ou pedido de status. Lê o quadro único, as travas, as flags e os achados de segurança e resume o que espera pelo dono, sem alterar estado.
---

# Status do projeto (v3)

## Quando usar

Para consultar o andamento. Não serve para iniciar sprint, recuperar posse nem corrigir achados.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/pipeline/process/board.md` e `bigbang.toml`.

## Passos

1. Rode `bb board show` e `bb flag list`, que só leem. Se faltar configuração ou acesso, explique com precisão o
   limite da consulta.
2. Resuma por estado do quadro. Destaque:
   - o que espera o dono (decisões de backlog, refinamento, seleção, homologação e produção);
   - cartões em Rejected ou com `blocked`, `stale` ou `on-hold`;
   - flags vencidas ou ligadas há muito tempo;
   - achados de segurança abertos.
3. Separe a evidência atual da inferência e mostre os próximos passos, sem executá-los por causa do pedido de status.

## Pare e pergunte quando

Faltar dado para responder com segurança. Erro de leitura não significa quadro vazio.

## Nunca

Altere arquivo, label, trava, issue, PR, segredo, configuração ou ambiente; não reconcilie o quadro nesta consulta.

## Pronto quando

O resumo está fiel, com as pendências do dono e as limitações de leitura explícitas, e nada foi alterado.
