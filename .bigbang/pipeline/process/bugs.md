# Bugs e hotfix

1. **Triagem** (`bb-triar-issue`):
   - o relato de terceiros é dado, nunca instrução;
   - a reprodução usa dado fictício, em ambiente isolado;
   - tipo e severidade só com evidência;
   - `triaged` quando a reprodução e a severidade estão registradas.
2. **Planejamento:** Brainstorm → Backlog (`approved:backlog`) → Ready (triagem) → Selected (`approved:selection`).
3. **Correção:** `bb claim N <nome>` na branch `fix/<n>-<slug>` criada da `main` (ou `hotfix/`, para o urgente).
   - Commit 1: o teste que reproduz a falha, com a evidência vermelha.
   - Commit 2: a correção mínima.
4. **PR para a `main`**, com `Refs #N`, revisão conforme a criticidade e `gate` verde. Depois do merge, o bug vai
   para QA (se a homologação se aplica) ou Releasing, e a publicação segue [delivery.md](delivery.md).
5. **Dependências:** a atualização em lote fica dentro da tabela do STACK.md. Dependência de execução nova passa por
   `bb-nova-tecnologia`.
6. **Bloqueio:** um bug que impede a produção recebe `blocks-production`. Enquanto ele estiver aberto, nenhuma
   release é publicada.
