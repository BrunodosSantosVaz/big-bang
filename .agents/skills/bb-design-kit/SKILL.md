---
name: bb-design-kit
description: Use em F3 da Fundação para criar identidade, tokens, componentes e protótipo navegável das telas principais, com aprovação do dono e acessibilidade AA.
---
<!-- Gerado pelo Big Bang v0.11.4 a partir de .bigbang/skills/bb-design-kit/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Design kit

## Quando usar

Em F3 se o produto tiver interface. Para protótipo de épico após a Fundação, use `bb-prototipar`.

## Antes de começar

Leia `PRODUTO.md`, `AGENTS.md`, `.bigbang/processo/02-fundacao.md`, `.bigbang/modelos/DESIGN.md` e
`.bigbang/padroes/frontend.md`. Confira stack já escolhida; F3 pode iniciar em paralelo com F2.

## Passos

1. Confirme as preferências de identidade e as três a cinco telas principais. Sem interface, registre F3 como não aplicável
   com concordância do dono, sem criar um front desnecessário.
2. Registre logo SVG, paleta, tipografia, ícones, tokens, componentes e padrões de lista/formulário/detalhe,
   incluindo vazio, erro e carregamento, em `DESIGN.md` e `docs/design/`.
3. Monte protótipo navegável só com tokens e componentes do kit; confira teclado, foco, contraste, rótulos e nível AA.
4. Mostre o protótipo, receba ajustes e itere até aprovação explícita. Feche detalhes dependentes de F2 depois da stack.
5. Abra o PR de F3 e registre a frase do dono antes de mesclar.

## Pare e pergunte quando

Faltar preferência que mude a identidade ou houver incompatibilidade com produto/stack ou acessibilidade.

## Nunca

Use cor ou fonte fora dos tokens, invente aprovação ou entregue imagem estática como protótipo navegável.

## Pronto quando

`DESIGN.md` e protótipo aprovados, ou não aplicabilidade registrada pelo dono.
