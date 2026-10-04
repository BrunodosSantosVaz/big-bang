---
name: bb-status
description: Use para como está o projeto ou pedido de status. Lê painéis, posses, flags e achados de segurança e resume o que espera pelo dono, sem alterar estado.
---
<!-- Gerado pelo Big Bang v0.10.0 a partir de .bigbang/skills/bb-status/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Status do projeto

## Quando usar

Para consulta de andamento, não para iniciar sprint, recuperar posse ou corrigir achados.

## Antes de começar

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
