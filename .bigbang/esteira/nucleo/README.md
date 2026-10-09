# Núcleo da esteira

O que todo sistema recebe, qualquer que seja o perfil de entrega (seções 14.1, 14.2 e 14.5 da
[especificação](https://github.com/BrunodosSantosVaz/big-bang/wiki/Especificacao)). Decisões: [ADR-0008](https://github.com/BrunodosSantosVaz/big-bang/wiki/ADR-0008-esteira-bash-e-bb).

- `arquivos/`: o que o `bb gerar --esteira` copia para o projeto (workflows `bb-*.yml`, formulários de issue, modelo
  de PR, `dependabot.yml`).
- `scripts/`: o que os workflows executam direto de `.bigbang/` (Bash; as regras ficam em `bb esteira …`).

| Botão / workflow | Script |
| --- | --- |
| CI (`check`) | `comando.sh` + `bb verificar` + `bb esteira documentacao` |
| Regras do PR (`regras`) | `regras-pr.sh` |
| Kanban | `kanban.sh` |
| Mesclar PR | `mesclar-pr.sh` |
| Iniciar sprint | `iniciar-sprint.sh` |
| Criar branches | `criar-branches.sh` |
| Integrar release | `integrar-release.sh` (usa `git-mesclar.sh`) |
| Publicar sem release | `publicar-sem-release.sh` |
| Encerrar | `encerrar.sh` |
| Ver painéis | `ver-paineis.sh` |
| (depois de cada publicação) | `devolver-main.sh` |

Todos usam `projeto.sh` para os painéis. A montagem do GitHub (labels e painéis) está em `.bigbang/scripts/`.
