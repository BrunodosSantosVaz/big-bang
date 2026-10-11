---
name: bb-documentar-epico
description: Use para a sub-issue de documentação de um épico. Confere o checklist documental e a rastreabilidade, atualiza os documentos necessários e prepara o rascunho do changelog.
---

# Documentar épico (v3)

## Quando usar

Para a sub-issue `type:docs` do épico, a última, depois das implementações pertinentes.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/padroes/documentacao.md`, `.bigbang/pipeline/process/execution.md`, o épico, as RNs e
os PRs mesclados das sub-issues.

## Passos

1. `bb claim N SEU-NOME`; trabalhe na pasta confirmada, na branch `docs/N-slug` criada da `develop`.
2. Aplique o checklist aos documentos realmente afetados: RN, C4/arc42, ADR, contratos, manual, runbook, memória e
   README. Marque como não aplicável, com motivo, o que não se aplica; não crie documento vazio. O README é sempre
   afetado. Público: apresentação breve, links atualizados e guias completos na Wiki. Privado: confira Estado
   atual, Recursos, Instalação, uso e imagem real contra o modelo (DOC-15). Se o épico entra com a flag desligada,
   documente o que muda quando ela for ligada.
3. Confira critério → RN → teste → tarefa/PR e prepare o rascunho do changelog em português com o que foi entregue.
4. Rode as verificações documentais e `bb verify`; abra o PR para a `develop` com `Refs #N`, peça a revisão e
   acompanhe o merge e a liberação da trava.

## Pare e pergunte quando

Um documento contradisser uma decisão aprovada ou faltar evidência de comportamento. Não descreva intenção como
entrega.

## Nunca

Mude produto, stack ou design sem pedido, invente rastreabilidade ou declare pronto um manual não verificável.

## Pronto quando

O checklist e a rastreabilidade foram conferidos e o PR documental foi mesclado, com a trava liberada; com isso
todas as sub-issues do épico estão fechadas.
