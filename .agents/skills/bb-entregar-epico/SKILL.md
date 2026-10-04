---
name: bb-entregar-epico
description: Use para vamos homologar ou vamos publicar um épico ou bug. Mostra candidata e critérios, registra a decisão do dono e confere checklist e portão sem aprovar o ambiente de produção.
---
<!-- Gerado pelo Big Bang v0.8.0 a partir de .bigbang/skills/bb-entregar-epico/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Entregar épico ou bug

## Quando usar

Na homologação ou publicação de release por épico/bug; nunca como aprovação implícita de produção.

## Antes de começar

Leia `AGENTS.md`, `.bigbang/processo/09-entrega.md`, `bigbang.toml`, épico/bug, critérios, documentação e candidata/staging.

## Passos

1. Homologar: mostre link, versão/SHA, o que testar e critérios. Espere homologado ou reprovado com motivo.
   Registre `bb decisao homologado N --frase "palavras do dono"`, ou reprovado com a frase correspondente.
2. Reprovado: crie nova tarefa de correção no mesmo épico pelo botão Tarefa de correção, com motivo;
   fluxo normal até próxima candidata, sem sobrescrever a candidata anterior.
3. Publicar: execute `bb checklist producao`; confira homologação, docs, bloqueios de segurança, PR/CI no SHA exato,
   candidata intacta e changelog. Rode Publicar em produção com simular=true e mostre o portão.
4. Só com ordem explícita do dono nesta conversa execute simular=false. Peça ao dono aprovar ambiente producao
   nas Actions; não aprove por API. Publique o mesmo artefato/digest homologado, sem recompilar.
5. Confira release, saúde, fechamento e devolução de main. Para sem-release, siga o botão Publicar sem release e seu portão.

## Pare e pergunte quando

Faltar homologação/ordem, qualquer check falhar, candidata mudar ou existir bloqueio. Retorno de versão também exige ordem.

## Nunca

Aprove ambiente producao, invente decisão, burle portão ou confunda CI verde com autorização de produção.

## Pronto quando

Épico/bug Concluída, versão/artefato conferidos e resultado de produção registrado; pendências não são sucesso.
