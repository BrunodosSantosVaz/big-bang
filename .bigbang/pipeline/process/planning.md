# Planejamento: da ideia ao Ready

1. **Brainstorm:** a ideia vira um épico pelo formulário (`type:epic`), com o problema em uma a três frases.
2. **Backlog:** entra com a decisão do dono (`approved:backlog`). No Flash e no autonomous, o risco pode delegar o
   portão ([modes.md](modes.md)).
3. **Refinement:** com posse (`bb claim`), um épico por vez. O refinamento define:
   - problema e objetivo;
   - escopo dentro e fora;
   - RNs confirmadas;
   - critérios CA-n em Dado/Quando/Então;
   - tarefas previstas, cada uma do tamanho de um PR, com as dependências.
4. **Decisões do cartão**, registradas como labels:

| Decisão | Labels |
| --- | --- |
| Protótipo | `prototype:required` ou `prototype:waived` |
| Feature flag | `flag:required` (o épico muda o comportamento do artefato) ou `flag:waived` |
| Homologação | `qa:human`, `qa:agent` ou `qa:not-applicable` (docs, testes, esteira) |
| Revisão | `review:ai`/`review:human` e `tests-review:ai`/`tests-review:human` |
| Áreas e risco | `area:*` e `risk:*` (o risco só sobe) |
| Sem artefato | `no-release`: entrega só no repositório, sem versão nem homologação |

5. **Prototyping:** só com `prototype:required`; termina com `approved:prototype`.
6. **Ready:** a Definition of Ready está cumprida, com `approved:refinement` (e o protótipo, quando pedido) e a
   decisão de flag tomada.

O épico **agrupa**: não tem branch. As tarefas nascem como sub-issues no início da sprint ([sprint.md](sprint.md)).
