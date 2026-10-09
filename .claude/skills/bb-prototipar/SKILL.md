---
name: bb-prototipar
description: Use para vamos montar o protótipo de um épico com-prototipo cujo refinamento já foi aprovado. Itera um protótipo navegável até aprovação do dono.
---
<!-- Gerado pelo Big Bang v2.0.0 a partir de .bigbang/skills/bb-prototipar/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Prototipar épico

## Quando usar

Para protótipo de épico; para design da Fundação, use `bb-design-kit`.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `DESIGN.md`, épico/critérios, `.bigbang/processo/03-planejamento.md` e `.bigbang/padroes/frontend.md`.
Confirme com-prototipo e refinamento-aprovado.

## Passos

1. Monte protótipo navegável em `docs/prototipos/N/`, cobrindo telas/critérios do épico com tokens/componentes do kit.
2. Ligue o protótipo no épico; mostre fluxos e estados, confira acessibilidade e itere com os comentários do dono.
3. Peça aprovação; com a resposta explícita, `bb decisao prototipo-aprovado N --frase "palavras do dono"`.
4. Incorpore o protótipo como referência dos critérios; confira a movimentação para Próxima sprint, sem iniciar código.

## Pare e pergunte quando

O pedido mudar escopo/RN ou exigir token/componente inexistente. Retome o refinamento ou design, com decisão do dono.

## Nunca

Invente aprovação, ignore reprovação ou use cores/fontes fora dos tokens.

## Pronto quando

Protótipo aprovado e ligado aos critérios; épico em Próxima sprint.
