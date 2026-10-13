# Entrega

## Release cortada da `develop`

`bb release cut` (botão *Cut release*, primeiro com `dry_run=true`):

- calcula a versão, ou usa a informada;
- cria `release/x.y.z` a partir da `develop`;
- adquire a trava da versão;
- cria o milestone `vX.Y.Z`.

`bb release items` lista os épicos da release. Um épico que mudou o artefato sem homologação vai para produção com
**todas as suas flags desligadas** e fica "no escuro".

## Candidata e QA

O botão *Candidate* gera `vX.Y.Z-rc.N` e roda `bb pipeline candidate-ready`:

- os épicos vão para QA, ou para Releasing com `qa:not-applicable`;
- o campo Candidate é preenchido;
- o PR release → `main` é aberto uma vez.

Quem homologa depende da label de QA do épico:

| Label | Quem homologa |
| --- | --- |
| `qa:human` | O dono homologa a candidata e registra `qa:approved`, em qualquer modo e risco |
| `qa:agent` delegado pelo modo | Um agente declarado em `agents.names`, sem posse no épico nem nas tarefas, registra `bb qa verdict` para a candidata atual |

Quem entrega nunca homologa.

**Reprovação:**

- vale a decisão `qa:rejected` do dono ou, no QA delegado, o veredito `rejected` de um agente independente para a
  candidata atual;
- `bb qa reject N --reason "…"` (botão *QA reject*, que simula por padrão) devolve o épico e cria a tarefa de
  correção a partir da release;
- a candidata seguinte nunca sobrescreve a anterior.

## Publicação

O portão de `bb release gate` e `bb release publish` lê o conteúdo da **própria release**: `flags.toml` e os testes
pendentes, lidos como dado com `--content-dir`. Ele exige:

- cada épico com o QA cumprido ou no escuro com todas as flags desligadas em produção. QA cumprido significa estado
  Releasing, ou QA que as regras já deixam avançar (decisão do dono ou veredito independente);
- nenhuma flag vencida;
- testes de aceite pendentes só de épicos no escuro;
- nenhuma issue `blocks-production` aberta;
- a candidata igual à ponta da release e ao head do PR da release, verde no SHA exato;
- no autonomous, o alvo, o portão `publish` e a janela do contrato.

O botão *Publish* (`dry_run=false`) espera a aprovação do ambiente `production`, que o dono dá pela interface. A
versão digitada é validada (`x.y.z`) e nunca entra num script sem passar por variável de ambiente.

Depois da aprovação, a publicação:

1. mescla a release na `main`;
2. promove os mesmos bytes da candidata, sem recompilar;
3. conclui os épicos entregues e mantém no escuro os demais;
4. fecha o milestone;
5. devolve a `main` à `develop` (PR de sync com `conflict` se houver conflito);
6. libera a trava da versão;
7. remove os registros de deployment do próprio run (sucesso ou falha), mantendo a página do repositório limpa sem alterar o ambiente nem seus revisores.

Como `environment: production` é uma regra de proteção no nível do job, o runner só é despachado após a aprovação manual do dono. Enquanto a execução aguarda aprovação na interface do GitHub, o registro em Deployments permanece visível como pendente/em espera; ao ser concluída (com sucesso ou falha), o passo de limpeza (`if: always()`) marca o registro como inativo e o exclui pelo ID exato do run. Caso uma execução seja cancelada ou abandonada antes de rodar o job, a faxina periódica (`bb cleanup`) ou o comando manual `bb pipeline clean-deployments` realizam a higienização dos registros remanescentes.

Promoção que falha não conclui nenhum épico. Publicar de novo não duplica nada.

## Depois da publicação

- **Flags:** `bb flag list` mostra o estado. Ligar ou desligar é decisão do dono:
  `bb flag on|off <nome> --env production`. A flag ligada e estável é removida numa tarefa de limpeza.
- **Manutenção** (sem mudar o artefato): `maintenance/*` a partir da `main`, publicada com
  `bb release maintenance --pr N`. O botão *Publish maintenance* simula por padrão.
- **Voltar versão:** botão *Rollback* (perfil deploy), atrás da aprovação de `production`. Down migration nunca é
  automática.
- **Faxina:** `bb cleanup` (botão *Cleanup*, diário):
  - apaga só as branches mescladas de issues fechadas sem PR aberto;
  - relata as branches fora do padrão e as posses vencidas há mais de uma semana;
  - nunca toca na `main`, na `develop`, nas releases, nas tags nem nas refs de trava.
