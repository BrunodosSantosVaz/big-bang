---
name: bb-entrevista-produto
description: Use em F1 da Fundação para entrevistar o dono sobre o sistema, escrever PRODUTO.md e definir o nível ASVS. Não escolhe stack.
---

# Entrevista do produto

## Quando usar

Em F1, após F0, ou para retomar a entrevista incompleta.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/processo/02-fundacao.md`, `.bigbang/modelos/PRODUTO.md` e respostas já registradas.

## Passos

1. Faça no máximo dez perguntas, uma por vez, com opções e espaço para resposta livre. Não repita o que já foi respondido.
2. Cubra objetivo, usuários/quantidade, onde roda, login/perfis, offline, dinheiro/saúde/dados pessoais, integrações,
   orçamento, experiência do dono e prazo do primeiro uso.
3. Registre só respostas confirmadas em `PRODUTO.md`, usando o modelo; destaque pendências e contradições.
4. Proponha ASVS L1 para ferramenta interna sem dado sensível; com dado pessoal ou dinheiro, L2 é obrigatório.
   Explique o motivo e registre em `bigbang.toml` após aprovação.
5. Mostre o documento, peça aprovação e leve ao PR de F1; registre as palavras do dono antes de mesclar.

## Pare e pergunte quando

Respostas se contradisserem ou faltarem dados para classificar o risco. Não resolva a contradição sozinho.

## Nunca

Sugira stack nesta etapa, invente regras de negócio ou registre aprovação não dada.

## Pronto quando

`PRODUTO.md` e nível ASVS aprovados, com a decisão registrada no PR de F1.
