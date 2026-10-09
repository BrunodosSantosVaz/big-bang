---
name: bb-entregar-epico
description: Use para vamos homologar ou vamos publicar um épico ou bug. Mostra candidata e critérios, registra a decisão do dono e confere checklist e portão sem aprovar o ambiente de produção.
---

# Entregar épico ou bug

## Quando usar

Na homologação ou publicação de release por épico/bug; nunca como aprovação implícita de produção.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/processo/09-entrega.md`, `bigbang.toml`, épico/bug, critérios, documentação e candidata/staging.

## Passos

0. Entrega por sprint (combinada no início da sprint): quando todos os épicos da sprint estão prontos, rode
   Integrar release com `epico=sprint`; homologue cada épico da candidata única e publique uma vez.

1. Homologar: mostre link, versão/SHA, o que testar e critérios. Espere homologado ou reprovado com motivo.
   Registre `bb decisao homologado N --frase "palavras do dono"`, ou reprovado com a frase correspondente.
2. Reprovado: crie nova tarefa de correção no mesmo épico pelo botão Tarefa de correção, com motivo;
   fluxo normal até próxima candidata, sem sobrescrever a candidata anterior.
3. Publicar: execute `bb checklist producao`; confira homologação, docs, bloqueios de segurança, PR/CI no SHA exato,
   candidata intacta e changelog. Rode Publicar em produção com simular=true e mostre o portão.
4. Só com ordem explícita do dono nesta conversa execute simular=false. Logo depois, rode
   `bash .bigbang/esteira/nucleo/scripts/link-aprovacao.sh bb-publicar-producao.yml` e entregue ao humano que aprova
   o bloco que ele imprime: link direto do run e passos (Review deployments → producao → Approve and deploy).
   Não aprove por API. Publique o mesmo artefato/digest homologado, sem recompilar.
5. Confira release, saúde, fechamento e devolução de main. Para sem-release, siga o botão Publicar sem release e seu
   portão; Publicar sem release (`bb-publicar-sem-release.yml`) e Voltar versão (`bb-voltar-versao.yml`) também
   esperam aprovação: entregue o link e os passos do mesmo jeito.

## Pare e pergunte quando

Faltar homologação/ordem, qualquer check falhar, candidata mudar ou existir bloqueio. Retorno de versão também exige ordem.

## Nunca

Aprove ambiente producao, invente decisão, burle portão ou confunda CI verde com autorização de produção.

## Pronto quando

Épico/bug Concluída, versão/artefato conferidos e resultado de produção registrado; pendências não são sucesso.
