# 04 · Painéis

Três painéis do GitHub Projects (de usuário), criados na Fundação (F4) pelo script `criar-paineis`.

## Colunas

| Painel | Colunas | Itens |
| --- | --- | --- |
| **Planejamento** | Brainstorm → Backlog → Backlog Refinement → Validar protótipo (só `com-prototipo`) → Próxima sprint → Em desenvolvimento → Homologação → Concluída | Épicos |
| **Execução** | A fazer → Feature → Code → CI/PR → Validar PR (só `revisao-humana`) → Pronto → Concluído | Teste do épico, tarefas, documentação |
| **Bugs** | Novo → Em correção → CI/PR → Validar PR → Homologação → Corrigido | Bugs |

*Pronto* = PR aprovado e mesclado na branch do épico, esperando o resto do épico. A homologação acontece no cartão do
**épico**, não das tarefas.

## Campos

| Campo | Tipo | Uso |
| --- | --- | --- |
| **Sprint** | Seleção única | Uma opção por sprint, criada pelo *Iniciar sprint*, no formato `Sprint 7 · 2026-10-05`. Não usar *Iteration*, que tem duração fixa |
| **Épico** | Texto | `#n` do épico de cada item |
| **Prioridade** | Seleção única | alta, média, baixa |
| **Versão** | Texto | Preenchida na integração |

Visões: quadro, tabela agrupada por épico, roadmap.

## Quem move cada coluna

O dono só arrasta **Brainstorm → Backlog** (a decisão de implementar). Todo o resto é movido pela automação a partir
de eventos do GitHub (push, PR, labels) ou pelos botões.

**Arrastar cartão não dispara nada**: Projects de usuário não emitem eventos para as Actions. Por isso toda decisão do
dono é uma label, e os portões leem o estado na hora.

| Painel | Coluna | Entra quando |
| --- | --- | --- |
| Planejamento | Brainstorm | épico criado |
| Planejamento | Backlog | o dono arrasta |
| Planejamento | Backlog Refinement | `bb-refinar-backlog` começa o refinamento |
| Planejamento | Validar protótipo | `refinamento-aprovado` + `com-prototipo` |
| Planejamento | Próxima sprint | `refinamento-aprovado` + `sem-prototipo`, ou `prototipo-aprovado` |
| Planejamento | Em desenvolvimento | *Iniciar sprint*; ou `reprovado` (volta) |
| Planejamento | Homologação | candidata publicada (rc ou staging) |
| Planejamento | Concluída | publicado em produção (ou *Publicar sem release*) |
| Execução | A fazer | issue criada |
| Execução | Feature | branch criada |
| Execução | Code | primeiro push; ou revisão reprovada / PR fechado sem merge (volta) |
| Execução | CI/PR | PR aberto |
| Execução | Validar PR | CI verde + `revisao-humana` |
| Execução | Pronto | PR mesclado na branch do épico |
| Execução | Concluído | épico publicado |
| Bugs | Novo | bug criado |
| Bugs | Em correção | branch `bugfix/*` ou `hotfix/*` criada |
| Bugs | CI/PR | PR aberto |
| Bugs | Validar PR | CI verde + `revisao-humana` |
| Bugs | Homologação | candidata publicada |
| Bugs | Corrigido | publicado em produção |

## O que a automação faz sozinha

O workflow *Kanban* move os cartões a cada evento; o *Ver painéis* mostra, sem alterar nada, as colunas, as posses
paradas, as feature flags vencidas e o que espera pelo dono.
