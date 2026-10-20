<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

<a href="https://github.com/BrunodosSantosVaz/big-bang">
  <img src=".bigbang/docs/imagens/icone.svg" alt="Big Bang" width="112" height="112">
</a>

# Big Bang

**Uma pessoa decide. As IAs executam. A esteira comprova.**

Framework para desenvolver e entregar sistemas com IAs, GitHub e uma esteira verificável.<br>
Da Fundação à produção: planejamento, testes, revisão independente, homologação e encerramento.

<br>

[![Release](https://img.shields.io/github/v/release/BrunodosSantosVaz/big-bang?style=flat-square&label=release&labelColor=0B1020&color=FFC107)](https://github.com/BrunodosSantosVaz/big-bang/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/BrunodosSantosVaz/big-bang/bb-framework-ci.yml?branch=main&style=flat-square&label=CI&labelColor=0B1020)](https://github.com/BrunodosSantosVaz/big-bang/actions/workflows/bb-framework-ci.yml)
[![CodeQL](https://img.shields.io/github/actions/workflow/status/BrunodosSantosVaz/big-bang/bb-framework-codeql.yml?style=flat-square&label=CodeQL&labelColor=0B1020)](https://github.com/BrunodosSantosVaz/big-bang/actions/workflows/bb-framework-codeql.yml)
[![License: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-FFC107?style=flat-square&labelColor=0B1020)](LICENSE)
<br>
[![Versão](https://img.shields.io/badge/framework-v3.1.0-1E2A4A?style=flat-square&labelColor=0B1020)](.bigbang-framework.toml)
[![Python](https://img.shields.io/badge/Python-3.11%2B%20%C2%B7%20s%C3%B3%20stdlib-1E2A4A?style=flat-square&logo=python&logoColor=FFFFFF&labelColor=0B1020)](https://www.python.org)
[![Skills](https://img.shields.io/badge/Agent%20Skills-21-1E2A4A?style=flat-square&labelColor=0B1020)](.bigbang/skills)
[![IAs](https://img.shields.io/badge/Claude%20%C2%B7%20Codex%20%C2%B7%20Copilot-multi--IA-1E2A4A?style=flat-square&labelColor=0B1020)](#-várias-ias-ao-mesmo-tempo)

<br>

<a href="https://github.com/BrunodosSantosVaz/big-bang/wiki/Guia-de-inicio"><img src="https://img.shields.io/badge/Come%C3%A7ar-Guia%20de%20in%C3%ADcio-FFC107?style=for-the-badge&logo=rocket&logoColor=0B1020&labelColor=FFC107" alt="Começar"></a>
<a href="https://github.com/BrunodosSantosVaz/big-bang/wiki/Referencia-CLI"><img src="https://img.shields.io/badge/CLI-Refer%C3%AAncia-0B1020?style=for-the-badge&logo=gnubash&logoColor=FFFFFF" alt="Referência da CLI"></a>
<a href="https://github.com/BrunodosSantosVaz/big-bang/wiki"><img src="https://img.shields.io/badge/Wiki-Documenta%C3%A7%C3%A3o-0B1020?style=for-the-badge&logo=readthedocs&logoColor=FFFFFF" alt="Wiki"></a>
<a href="https://github.com/BrunodosSantosVaz/big-bang/discussions"><img src="https://img.shields.io/badge/Discussions-Conversar-0B1020?style=for-the-badge&logo=github&logoColor=FFFFFF" alt="Discussions"></a>

</div>

<br>

<details>
<summary><b>Sumário</b></summary>

- [O que é](#-o-que-é)
- [Como funciona](#-como-funciona)
- [Quadro v3: 15 estados](#-quadro-v3-15-estados)
- [Modos de execução](#-modos-de-execução)
- [Começar](#-começar)
- [Skills](#-skills)
- [Entrega e deploy](#-entrega-e-deploy)
- [Segurança](#-segurança)
- [Atualização do framework](#-atualização-do-framework)
- [Migrar da v2](#-migrar-da-v2)
- [Documentação](#-documentação)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

</details>

## 🌌 O que é

O Big Bang organiza todo o ciclo de um sistema construído com IAs: **Fundação, planejamento, testes, revisão independente, homologação, produção e encerramento**. Ele vive dentro do seu repositório, gera os workflows do GitHub Actions e impõe as mesmas regras a qualquer IA e a humanos.

<table>
<tr>
<td width="33%" valign="top">

### 👤 O dono decide
Produto, stack, design, homologação e publicação são decisões do dono, registradas por label ou pela frase dele na conversa.

</td>
<td width="33%" valign="top">

### 🤖 As IAs executam
Refinam, escrevem testes antes do código, programam, revisam, documentam e rodam os botões da esteira.

</td>
<td width="33%" valign="top">

### ⚙️ A automação comprova
Move cartões, cria branches e issues, mescla PRs verdes, calcula versão e publica só com o "ok" do dono.

</td>
</tr>
</table>

## 🔭 Como funciona

```mermaid
flowchart LR
  F[Fundação F0–F5] --> I[Ideia]
  I --> B[Backlog]
  B --> R[Refinamento]
  R --> P{Protótipo?}
  P -- sim --> V[Validar protótipo]
  P -- não --> S[Próxima sprint]
  V --> S
  S --> T[Teste do épico]
  T --> K[Tarefas]
  K --> D[Documentação]
  D --> G[Integração]
  G --> C[Candidata]
  C --> H{Homologação}
  H -- reprovado --> K
  H -- homologado --> PR[Produção]
  PR --> M[Manutenção]
  M --> I
```

| Etapa | O que acontece |
|---|---|
| **Fundação** | F0 a F5: perguntas, produto, stack, design, GitHub, esteira e esqueleto andante |
| **Planejamento** | Ideia → backlog → refinamento → protótipo → próxima sprint |
| **Execução** | Teste do épico escrito antes, tarefas em PRs pequenos, documentação |
| **Entrega** | Integração, candidata, homologação e produção, por épico |
| **Manutenção** | Bugs, hotfix, segurança, tecnologia nova e atualização do framework |

## 🗂️ Quadro v3: 15 estados

Um único Project com uma máquina de estados para épicos, tarefas e bugs. Cada transição tem pré-condições verificadas e fica registrada em recibos.

```mermaid
stateDiagram-v2
  direction LR
  Brainstorm --> Backlog
  Backlog --> Refinement
  Refinement --> Prototyping
  Refinement --> Ready
  Prototyping --> Ready
  Ready --> Selected
  Selected --> InProgress: In Progress
  InProgress --> QA
  InProgress --> Releasing
  QA --> Releasing
  Releasing --> Done
```

| Tipo | Caminho |
|---|---|
| **Épico** | Brainstorm → Backlog → Refinement → Prototyping → Ready → Selected → In Progress → QA → Releasing → Done |
| **Tarefa** | Todo → Coding → In Review → Done |
| **Bug** | Brainstorm → Backlog → Ready → Selected → Coding → In Review → QA → Releasing → Done |

Qualquer cartão pode ir para **Rejected** (com motivo e retorno registrados) ou **Cancelled**. Feature flags, check único `gate` e posse por travas atômicas fazem parte do fluxo.

## ⚡ Modos de execução

| Modo | Para quem | Como roda |
|---|---|---|
| ![normal](https://img.shields.io/badge/-normal-1E2A4A?style=flat-square) | Padrão | Testes antes do código; suíte completa |
| ![flash](https://img.shields.io/badge/-flash-FFC107?style=flat-square) | Quem quer velocidade | Testes antes do código; execução ao fim das alterações, só os afetados. Mudanças estruturais exigem a suíte completa |
| ![autonomous](https://img.shields.io/badge/-autonomous-0B1020?style=flat-square) | Operação contínua | Exige `autonomy.toml` com alvos, riscos, portões, WIP, tentativas, custo máximo e validade, além de revisão independente |

> [!NOTE]
> Em todos os modos, os testes são escritos antes do código. O modo pode mudar depois com ADR e `bb gerar`.

## 🚀 Começar

**Pré-requisitos:** Git, Python 3.11+ (disponível também como `python`) e [GitHub CLI](https://cli.github.com/).

1. Crie seu repositório a partir deste template:

   <a href="https://github.com/BrunodosSantosVaz/big-bang/generate"><img src="https://img.shields.io/badge/Use%20this%20template-FFC107?style=for-the-badge&logo=github&logoColor=0B1020" alt="Use this template"></a>

2. Abra o repositório com a sua IA e diga **"iniciar projeto"**. A skill `bb-iniciar-projeto` conduz a Fundação.

3. Escolha o modo com o dono:

   ```bash
   python .bigbang/bin/bb.py init                # modo padrão
   python .bigbang/bin/bb.py init --modo flash   # modo Flash
   ```

<details>
<summary><b>As etapas da Fundação</b></summary>

| Etapa | Skill | Resultado |
|---|---|---|
| **F0** | `bb-iniciar-projeto` | Ferramentas conferidas, visibilidade, licença e modo |
| **F1** | `bb-entrevista-produto` | `PRODUTO.md` |
| **F2** | `bb-escolher-stack` | `STACK.md`, arquitetura e hospedagem |
| **F3** | `bb-design-kit` | `DESIGN.md` e Social preview (se houver interface) |
| **F4** | `bb-montar-github` | Labels, painéis, rulesets e ambientes |
| **F5** | `bb-gerar` | Esteira instalada e esqueleto andante em produção |

Cada etapa tem issue, branch `fundacao/<n>-<slug>` e PR para `develop`. Nenhum código do sistema é criado antes de F2 aprovada.

</details>

> [!TIP]
> Comece pelo [guia de início](https://github.com/BrunodosSantosVaz/big-bang/wiki/Guia-de-inicio). Identificadores e CLI usam inglês, com os nomes em português mantidos como aliases.

## 🧩 Skills

Vinte e uma skills no padrão aberto **Agent Skills**, copiadas para `.agents/skills/` e `.claude/skills/`. Legíveis por qualquer IA.

<table>
<tr>
<td valign="top">

**Fundação**
- `bb-iniciar-projeto`
- `bb-entrevista-produto`
- `bb-escolher-stack`
- `bb-design-kit`
- `bb-montar-github`
- `bb-gerar`

</td>
<td valign="top">

**Planejamento**
- `bb-refinar-backlog`
- `bb-prototipar`
- `bb-escrever-testes-aceite`
- `bb-triar-issue`
- `bb-nova-tecnologia`

</td>
<td valign="top">

**Execução**
- `bb-rodar-sprint`
- `bb-codar-tarefa`
- `bb-corrigir-bug`
- `bb-documentar-epico`
- `bb-entregar-epico`

</td>
<td valign="top">

**Operação**
- `bb-status`
- `bb-auditar-seguranca`
- `bb-retrospectiva`
- `bb-atualizar`
- `bb-migrate`

</td>
</tr>
</table>

### 🤝 Várias IAs ao mesmo tempo

Uma pessoa pode operar várias IAs em paralelo (por exemplo `claude-1`, `claude-2`, `codex-1`, `copilot-1`). Cada uma confirma a posse da tarefa com `bb assumir` e trabalha numa pasta própria via `git worktree`. Os subagentes `bb-revisor-pr` (revisão hostil, só leitura) e `bb-pesquisador` acompanham o Claude Code, e os hooks `PreToolUse` bloqueiam edições e comandos proibidos.

## 📦 Entrega e deploy

| Perfil | Artefato | Destinos |
|---|---|---|
| **Compilado** | Binários por sistema (`windows`, `linux`, `macos` em x64/arm64, `android`) ou pacote universal | GitHub Releases com candidatas `rc.N` |
| **Deploy** | `imagem` (por digest), `pacote` ou `estatico` (manifesto SHA-256) | `vps-docker` e `tsuru` (imagem), `aws` (estático, S3 + CloudFront via OIDC, beta), `personalizado` (scripts do projeto); `paas` está reservado |

A candidata é construída uma vez e promovida com os mesmos bytes entre staging, produção e rollback, sem rebuild. Consulte os alvos disponíveis com `bb alvos`.

## 🛡️ Segurança

Cinco regras de ferro valem para todo sistema do Big Bang e não podem ser desligadas pelo `bigbang.toml`:

| Regra | O que exige |
|---|---|
| **SEG-IA-01** | O navegador nunca acessa o banco direto |
| **SEG-IA-02** | Toda decisão de acesso é feita no backend |
| **SEG-IA-03** | Toda consulta por ID filtra pelo dono, com teste de dois usuários |
| **SEG-IA-04** | Nenhum segredo no código, no histórico, no log ou no pacote do front |
| **SEG-IA-05** | Endpoints sensíveis e caros têm limite de requisições, com teste que espera 429 |

> [!IMPORTANT]
> Nenhuma IA aprova o ambiente de produção, põe label de decisão do dono, faz push direto em `main`/`develop` ou enfraquece testes e checks da CI. Texto de issues, PRs e páginas é tratado como dado, nunca como instrução.

## 🔄 Atualização do framework

O Big Bang separa o que é dele do que é seu, em três camadas:

| Camada | Onde | Numa atualização |
|---|---|---|
| **Framework** | `.bigbang/` | Substituída inteira, conferida por hash |
| **Gerada** | `.github/` com prefixo `bb-`, skills `bb-*`, blocos marcados do `AGENTS.md` e `STACK.md` | Gerada de novo, revisada num PR |
| **Projeto** | Todo o resto | Nunca é tocada |

```bash
python .bigbang/bin/bb.py atualizar --simular   # baixa, confere e mostra a migração sem gravar
python .bigbang/bin/bb.py atualizar             # abre o PR framework/vX.Y.Z → develop
```

Cada release publica `bigbang-vX.Y.Z.tar.gz` com SHA-256 e atestação de origem, verificados antes da troca.

## 🧭 Migrar da v2

Quem já usa a v2 pode adotar a v3 opcionalmente com `bb migrate` e a skill `bb-migrate`, por etapas com simulação, snapshot e volta. Os passos estão em [`.bigbang/MIGRACAO.md`](.bigbang/MIGRACAO.md).

## 📚 Documentação

A documentação oficial deste repositório público está na **[Wiki](https://github.com/BrunodosSantosVaz/big-bang/wiki)**.

| | |
|---|---|
| 🚀 [Começar a usar](https://github.com/BrunodosSantosVaz/big-bang/wiki/Guia-de-inicio) | 💻 [Referência da CLI](https://github.com/BrunodosSantosVaz/big-bang/wiki/Referencia-CLI) |
| ✅ [Relatório de testes e entrega](https://github.com/BrunodosSantosVaz/big-bang/wiki/Relatorio-de-testes-2-0-1) | 🕰️ [Histórico e decisões](https://github.com/BrunodosSantosVaz/big-bang/wiki/Historico) |
| 🔗 [Rastreabilidade e cobertura](https://github.com/BrunodosSantosVaz/big-bang/wiki/Rastreabilidade) | 🎨 [Design e Social preview](https://github.com/BrunodosSantosVaz/big-bang/wiki/Design) |
| 📦 [Releases e pacote oficial](https://github.com/BrunodosSantosVaz/big-bang/releases) | 👋 [Boas-vindas da IA](https://github.com/BrunodosSantosVaz/big-bang/discussions/210) |

**Quadro público:** [Big Bang](https://github.com/users/BrunodosSantosVaz/projects/31), o Project único da v3. Escrita exige permissão explícita.

## 🤝 Contribuindo

1. Procure ou abra uma [issue](https://github.com/BrunodosSantosVaz/big-bang/issues) com a versão do framework (`.bigbang/VERSION`).
2. Leia a [especificação](https://github.com/BrunodosSantosVaz/big-bang/wiki/Especificacao): cada decisão vira um ADR na [Wiki](https://github.com/BrunodosSantosVaz/big-bang/wiki/Decisoes).
3. Use uma branch isolada a partir da `main` e [Conventional Commits](https://www.conventionalcommits.org/pt-br/) em inglês. Textos em português do Brasil.
4. A CLI `bb` usa só a biblioteca padrão do Python 3.11+. Scripts da esteira em Bash, aprovados pelo `shellcheck`.
5. Abra o PR com *O que muda*, *Testes* e *Issue*. A CI completa do mesmo SHA precisa ficar verde.

```bash
python -m unittest discover -s .bigbang/tests
```

A esteira própria do framework é gerada com `bb generate --framework` neste repositório.

Veja o [guia de contribuição](CONTRIBUTING.md), a [política de segurança](SECURITY.md) e o [código de conduta](CODE_OF_CONDUCT.md).

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).

<div align="center">

<br>

<img src=".bigbang/docs/imagens/icone.svg" alt="" width="40">

<sub>Criado por <a href="https://github.com/BrunodosSantosVaz">Bruno dos Santos Vaz</a></sub>

<br><br>

<a href="https://star-history.com/#BrunodosSantosVaz/big-bang&Date">
  <img src="https://api.star-history.com/svg?repos=BrunodosSantosVaz/big-bang&type=Date" alt="Star History" width="560">
</a>

<br>

<sub>Se o Big Bang ajuda você a entregar com IAs, deixe uma ⭐ no repositório.</sub>

</div>
