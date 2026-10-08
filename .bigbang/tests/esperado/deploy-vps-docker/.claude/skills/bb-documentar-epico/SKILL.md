---
name: bb-documentar-epico
description: Use para a issue documentacao de um épico. Confere checklist documental e rastreabilidade, atualiza os documentos necessários e prepara o rascunho do changelog.
---
<!-- Gerado pelo Big Bang v1.5.4 a partir de .bigbang/skills/bb-documentar-epico/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Documentar épico

## Quando usar

Para tarefa documental do épico, depois das implementações pertinentes.

## Antes de começar

Leia `AGENTS.md`, `.bigbang/padroes/documentacao.md`, `.bigbang/processo/06-execucao.md`,
especificação seção 9.4, épico, RNs e PRs mesclados.

## Passos

1. `bb assumir N SEU-NOME`; trabalhe na pasta confirmada e branch docs/N-slug do épico.
2. Aplique checklist 9.4 aos documentos realmente afetados: RN, C4/arc42, ADR, contratos, manual, runbook,
   memória e README. Marque não aplicável com motivo; não crie documento vazio para satisfazer checklist.
   O README é sempre afetado: reescreva Estado atual e Recursos com o que o épico entrega, confira Instalação, uso
   e a imagem real (print atualizado em docs/imagens/) contra o modelo `.bigbang/modelos/README-sistema.md` (DOC-15).
3. Confira critério → RN → teste → tarefa/PR e prepare rascunho de changelog em português com o que foi entregue.
4. Rode verificações documentais e `bb verificar`; abra PR para o épico, peça revisão e acompanhe merge/liberação.

## Pare e pergunte quando

Documento contradisser uma decisão aprovada ou faltar evidência de comportamento. Não descreva intenção como entrega.

## Nunca

Mude produto/stack/design sem pedido, invente rastreabilidade ou declare pronto um manual não verificável.

## Pronto quando

Checklist/rastreabilidade conferidos e PR documental mesclado, com posse liberada.
