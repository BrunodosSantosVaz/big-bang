---
name: bb-retrospectiva
description: Use ao fim de cada épico ou sprint para registrar o que funcionou, travou e deve mudar, atualizar a memória do projeto e propor ajustes sustentados por evidências.
---
<!-- Gerado pelo Big Bang v2.0.1 a partir de .bigbang/skills/bb-retrospectiva/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Retrospectiva

## Quando usar

Ao concluir épico ou encerrar sprint; não substitui portões de conclusão/publicação.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/processo/05-sprint.md`, `docs/memoria.md`, issues/PRs e resultados reais da etapa.

## Passos

1. Separe o que funcionou, o que travou e o que mudar, com exemplos/evidências; peça ao dono contexto que só ele tenha.
2. Atualize `docs/memoria.md` com decisões e pegadinhas úteis, preservando entradas válidas; evite narrativa sem ação.
3. Proponha ajuste das skills do projeto sem prefixo bb-. Para problema do framework, abra issue em sua origem
   com reprodução/evidência dentro da autorização; não altere `.bigbang/` ou skills geradas.
4. Confira que nada ficou para trás: a saída da faxina (branches, issues, PRs, posses), o README em dia com a versão
   em produção (DOC-15) e repositórios auxiliares sem uso (proponha arquivar ao dono).
5. Registre melhoria, responsável e próximo passo. Skill encostada é dívida: revise uso real, não acrescente regra universal
   só por hipótese. Leve as mudanças ao PR adequado, sem push direto em branch compartilhada.

## Pare e pergunte quando

A proposta mudar decisão do dono, escopo ou exigir ação externa ainda não autorizada.

## Nunca

Declare sucesso sem evidência, edite skill gerada à mão ou transforme retrospectiva em refatoração não pedida.

## Pronto quando

Registro feito e melhorias encaminhadas, com pendências explícitas.
