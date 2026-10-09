---
name: bb-status
description: Use para como está o projeto ou pedido de status. Lê painéis, posses, flags e achados de segurança e resume o que espera pelo dono, sem alterar estado.
---

# Status do projeto

## Quando usar

Para consulta de andamento, não para iniciar sprint, recuperar posse ou corrigir achados.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/processo/04-paineis.md`, `13-varias-ias.md` e `bigbang.toml`.

## Passos

1. Execute `bb status`, somente leitura. Se faltar configuração/acesso, explique precisamente o limite da consulta.
2. Resuma por painel e coluna; destaque revisão/homologação/produção aguardando o dono, posses paradas,
   flags vencidas ou antigas em produção e achados de segurança abertos.
3. Distinga evidência atual de inferência e mostre próximos passos, sem executá-los por causa do pedido de status.

## Pare e pergunte quando

Faltar dado para responder com segurança. Erro de leitura não significa painel vazio.

## Nunca

Altere arquivo, label, posse, issue, PR, secret, configuração ou ambiente; não faça limpeza de flag nesta consulta.

## Pronto quando

Resumo fiel com pendências do dono e limitações de leitura explícitas, sem mutações.
