---
name: bb-codar-tarefa
description: Use para próxima tarefa ou codar uma issue de implementação. Confirma posse e worktree, libera as marcas da tarefa, implementa, testa e pede revisão independente do PR.
---
<!-- Gerado pelo Big Bang v1.5.0 a partir de .bigbang/skills/bb-codar-tarefa/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Codar tarefa

## Quando usar

Para tarefa de épico livre e desbloqueada. Para bug/hotfix, use `bb-corrigir-bug`.

## Antes de começar

Leia `AGENTS.md`, padrões aplicáveis em `.bigbang/padroes/`, tarefa/épico, testes de aceite,
`STACK.md` e `.bigbang/processo/06-execucao.md`, `08-revisao.md`, `13-varias-ias.md`.

## Passos

1. `bb assumir N SEU-NOME`; espere sucesso e entre na pasta própria informada. Se perder a disputa ou faltar branch,
   não programe. Não use forcar sem ordem explícita do dono e posse vencida.
2. Rode `bb aceite liberar N`, única alteração permitida nas marcas de pendente desta tarefa. Não altere cenários.
3. Implemente o escopo, incluindo unidade/integração, documentação tocada e evidências SEG-IA aplicáveis. Se a
   tarefa muda o que o usuário vê, instala ou configura, atualize o README.md no mesmo PR (DOC-15).
4. Consulte `projeto.modo`. No padrão, execute os comandos completos da stack. No Flash, escreva os testes antes
   do código e, após concluir as alterações, use `bb testes --base <base>` para uma rodada dos afetados; prefira a
   CI do mesmo commit como evidência e não repita a suíte inteira sem mudança/falha. Mudanças estruturais,
   produção e major/minor exigem tudo. Lint, tipos, arquitetura, scanners e `bb verificar` continuam obrigatórios.
5. Commit Conventional Commits; abra PR para a branch do épico com alegações verificáveis e resultados.
   Acione `bb-revisor-pr` em contexto limpo, ou revisão humana conforme labels/diff; não revise o próprio raciocínio.
6. Se aprovado pelo revisor e permitido, `bb revisao aprovar PR --relatorio ARQUIVO`; acompanhe Mesclar PR e CI.
   Após merge, confira liberação automática; se necessário `bb liberar N` na pasta da sessão.

## Pare e pergunte quando

Teste de aceite parecer errado (mostre evidência) ou precisar de dependência nova (siga `bb-nova-tecnologia`).
Portão recusado/CI vermelha exige diagnóstico, nunca bypass.

## Nunca

Altere `tests/aceite/` fora de bb aceite liberar, enfraqueça teste/check ou refatore fora do escopo.

## Pronto quando

PR revisado e mesclado, posse liberada e evidências/documentação atualizadas. Libere a posse (`bb liberar N`) **na pasta da tarefa** antes de removê-la com `git worktree remove`: o recibo da
posse fica nos metadados dessa pasta.
