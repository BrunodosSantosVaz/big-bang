---
name: bb-atualizar
description: Use para atualizar o Big Bang. Confere versão e migração, preserva a camada do projeto e prepara PR framework/vX.Y.Z para revisão independente; não atualiza dependências do sistema.
---
<!-- Gerado pelo Big Bang v2.0.0 a partir de .bigbang/skills/bb-atualizar/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Atualizar Big Bang

## Quando usar

Para atualizar o framework; dependências da aplicação seguem `bb-corrigir-bug` ou `bb-nova-tecnologia`.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `bigbang.toml`, `.bigbang/processo/15-atualizacao-do-framework.md` e notas/MIGRACAO.md da versão alvo.

## Passos

Confira o destino documental pela visibilidade, Discussions com primeiro post idempotente, os painéis
públicos após auditoria e Social preview. Preserve configurações do projeto e documentos até confirmar a Wiki.

1. Com a árvore limpa, rode `bb atualizar [versão] --simular`: baixa o pacote da origem, confere o SHA-256 e a
   atestação de origem e mostra o `MIGRACAO.md` entre as versões, sem gravar nada.
2. Mostre ao dono o que muda. Se houver "O que o projeto precisa fazer" diferente de "Nada.", pergunte ao dono e
   registre a resposta dele; só com o sim dele rode com `--confirmo-migracao`.
3. Rode `bb atualizar [versão]`: cria `framework/vX.Y.Z` da `develop`, troca `.bigbang/`, atualiza
   `bigbang.versao`, roda `bb gerar` e `bb verificar` da versão nova e abre o PR com `revisao-humana` no padrão ou `revisao-ia` no Flash.
4. Rode os testes do projeto na branch e confira no diff do PR que só `.bigbang/`, a camada gerada e
   `bigbang.versao` mudaram. Faça os passos manuais confirmados em commits seguintes, na mesma branch.

## Pare e pergunte quando

MIGRACAO.md pedir ação manual, hash ou atestação falhar, alterações do dono conflitarem ou `bb verificar` falhar.

## Nunca

Ignore hash, use `--sem-atestacao` sem o dono pedir, altere código/documentos do projeto sem pedido ou instale versão
de origem não confirmada.

## Pronto quando

PR framework/vX.Y.Z aberto para revisão humana, com a camada do projeto preservada.

No modo Flash, a atualização abre PR com `revisao-ia`: revisão independente e CI completa (estrutura).
Reutilize autorização já dada para passos manuais conhecidos; não repita pedidos de confirmação.
