---
name: bb-codar-tarefa
description: Use para próxima tarefa ou codar uma issue de implementação. Adquire a trava com bb claim, trabalha na pasta própria a partir da develop, implementa, testa e pede revisão independente do PR.
---

# Codar tarefa (v3)

## Quando usar

Para uma tarefa (`type:task`) desbloqueada de um épico em In Progress. Para bug ou hotfix, use `bb-corrigir-bug`.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, os padrões aplicáveis em `.bigbang/padroes/`, a tarefa e o épico, os testes de aceite, `STACK.md`
e `.bigbang/pipeline/process/execution.md`.

## Passos

1. `bb claim N SEU-NOME`. Espere a confirmação da trava (`refs/bigbang/locks/issue-N`) e entre na pasta própria
   informada, na branch `feature/N-slug` criada da `develop`. Se perder a disputa, não programe. Retomar posse
   vencida de outro só com a ordem do dono (`--force-claim`). Em sessões longas, renove com `bb renew N`.
2. Rode `bb acceptance unpend N`, a única alteração permitida nas marcas de pendente desta tarefa. Não altere cenários.
3. Implemente o escopo, com unidade e integração, a documentação tocada e as evidências SEG-IA aplicáveis. Se o
   épico tem `flag:required`, o comportamento novo fica atrás da flag dele (desligada por padrão). Se a tarefa muda
   o que o usuário vê, instala ou configura, atualize o README.md no mesmo PR (DOC-15).
4. Testes: no normal, rode os comandos completos da stack. No Flash e no autonomous, escreva os testes antes e,
   depois do código, rode `bb test --base develop` para uma rodada dos afetados. Lint, tipos, scanners e
   `bb verify` continuam obrigatórios.
5. Commit em Conventional Commits; abra o PR para a `develop` com `Refs #N` (nunca `Closes`). O controlador move a
   tarefa para In Review. Acione `bb-revisor-pr` com contexto limpo, ou a revisão do dono conforme `review:*`.
6. Com a revisão aprovada e o check `gate` verde no SHA exato, `bb review approve PR --report ARQUIVO` e
   `bb merge PR` (botão *Merge PR*). No merge, o controlador fecha a tarefa e libera a trava. Se ela ficar, rode
   `bb unclaim N` na pasta da tarefa e só então remova a pasta com `git worktree remove`.

## Pare e pergunte quando

Um teste de aceite parecer errado (mostre a evidência) ou precisar de dependência nova (siga `bb-nova-tecnologia`).
Portão recusado ou CI vermelha pedem diagnóstico, nunca contorno.

## Nunca

Programe sem a trava confirmada, altere `tests/aceite/` fora do `bb acceptance unpend`, enfraqueça teste ou check,
ligue a flag do épico sem a decisão do dono ou refatore fora do escopo.

## Pronto quando

O PR está revisado e mesclado na `develop`, a tarefa está em Done, a posse foi liberada e as evidências e a
documentação estão atualizadas.
