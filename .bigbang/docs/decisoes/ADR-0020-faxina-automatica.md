# ADR-0020: Faxina automática e encerramento que aponta sobras

- **Situação:** aceita
- **Data:** 2026-10-09
- **Decisores:** Bruno dos Santos Vaz (dono); Codex

## Contexto

A publicação v1.5.4 do próprio Big Bang deixou doze branches incorporadas no GitHub. A distribuição própria
não chamava a faxina; nos consumidores, Encerrar transformava falhas da limpeza em aviso. O dono pediu a
correção e a atualização de Snake3310 e ScreenFakeCam, sem novo deploy ou compilação dos aplicativos (#205).

## Decisão

- O workflow próprio Faxina do Big Bang responde à conclusão de CI/release de push, fechamento de issues,
  agenda diária e botão com simulação. Usa somente scripts da main, sem código, cache ou artefatos de PR.
- Antes da exclusão, exige tag correspondente à ponta da main e VERSION, release estável com pacote/hash,
  main contida na develop, árvores iguais e última CI de push bem-sucedida nos dois SHAs exatos.
  Enquanto um portão normal estiver pendente, informa que aguarda e não apaga nada; falha de CI nunca prova
  sucesso. O próximo evento ou a agenda recupera a limpeza.
- Nos consumidores, o workflow Faxina roda após publicação/encerramento e diariamente; checkout da main
  e token do próprio projeto. Conserva as regras existentes de branch incorporada, issue concluída e PR.
- `FAXINA_EXIGIR_LIMPA=true` torna sobras uma falha explícita. Encerrar usa esse modo e propaga o resultado,
  sem anunciar sucesso da limpeza. O encerramento pode já ter registrado a data ou fechado o milestone;
  corrigir as sobras e repetir é idempotente e não desfaz publicação.
- Main, develop, tags, branches com PR aberto e commits exclusivos não são apagados. Sobras exclusivas
  exigem análise e preservação humana; não se arquiva nem mescla trabalho automaticamente para esconder avisos.
- O pacote do framework recebe patch imutável; os aplicativos recebem atualização por Publicar sem release
  quando o diff dos caminhos do artefato é vazio. Não há nova imagem/APK nem mudança da versão do aplicativo.

## Consequências e limites

A limpeza deixa de depender de lembrar um comando após cada release. Permissões de escrita ficam no job
de limpeza; testes usam Git real e GitHub simulado para comprovar os portões e a preservação. Não há exclusão
de branches locais ou stashes das máquinas do dono. Trabalho futuro e Dependabot continuam seguindo revisão.

## Referências

- Issue #205; `.bigbang/processo/05-sprint.md`; ADR-0014 e ADR-0017.
- [Eventos e segurança de workflow_run](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run).
- [API de execuções dos workflows](https://docs.github.com/en/rest/actions/workflow-runs).
