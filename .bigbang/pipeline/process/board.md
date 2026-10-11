# Quadro único e estado

## Estados

Um só GitHub Project por repositório, com o campo `Status` e 15 estados:

| Tipo | Caminho |
| --- | --- |
| Épico | Brainstorm → Backlog → Refinement → (Prototyping) → Ready → Selected → In Progress → (QA) → Releasing → Done |
| Tarefa (`type:task`, `type:test`, `type:docs`) | Todo → Coding → In Review → Done |
| Bug | Brainstorm → Backlog → Ready → Selected → Coding → In Review → (QA) → Releasing → Done |
| Todos | Rejected (com motivo e retorno) e Cancelled (com motivo) |

Nos épicos, as voltas permitidas sem reprovação são Ready → Refinement e Selected → Ready.

## De onde vem o estado

O estado de um cartão vem dos **recibos** da issue: comentários `<!-- bb:receipt {…} -->` gravados pela conta
confiável (`project.owner`). O campo do Project só projeta esse estado.

- Mova sempre com `bb move <issue> <estado>`.
- Um cartão arrastado à mão volta ao estado registrado na próxima reconciliação (agenda do controlador ou
  `bb board reconcile`), com um comentário explicando o motivo.
- Todo recibo de transição com portão grava `approval` com o portão, o risco, o modo e quem aprovou
  (`owner:<login>` ou `agent:<nome>`).

## Portões e decisões do dono

| Portão | Transição | Decisão registrada |
| --- | --- | --- |
| backlog | Brainstorm → Backlog | `approved:backlog` |
| refinement | Refinement → Prototyping/Ready | `approved:refinement` |
| prototype | Prototyping → Ready | `approved:prototype` |
| selection | Ready → Selected | `approved:selection` |
| qa | QA → Releasing (e QA → Rejected) | `qa:approved` (ou `qa:rejected`) |
| publish | Releasing → Done | aprovação do ambiente `production` |
| cancel | → Cancelled (épico ou bug) | `approved:cancel` |

- A decisão do dono é sempre uma label registrada com `bb decision <label> <issue> --quote "<palavras dele>"`.
- A identidade de quem roda o comando nunca aprova nada: numa conta pessoal, o dono e as IAs compartilham o login.
- O risco de planejamento vem das áreas (`area:*`, médio por padrão).
- O risco de QA e de publicação vem dos arquivos dos PRs mesclados das sub-issues, lidos desde a criação da
  sub-issue mais antiga. Sem esses PRs, o risco nunca fica abaixo de alto.
- `risk:*` só sobe o risco.
- Quem aprova cada portão depende do modo ([modes.md](modes.md)).

## Reprovação

- O comando é `bb move N Rejected --reason <motivo> --return-to <estado>`. Os motivos são requirements,
  prototype, tests, code, security, docs, qa e release.
- O retorno precisa ser um dos permitidos para a etapa.
- Sair de Rejected só leva ao retorno registrado, e só sem impedimento ativo.
- Uma reprovação, ou uma volta sem reprovação, retira as decisões do dono da etapa de retorno em diante.
- As tentativas vêm dos recibos. No limite (`attempts`), o cartão fica em Rejected com `blocked` até o dono decidir.

## Posse e travas

- `bb claim N <nome>` cria a trava atômica `refs/bigbang/locks/issue-N`. Quem pede depois perde e fica sabendo
  quem tem a posse.
- `bb renew N` estende o prazo; `bb unclaim N` libera.
- A trava liberada vira uma lápide e nunca é apagada.
- Uma sessão vencida não renova nem conclui trabalho.
- Retomar a posse vencida de outro exige a ordem do dono (`--force-claim`).
- A capacidade de cada agente conta as travas das issues abertas.
- Pessoas usam `person:<login>`; IAs usam `agent:<nome>` de `agents.names`.

## Controlador

O workflow `bb-controller.yml` transforma eventos em movimentos validados (`bb pipeline controller`):

| Evento | Movimento |
| --- | --- |
| push na branch da tarefa | Todo → Coding |
| PR aberto | In Review |
| merge | Done, com a issue fechada e a trava liberada; no bug, QA ou Releasing |
| PR fechado sem merge | volta a Coding |
| label de decisão | avanço permitido |
| agenda | reconcilia o quadro e marca `stale` nas posses vencidas |

Eventos repetidos ou fora de ordem não duplicam nada. Uma posse tomada depois do merge não é solta por um evento
atrasado.
