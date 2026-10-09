# 14 · Automações

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

O [modo Flash](17-flash.md) muda a execução dos testes no job `check`: após o build, usa `bb testes` com a base do PR/push; mudanças estruturais e releases major/minor forçam suíte completa. A candidata espera o `check` verde do SHA exato, e produção executa suíte completa antes da aprovação do ambiente.

## Coordenação de IAs

**Marcar posses paradas** (`bb-posses.yml`) roda a cada hora e marca `parada` quando não houve push registrado por
mais que `ias.trava_expira_horas`. O botão começa em simulação. **Kanban** registra pushes na sessão e libera a posse
no merge do PR. **Ver painéis** e `bb status` exibem posses, flags vencidas e achados de segurança sem alterar estado.
Essas automações usam o `PROJETO_TOKEN` do projeto; detalhes em [13-varias-ias.md](13-varias-ias.md).

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
| Encerrar | `bb-encerrar.yml` | botão | completa a limpeza pós-produção; encerra a sprint; roda a faxina |
| Faxina | `faxina.sh` (no *Encerrar*, no *Publicar em produção* e no *Publicar sem release*) | automático | apaga branches mescladas cujo trabalho acabou; lista issues, PRs e posses que sobraram |
| Faxina (recuperação) | `bb-faxina.yml` | diário e botão | complementa a faxina das publicações reais; scripts apenas da main; simula ou limpa branches concluídas; falha se houver sobras |
| Ver painéis | `bb-ver-paineis.yml` | botão | somente leitura: colunas, posses paradas, flags vencidas, pendências do dono |
| Tarefa de correção | `bb-tarefa-de-correcao.yml` | botão (`epico`, `motivo`) | tarefa nova no épico reprovado na homologação (decisão 16) |
| Dependabot | `.github/dependabot.yml` | mensal | actions → `develop` (`sem-release`); pacotes da stack → `main`, via release de manutenção |

### Perfil `compilado`

| Arquivo | Disparo | O que faz |
| --- | --- | --- |
| `bb-candidata.yml` | push em `release/**` | testes; build por sistema; pre-release `vX.Y.Z-rc.N` com binários, `SHA256SUMS-<sistema>.txt`, atestado e SBOM; abre o PR da release |

Contrato de build (ADR-0009): `compilado.build_<sistema>` deixa **exatamente um arquivo** em `$BB_SAIDA`
(`dist/<sistema>`) e pode ler `BB_VERSAO`, `BB_RC` e `BB_SISTEMA`. Para assinar o binário (APK, executável), o build
recebe os segredos opcionais `BB_ASSINATURA_ARQUIVO` (keystore ou certificado em base64), `BB_ASSINATURA_SENHA`,
`BB_ASSINATURA_ALIAS` e `BB_ASSINATURA_SENHA_CHAVE`, só nesse passo; o script do projeto grava o arquivo num temporário
e nunca o imprime. O atestado de procedência só é gerado em
repositório público (em privado exige GitHub Enterprise Cloud).

### Perfil `deploy`

| Arquivo | Disparo | O que faz |
| --- | --- | --- |
| `bb-candidata.yml` | push em `release/**` | imagem uma vez, registro com digest, Trivy, staging, migração, smoke, ZAP; abre o PR da release |
| `bb-voltar-versao.yml` | botão + ambiente `producao` | reimplanta a imagem da tag anterior; nunca desfaz migração |

Consulte `bb alvos` (somente leitura, disponível antes da Fundação) para distinguir alvos e formatos implementados
das reservas. Hoje a entrega disponível é `vps-docker` + `imagem`; `aws`, `paas`, `tsuru`, `personalizado`, `pacote` e
`estatico` estão reservados e o gerador recusa sua seleção. A configuração `deploy.artefato` é opcional e usa
`imagem` por padrão.

Cada alvo implementado declara as operações `publicar <ambiente> <digest>`, `voltar <ambiente> <tag>`,
`migrar <ambiente> <digest>` e `saude <ambiente>`, podendo oferecer `checar`. Os contratos instalados são validados
antes de gerar arquivos. A composição passa pelo formato do artefato antes do alvo. Veja o
[contrato de extensão](../esteira/perfis/deploy/README.md) e o [ADR-0016](https://github.com/BrunodosSantosVaz/big-bang/wiki/ADR-0016-deploy-multiplataforma).

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
- **Limites de requisições:** a API GraphQL (que os Projects usam) dá 5.000 pontos por hora por conta, divididos entre
  todos os workflows que usam o `PROJETO_TOKEN` e a IA; os scripts guardam os ids dos painéis durante cada execução
  para economizar. Há também um **limite secundário** para criar conteúdo em sequência (issues, PRs, comentários):
  um *Iniciar sprint* com muitos épicos pode esbarrar nele. Os botões são idempotentes, então a solução é esperar
  alguns minutos e rodar de novo.
- O workflow embutido *Auto-add sub-issues to project* vem ligado em painel novo e puxaria as tarefas para o
  Planejamento; a API não o desliga, só o apaga, e o `criar-paineis` apaga no Planejamento e em Bugs.

## O que a automação faz sozinha

Este documento é o catálogo dela: tudo que está nas tabelas acima roda sem ninguém pedir, a partir de eventos do
GitHub (push, PR, labels, agenda), exceto os **botões**, que o dono ou a IA disparam, sempre com `simular=true`
primeiro. Publicar em produção, publicar sem release e voltar versão ainda exigem a aprovação do dono no ambiente
`producao`; quem dispara entrega o link do run e os passos de aprovação (`link-aprovacao.sh`), que também ficam no
resumo do run.
