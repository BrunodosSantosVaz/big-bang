---
name: bb-entregar-epico
description: Use para vamos homologar ou vamos publicar. Corta a release da develop, leva a candidata a QA, registra a decisão do dono e confere o portão da publicação sem aprovar o ambiente production.
---

# Entregar épicos (v3)

## Quando usar

Para cortar a release, homologar a candidata e publicar. CI verde nunca é aprovação de produção.

Consulte `project.mode` e `.bigbang/pipeline/process/modes.md`. No normal, o dono decide nos portões. No Flash, você aprova o trabalho comum e chama o dono para o crítico. No autonomous, você só age dentro do `autonomy.toml`; fora dele, o portão fica bloqueado até a decisão registrada do dono.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/pipeline/process/delivery.md`, `bigbang.toml`, `flags.toml`, os épicos com os
critérios, a documentação e a candidata ou o staging.

## Passos

1. Cortar: com os épicos prontos (sub-issues fechadas), rode `bb release cut` (botão *Cut release*, primeiro com
   `dry_run=true`). Ele cria `release/x.y.z` da `develop`, a trava da versão e o milestone; `bb release items`
   lista os épicos. Épico que mudou o artefato sem homologação vai com a flag desligada.
2. Candidata: o botão *Candidate* gera `vX.Y.Z-rc.N` e roda `bb pipeline candidate-ready`. Os épicos vão para QA
   (ou para Releasing com `qa:not-applicable`) e o PR release → `main` é aberto.
3. Homologar: mostre o link, a versão e o SHA, o que testar e os critérios.
   - `qa:human`: espere a decisão do dono e registre `bb decision qa:approved N --quote "…"`.
   - Reprovação: registre `qa:rejected` e rode `bb qa reject N --reason "…"` (botão *QA reject*). Ele cria a tarefa
     de correção a partir da release; a candidata seguinte nunca sobrescreve a anterior.
   - `qa:agent` delegado pelo modo: um agente sem posse no épico homologa a candidata atual e registra
     `bb qa verdict N --candidate vX.Y.Z-rc.N --digest sha256:… --verdict approved --agent SEU-NOME`.
4. Publicar: rode `bb release gate --epic N…` e `bb release publish --version x.y.z --dry-run` e mostre o portão.
   O portão confere:
   - homologação ou flag desligada;
   - pendências só de épicos no escuro;
   - nenhuma `blocks-production`;
   - candidata igual à ponta da release;
   - PR verde.
5. Só com a ordem do dono nesta conversa (ou dentro do `autonomy.toml` no autonomous) rode o botão *Publish* com
   `dry_run=false`. Entregue ao humano que aprova o link do run e os passos que o job imprime (Review deployments →
   production → Approve and deploy). Não aprove por API. A publicação:
   - mescla na `main`;
   - promove os mesmos bytes da candidata;
   - conclui os épicos entregues e deixa os do escuro com a flag desligada;
   - fecha o milestone e devolve a `main` à `develop`.
6. Depois: confira a saúde. Ligar a flag de um épico no escuro é decisão do dono (`bb flag on <nome>`). Mudança sem
   artefato sai de `maintenance/*` (`bb release maintenance --pr N`). Voltar versão usa o botão *Rollback*, também
   atrás da aprovação.

## Pare e pergunte quando

Faltar homologação ou ordem, qualquer check falhar, a candidata mudar ou existir bloqueio. Voltar versão também
exige ordem.

## Nunca

Aprove o ambiente production, invente decisão, homologue o que você mesmo entregou, recompile o artefato
homologado ou burle o portão.

## Pronto quando

Os épicos estão em Done (ou entregues no escuro, com a flag registrada), a versão e o digest foram conferidos e o
resultado da produção está registrado. Pendência não é sucesso.
