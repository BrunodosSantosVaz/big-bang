# 06 · Execução de um épico

No [modo Flash](17-flash.md), a ordem teste → tarefas permanece. Escreva os testes antes, conclua o código e execute uma rodada dos testes afetados (`bb testes --base <base>`). Não repita a suíte completa por hábito; a CI do mesmo commit serve como evidência. Mudanças estruturais, major/minor e produção exigem tudo.

Ordem fixa: **teste do épico → tarefas → documentação**. Painel: **Execução**.

## 1. Teste do épico (issue `teste-aceite`)

Feito por **uma IA só** (skill `bb-escrever-testes-aceite`), na branch `teste/<n>-<slug>`:

1. `bb assumir <issue> <nome>`.
2. Em `tests/aceite/<n>-<slug>/`, um teste por critério de aceite, com o ID da regra de negócio no nome (por exemplo
   `test_rn0042_blocks_order_without_stock` ou `it("RN-0042 …")`).
3. Cada teste marcado como **pendente da tarefa** que vai implementá-lo (`testes.marca_pendente`; por exemplo
   `xfail(strict=True, reason="#42")` no pytest ou `test.failing` no Jest). A CI fica verde porque a falha é esperada.
4. Cria ou atualiza os arquivos `docs/negocio/regras/RN-*`.
5. PR para o `epico/…`, listando os cenários em português.

**Revisão dos testes:** com `testes-revisao-humana`, espera o dono pôr `testes-aprovados`. Com `testes-revisao-ia`, o
`bb-revisor-pr` confere que cada critério tem teste, que cada teste falharia sem a implementação e que cita uma RN; se
passar, `pr-aprovado`. Aprovado e com CI verde, a automação mescla no `epico/…`.

## 2. Tarefas (issues `task`)

Depois do merge do teste, *Criar branches* cria `feature/<n>-<slug>` a partir do `epico/…` para cada tarefa
desbloqueada (respeitando as dependências). Cada IA (skill `bb-codar-tarefa`):

1. `bb assumir <issue> <nome>` e uma pasta própria (`git worktree`).
2. `bb aceite liberar <tarefa>`: tira a marca de pendente **só** dos testes desta tarefa.
3. Programa até os testes passarem, com testes de unidade e integração próprios.
4. Atualiza a documentação que tocou (RN, API, glossário).
5. Roda os comandos da stack localmente (`[comandos]` do `bigbang.toml`).
6. Abre o PR para o `epico/…` com alegações e evidências, e pede revisão.

## 3. Documentação (issue `documentacao`)

A última do épico (skill `bb-documentar-epico`). *Criar branches* cria `docs/<n>-<slug>` quando todas as tarefas
estão em *Pronto*. Checklist:

- [ ] Regras de negócio novas ou alteradas em `docs/negocio/regras/`
- [ ] Glossário com os termos novos
- [ ] Diagramas C4 e arc42, se a arquitetura mudou
- [ ] Contrato da API, se mudou
- [ ] Inventário LGPD, se há dado pessoal novo
- [ ] Runbook, se a operação mudou
- [ ] Guia de quem usa, se a tela ou o fluxo mudou
- [ ] ADR de cada decisão tomada no épico
- [ ] Rascunho da entrada do `CHANGELOG.md` (a versão é preenchida na integração)
- [ ] `README.md` completo e atual: estado atual, recursos, instalação, uso e uma imagem real do sistema (DOC-15)
- [ ] `docs/operacao/checklist-producao.md` com a verificação de cada item, se o épico mudou algum deles (o
  *Publicar em produção* recusa sem ele; app sem servidor marca os itens de backend como `nao-se-aplica`)

Ela não muda o artefato, mas **o épico só é integrado com ela concluída**.

## Definition of Done (tarefa)

- [ ] Testes de aceite das RNs da tarefa passando, com só as marcas desta tarefa retiradas
- [ ] Testes de unidade e integração da mudança
- [ ] Lint, tipos, arquitetura e segurança verdes
- [ ] Documentação que tocou atualizada
- [ ] Padrões aplicados (citados quando relevante)
- [ ] PR aprovado (`pr-aprovado`) e mesclado na branch do épico
- [ ] Posse liberada

## Testes travados

- A CI reprova PR de tarefa ou documentação que altere, acrescente ou apague linha em `tests/aceite/`, **exceto** a
  retirada das marcas de pendente que referenciam a issue do próprio PR.
- Depois de mesclado, nem o PR de teste altera linha existente sem aprovação.
- Para mudar um teste aceito: a IA comenta no PR por que o teste está errado, com evidência, e o dono põe
  `teste-alterado-aprovado` — sempre, mesmo em épico `testes-revisao-ia`.
- O check *Pendentes* reprova teste ainda marcado como pendente de tarefa já mesclada ou fechada. A marca estrita
  (como `xfail(strict=True)`) já falha sozinha se o teste passar com a marca.

## O que a automação faz sozinha

Cria as branches das tarefas e da documentação, move os cartões, mescla no `epico/…` o PR aprovado e verde (merge
commit), libera a posse quando o PR é mesclado e dispara a integração quando teste, tarefas e documentação estão
mesclados.
