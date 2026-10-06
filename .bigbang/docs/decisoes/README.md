# Decisões do framework (ADRs)

Decisões de arquitetura do próprio Big Bang, no formato [MADR](https://adr.github.io/madr/). As decisões de cada
sistema ficam em `docs/decisoes/` do sistema, não aqui.

| ADR | Decisão | Situação |
| --- | --- | --- |
| [0001](ADR-0001-python-biblioteca-padrao.md) | Ferramentas do framework em Python só com a biblioteca padrão | aceita |
| [0002](ADR-0002-configuracao-em-toml.md) | Configuração do projeto em `bigbang.toml` | aceita |
| [0003](ADR-0003-branch-de-epico.md) | Branch de épico (`epico/*`) | aceita |
| [0004](ADR-0004-release-por-epico-a-partir-da-main.md) | Release por épico a partir da `main` | aceita |
| [0005](ADR-0005-skills-em-agents-e-claude.md) | Skills em `.agents/skills/`, com cópia em `.claude/skills/` | aceita |
| [0006](ADR-0006-ci-do-framework.md) | CI do próprio Big Bang | aceita |
| [0007](ADR-0007-gerador-e-verificador.md) | Como o gerador e o verificador funcionam | aceita |
| [0008](ADR-0008-esteira-bash-e-bb.md) | Esteira: Bash orquestra, o `bb` decide | aceita |
| [0009](ADR-0009-perfil-compilado.md) | Perfil compilado: candidata, promoção e correção | aceita |
| [0010](ADR-0010-portoes-de-teste-revisao-e-seguranca.md) | Portões de testes, revisão e segurança | aceita |
| [0011](ADR-0011-posses-e-concorrencia.md) | Posse de tarefas, isolamento e inatividade das IAs | aceita |
| [0012](ADR-0012-skills-hooks-e-fundacao.md) | Skills, hooks e a montagem do GitHub na Fundação | aceita |
| [0013](ADR-0013-perfil-deploy.md) | Perfil deploy e alvo vps-docker | aceita |
| [0014](ADR-0014-pacote-e-atualizacao.md) | Pacote do framework e `bb atualizar` | aceita |
| [0015](ADR-0015-release-por-sprint.md) | Release por sprint ou por épico | aceita |
| [0016](ADR-0016-deploy-multiplataforma.md) | Deploy multiplataforma por contratos instalados | aceita (refinamento #174) |
