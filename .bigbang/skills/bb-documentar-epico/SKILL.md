---
name: bb-documentar-epico
description: Use para a issue documentacao de um épico. Confere checklist documental e rastreabilidade, atualiza os documentos necessários e prepara o rascunho do changelog.
---

# Documentar épico

## Quando usar

Para tarefa documental do épico, depois das implementações pertinentes.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/padroes/documentacao.md`, `.bigbang/processo/06-execucao.md`,
especificação seção 9.4, épico, RNs e PRs mesclados.

## Passos

1. `bb assumir N SEU-NOME`; trabalhe na pasta confirmada e branch docs/N-slug do épico.
2. Aplique checklist 9.4 aos documentos realmente afetados: RN, C4/arc42, ADR, contratos, manual, runbook,
   memória e README. Marque não aplicável com motivo; não crie documento vazio para satisfazer checklist.
   O README é sempre afetado. Público: apresentação breve, links atualizados e guias completos na Wiki.
   Privado: confira Estado atual, Recursos, Instalação, uso e imagem real contra o modelo do README (DOC-15).
3. Confira critério → RN → teste → tarefa/PR e prepare rascunho de changelog em português com o que foi entregue.
4. Rode verificações documentais e `bb verificar`; abra PR para o épico, peça revisão e acompanhe merge/liberação.

## Pare e pergunte quando

Documento contradisser uma decisão aprovada ou faltar evidência de comportamento. Não descreva intenção como entrega.

## Nunca

Mude produto/stack/design sem pedido, invente rastreabilidade ou declare pronto um manual não verificável.

## Pronto quando

Checklist/rastreabilidade conferidos e PR documental mesclado, com posse liberada.
