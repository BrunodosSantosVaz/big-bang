# 14 · Automações

Todos os workflows gerados pelo Big Bang, os botões, os segredos e as variáveis, e os limites conhecidos do GitHub.

## Regras de todos os workflows gerados

- Arquivo `bb-<nome>.yml`; nome exibido em português (é o botão).
- `permissions:` mínimas declaradas no topo.
- Actions fixadas por **SHA completo**, com a versão em comentário; runners Linux em versão fixa (por exemplo
  `ubuntu-24.04`), nunca `ubuntu-latest`. O `bb verificar` reprova o que estiver fora da regra.
- Em eventos de PR, o checkout dos scripts que usam `PROJETO_TOKEN` vem do SHA da branch de **destino**, nunca do PR.
- `concurrency` por issue/PR/ref, sem cancelar o que está em andamento.
- Todo botão tem `simular` (padrão `true`): mostra o plano e não altera nada.
- Todo job é idempotente: rodar de novo não duplica nem quebra.

## Workflows do núcleo

| Botão | Arquivo | Disparo | O que faz |
| --- | --- | --- | --- |
| CI | `bb-ci.yml` | PR e push | instala, lint, tipos, testes (unidade, integração, aceite), arquitetura, cobertura, build, documentação, `bb verificar`. Job obrigatório: `check` |
| Regras do PR | `bb-regras-pr.yml` | PR | nomes, destino, `Refs #n`, título, zona sensível, `sem-release`, trava de aceite, pendentes, rastreabilidade, guarda da stack, regressão. Job obrigatório: `regras` |
| Segurança | `bb-seguranca.yml` | PR, push e semanal | Gitleaks, Opengrep, Bandit, OSV-Scanner, segredo no pacote do front, RLS. Job obrigatório: `seguranca` |
| CodeQL | `bb-codeql.yml` | PR, push e semanal | análise estática do GitHub |
| Kanban | `bb-kanban.yml` | issues, labels, push, PR | move os cartões; converte respostas do formulário do épico em labels |
| Mesclar PR | `bb-mesclar-pr.yml` | `pr-aprovado`/`testes-aprovados`, checks | mescla no `epico/…` quando aprovado e verde; na `develop`, só PRs `sem-release` fora de épico; **nunca** na `main` |
| Iniciar sprint | `bb-iniciar-sprint.yml` | botão | branches do épico, issues de teste/tarefas/documentação |
| Criar branches | `bb-criar-branches.yml` | botão; após merge do teste | branches das tarefas desbloqueadas e da documentação |
| Integrar release | `bb-integrar-release.yml` | último merge do épico; botão | `release/x.y.z`, versão, changelog, milestone |
| Publicar em produção | `bb-publicar-producao.yml` | botão + ambiente `producao` | portão e publicação do mesmo artefato |
| Publicar sem release | `bb-publicar-sem-release.yml` | botão + ambiente `producao` | avança a `main` até a `develop` |
| Encerrar | `bb-encerrar.yml` | botão | completa a limpeza pós-produção; encerra a sprint |
| Ver painéis | `bb-ver-paineis.yml` | botão | somente leitura: colunas, posses paradas, flags vencidas, pendências do dono |
| Dependabot | `.github/dependabot.yml` | mensal | actions → `develop` (`sem-release`); pacotes da stack → `main`, via release de manutenção |

### Perfil `compilado`

| Arquivo | Disparo | O que faz |
| --- | --- | --- |
| `bb-candidata.yml` | push em `release/**` | testes; build por sistema; pre-release `vX.Y.Z-rc.N` com binários, `SHA256SUMS-<sistema>.txt`, atestado e SBOM; abre o PR da release |

### Perfil `deploy`

| Arquivo | Disparo | O que faz |
| --- | --- | --- |
| `bb-candidata.yml` | push em `release/**` | imagem uma vez, registro com digest, Trivy, staging, migração, smoke, ZAP; abre o PR da release |
| `bb-voltar-versao.yml` | botão + ambiente `producao` | reimplanta a imagem da tag anterior; nunca desfaz migração |

Cada alvo de deploy (`vps-docker`, `aws`, `paas`) implementa quatro operações: `publicar <ambiente> <digest>`,
`voltar <ambiente> <tag>`, `migrar <ambiente> <digest>` e `saude <ambiente>`.

## Segredos e variáveis

| Nome | Tipo | Para quê |
| --- | --- | --- |
| `PROJETO_TOKEN` | segredo | PAT clássico (`repo`, `project`; `workflow` só se necessário), com validade, um por projeto. Lê e move os painéis; dispara workflows |
| `PROJETO_OWNER` | variável | dono dos painéis |
| `PROJETO_PLANEJAMENTO`, `PROJETO_EXECUCAO`, `PROJETO_BUGS` | variáveis | números dos painéis |
| credenciais do alvo | segredos do ambiente | só no perfil deploy; preferir OIDC a chave fixa |

## Usar os botões pela IA

A IA usa os mesmos botões via `gh workflow run <arquivo> -f simular=true …`. Rodar à mão ou pela IA dá o mesmo
resultado.

## Limites conhecidos do GitHub

- Botão novo só aparece em *Run workflow* depois que o arquivo está na branch padrão.
- Cartão movido à mão não gera evento; por isso as decisões são labels e os portões leem o estado na hora.
- PR de fork roda sem segredos: a automação de painéis não age; o dono ajusta ou usa os botões.
- O primeiro PR de um contribuidor novo pode exigir aprovação para rodar a CI.
- Eventos gerados pelo `GITHUB_TOKEN` não disparam outros workflows; a esteira usa o `PROJETO_TOKEN` onde precisa
  disparar.
- Repositório privado no plano gratuito tem limites de rulesets e de aprovação de ambiente; a Fundação explica a
  alternativa no momento, conferindo a documentação vigente.
- Todas as IAs usam a conta do dono: o GitHub não distingue quem pôs uma label (veja [08-revisao.md](08-revisao.md)).

## O que a automação faz sozinha

Este documento é o catálogo dela: tudo que está nas tabelas acima roda sem ninguém pedir, a partir de eventos do
GitHub (push, PR, labels, agenda), exceto os **botões**, que o dono ou a IA disparam, sempre com `simular=true`
primeiro. Publicar em produção, publicar sem release e voltar versão ainda exigem a aprovação do dono no ambiente
`producao`.
