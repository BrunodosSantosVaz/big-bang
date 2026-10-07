# Entrega do framework 1.5.0

Tarefa [#181](https://github.com/BrunodosSantosVaz/big-bang/issues/181), critérios CA-6 e CA-11 do
[épico #174](https://github.com/BrunodosSantosVaz/big-bang/issues/174). O framework segue seu processo leve;
a Fundação e a esteira completa do sistema consumidor não se aplicam ao próprio Big Bang.

## Conteúdo e rastreabilidade

| Entrega | Decisão e documentação | Implementação e testes |
| --- | --- | --- |
| Catálogo de alvos/artefatos e compatibilidade | [ADR-0016](decisoes/ADR-0016-deploy-multiplataforma.md), [contrato](../esteira/perfis/deploy/README.md) | #175 / PR #182; `test_deploy_catalog.py` |
| Actions, credenciais e acesso conforme o alvo | ADR-0016 e contrato de deploy | #176 / PR #185; `test_deploy_actions.py`, `test_deploy.py` |
| Flash: teste antes, execução seletiva depois | [ADR-0017](decisoes/ADR-0017-modo-flash.md), [contrato Flash](../processo/17-flash.md) | #183 / PR #184; `test_flash.py`, `test_flash_scripts.py`, `test_decisao_revisao.py` |
| Tsuru existente, digest e migração comprovada | [ADR-0018](decisoes/ADR-0018-alvo-tsuru.md), [pesquisa/runbook](deploy-tsuru.md) | #178 / PR #186; `test_tsuru.py`, `test_tsuru_scripts.py` |
| SQLite, migração na inicialização e readiness | [ADR-0019](decisoes/ADR-0019-tsuru-migracao-na-inicializacao.md), [runbook](deploy-tsuru.md#sqlite-e-migração-na-inicialização) | #187 / PR #188; `test_tsuru.py` |
| Pacote, notas e atualização oficial | [ADR-0014](decisoes/ADR-0014-pacote-e-atualizacao.md), [migração](../MIGRACAO.md) | `test_pacote.py`, `test_atualizar.py`, `test_release_framework.py` |

Não há RN de um sistema de negócio, nova API pública do jogo, novo dado pessoal nem alteração de frontend
nesta tarefa. A arquitetura do framework foi registrada nos ADRs; o runbook documenta instalação, operação,
falha, saúde e rollback do adaptador. README, changelog, migração, VERSION, arquivos gerados e CHECKSUMS
acompanham a versão. A CI completa inclui Python 3.11/3.13, Docker real, ShellCheck e Gitleaks.

## Ordem da publicação

1. Concluir as tarefas autorizadas desta versão, incluindo eventuais correções do piloto, com revisão independente
   e CI completa do SHA exato. A #187 / PR #188 foi mesclada na `develop` em 2026-10-07T02:46:29Z, commit
   `82e28c645e7cd83145b1e500d144c08f6c481a9a`, e integrada nesta preparação. Sua revisão e a
   [CI completa](https://github.com/BrunodosSantosVaz/big-bang/actions/runs/37418098724) validaram o HEAD
   `43cee9ceaccfda58bc0f17916e0e6f8d2df1c460`; a integração ainda exige revisão e CI próprias do novo SHA.
   Não publicar um pacote com uma tarefa obrigatória ainda pendente.
2. Integrar os PRs na `develop` e revisar o PR `develop` → `main`; publicar a tag `v1.5.0` somente depois do merge
   e dos checks da `main`. A tag deve apontar para o commit validado cuja `.bigbang/VERSION` é `1.5.0`.
3. A Action **Release do Big Bang** confere ancestralidade/VERSION/CHECKSUMS, gera o pacote reprodutível e
   `.sha256`, atesta a origem e publica as notas da seção `[1.5.0]` de `MIGRACAO.md`.
4. Conferir run e assets da Release: `bigbang-v1.5.0.tar.gz`, `bigbang-v1.5.0.tar.gz.sha256` e atestação.
   Só a existência da tag não comprova que o pacote foi publicado corretamente.

## Atualização do Snake e limites da evidência

Após a Release, atualizar o consumidor por `bb atualizar 1.5.0`, conferir o hash/atestação e revisar seu PR
próprio de framework. Mudar alvo ou modo por decisão registrada em ADR e `bb gerar`, sem editar `.bigbang/`
manualmente. O [runbook](deploy-tsuru.md) orienta os recursos e credenciais separados por ambiente.

CA-6 requer evidência no Snake: URL real dentro do Tsuru, SHA, digest de origem, eventos e execução da migração
por job ou inicialização comprovada pelo sistema, saúde/readiness, smoke e operação do jogo/API.
`TSURU_MIGRACAO=job` é o padrão; `inicializacao` é a opção para SQLite persistente, com pré-checagem
`migration=pending`, migração antes da porta e uma réplica permanente, admitindo rollout transitório no mesmo
volume. A plataforma Node.js é preparação separada do servidor; esta versão entrega OCI por digest, sem upload
de fontes. Os testes do framework comprovam o adaptador e suas recusas, não a
homologação ou a publicação do jogo. Esta tarefa documental não registra uma produção inexistente.

AWS/paas, alvo personalizado e formatos de deploy por hashes permanecem reservas. O perfil compilado já
implementado conserva a promoção de binários por hashes; isso não anuncia um novo formato de deploy.
