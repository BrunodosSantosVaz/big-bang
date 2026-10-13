# 04 · Painéis

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Quadro único do GitHub Projects (de usuário), criado na Fundação (F4) pelo script `criar-paineis.sh`. Centraliza todo o fluxo do sistema com um único campo `Status` de 15 opções, campos complementares e as vistas Quadro, Tabela e Roadmap.

## Status do quadro único

O ciclo de vida consolida épicos, tarefas e bugs nas 15 opções do campo `Status`:

| Tipo | Fluxo de Status |
| --- | --- |
| **Épico** | Brainstorm → Backlog → Refinement → Prototyping (opcional) → Ready → Selected → In Progress → QA (opcional) → Releasing → Done |
| **Tarefa** (`task`, `teste-aceite`, `documentacao`) | Todo → Coding → In Review → Done |
| **Bug** | Brainstorm → Backlog → Ready → Selected → Coding → In Review → QA (opcional) → Releasing → Done |
| **Todos** | Rejected (com motivo e retorno) e Cancelled (com motivo) |

*Done* = PR mesclado e entregue, ou épico/bug publicado. A homologação do ciclo acontece na etapa QA/Releasing antes da publicação.

## Campos

| Campo | Tipo | Uso |
| --- | --- | --- |
| **Status** | Seleção única | As 15 opções do ciclo de vida |
| **Sprint** | Seleção única | Uma opção por sprint, criada pelo *Iniciar sprint*, no formato `Sprint 7 · 2026-10-05`. Não usar *Iteration*, que tem duração fixa |
| **Épico** | Texto | `#n` do épico de cada item |
| **Prioridade** | Seleção única | Alta, Média, Baixa |
| **Versão** | Texto | Preenchida na integração |

## Vistas do Project

O script `criar-paineis.sh` configura três vistas nativas no Project:
- **Quadro**: exibição em cartões agrupados pelas colunas do campo `Status`.
- **Tabela**: exibição tabular de itens e seus campos, agrupável por `Épico`.
- **Roadmap**: linha do tempo cronológica de planejamento e entregas.

## Quem move cada cartão

O dono decide e aprova (decisão de implementar, aprovação de refinamento, aprovação de protótipo, seleção de sprint e homologação). Todo o avanço é registrado por labels e recibos confiáveis ou disparado pela automação da esteira.

**Arrastar cartão não dispara nada**: Projects de usuário não emitem eventos para as Actions. Por isso toda decisão do dono é uma label, e os portões leem o estado na hora.

| Status | Entra quando |
| --- | --- |
| **Brainstorm** | Épico ou bug aberto |
| **Backlog** | Dono aprova a inclusão no backlog |
| **Refinement** | Início do refinamento da issue |
| **Prototyping** | Refinamento aprovado para épico com protótipo (`com-prototipo`) |
| **Ready** | Definition of Ready atendida e refinamento/protótipo aprovado |
| **Selected** | Épico selecionado para a sprint (*Iniciar sprint*) |
| **In Progress** | Épico em desenvolvimento durante a sprint |
| **Todo** | Tarefa, teste ou documentação criada para a sprint |
| **Coding** | Branch de trabalho criada e implementação iniciada |
| **In Review** | PR aberto e em revisão (CI/PR) |
| **QA** | Candidata de homologação publicada para teste |
| **Releasing** | Integração na branch de release e preparação da entrega |
| **Done** | PR mesclado e publicado em produção (ou *Publicar sem release*) |
| **Rejected** | Reprovação registrada com motivo e estado de retorno |
| **Cancelled** | Cancelamento do item registrado com motivo |

## O que a automação faz sozinha

O workflow *Kanban* e a esteira movem os cartões no quadro único a cada evento; o *Ver painéis* / `bb status` inspeciona e reporta, sem alterar nada, as colunas do quadro único, as posses ativas, as feature flags e o que espera pelo dono.
