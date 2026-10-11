# Sprint

## Seleção

O dono escolhe os épicos em Ready e registra `approved:selection`; o controlador os leva a Selected. O número de
épicos em andamento respeita `epics_in_progress` (ou `wip` do contrato no autonomous).

## Início: `bb sprint start`

O botão *Start sprint* roda primeiro com `dry_run=true`. Para cada épico em Selected, ele:

- cria as sub-issues: teste de aceite (`type:test`), tarefas (`type:task`) e documentação (`type:docs`, a última);
- registra as dependências nativas: as tarefas dependem do teste, e a documentação depende das tarefas;
- cria a branch `test/<n>-<slug>` a partir da `develop`;
- move o épico para In Progress.

Rodar de novo não duplica nada.

## Andamento

- Teste de aceite primeiro (`bb-escrever-testes-aceite`). Depois do merge, `bb branches` (botão *Create branches*)
  cria `feature/<n>-<slug>` e `docs/<n>-<slug>` a partir da `develop` para as tarefas desbloqueadas.
- Cada tarefa segue [execution.md](execution.md) e fecha no merge.
- Quando todas as sub-issues fecham, o épico está pronto para a release ([delivery.md](delivery.md)).

## Encerramento

Resuma o que foi publicado e o que segue em andamento e faça a retrospectiva (`bb-retrospectiva`). Trabalho
incompleto continua na próxima sprint.
