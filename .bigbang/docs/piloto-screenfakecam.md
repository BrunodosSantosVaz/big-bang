# Piloto ScreenFakeCam (E11)

O épico E11 da especificação pede um sistema pequeno e real, feito do zero só pelo Big Bang, com a Fundação
completa, o esqueleto andante e um épico de verdade em produção; cada problema encontrado vira correção no
framework, e ao fim sai a 1.0.0. Este é o registro.

## O sistema

[ScreenFakeCam](https://github.com/BrunodosSantosVaz/screenfakecam): câmera para Android cujo visor é uma imagem
guardada no celular (zoom, enquadramento, obturador manual, foto nova na galeria) e leitor de QR code e código de
barras. Kotlin com Jetpack Compose, perfil **compilado** com o sistema `android` (APK assinado), repositório
público, GPL-3.0.

| Etapa | Resultado |
| --- | --- |
| Fundação F0–F5 | Produto, stack, design kit com protótipo navegável, GitHub montado, esteira instalada |
| Sprint 1 | Épico *Esqueleto andante*: v0.1.0 em produção (uma reprovação na homologação, corrigida pela tarefa de correção) |
| Sprint 2 | Épicos *Obturador e foto salva* (v0.2.0) e *Leitor de QR e código de barras* (v0.3.0) em produção |
| Teste do dono | Instalou o APK da Release num celular real: "funcionou tudo" |

Cada versão foi homologada pelo APK assinado publicado na pre-release (hash, atestação de origem e assinatura
conferidos) num emulador Android 15, e a produção publicou os mesmos bytes da candidata.

## O que o piloto mudou no framework (v0.11.0 a 1.0.0)

- Perfil compilado com o sistema `android`, extensão `.apk` e segredos de assinatura `BB_ASSINATURA_*` no build.
- Guarda da stack para o Gradle moderno (catálogo de versões, bundles, BOM), com falha explícita no que não entende.
- Testes de aceite em linguagem compilada: driver, pacote único, nome com o ID da regra (ADR-0003 do piloto).
- CI e varredura de segurança antes de existir código do artefato; *Publicar sem release* da Fundação logo após a F5.
- Montagem do GitHub: rulesets válidos antes da F5, validação de `dono/repo`, segredos pendentes pelo nome.
- *Regras do PR*: arquivos pela API paginada, PR da release julgado como integração, ponta atual do destino.
- *Mesclar PR* pela execução mais recente de cada check; kanban sem eventos descartados nem edição vazia.
- Checklist de produção desde a Fundação; release **por sprint ou por épico**, perguntado a cada sprint (ADR-0015).
- `bb atualizar` usado de verdade a cada correção (v0.10.2 → v0.12.0), com a label de revisão garantida.

## O que fica para depois da 1.0.0

- **Perfil deploy em servidor real** (E9, #99): validado em contêiner, falta um servidor do dono (as lacunas
  #112–#115 vieram do deploy do RBAPP).
- **Publicação sem o clique do dono** (#153): pedida pelo dono, bloqueada pela política de segurança do agente;
  depende de decisão explícita do dono.
- **Migração do CNABLens e do PrintRoute** (E12).
