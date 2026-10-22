# Execução de tarefas

1. **Posse:** `bb claim N <nome>` adquire a trava e abre a pasta própria (`git worktree`) na branch da tarefa,
   criada da `develop` (`test/`, `feature/`, `docs/`). Sem a trava confirmada, ninguém programa. Em sessões longas,
   use `bb renew N`.
2. **Testes de aceite:** a tarefa só retira as marcas de pendente dos testes dela (`bb acceptance unpend N`).
   Nenhuma outra linha de `tests/aceite/` muda sem `approved:test-change`.
3. **Código:**
   - testes escritos antes do código;
   - comportamento novo de um épico com `flag:required` fica atrás da flag dele, desligada por padrão
     (`flags.toml`);
   - a documentação tocada é atualizada no mesmo PR.
4. **Verificação:** o normal roda os comandos completos da stack; Flash e autonomous rodam os afetados
   (`bb test --base develop`) depois do código. Lint, tipos, scanners e `bb verify` são sempre obrigatórios.
5. **PR para a `develop`:** título em Conventional Commits e `Refs #N` no corpo (nunca `Closes`: quem fecha é o
   controlador). As regras do PR (`bb pipeline pr-rules`) conferem:
   - nome e destino da branch;
   - modo e marca própria;
   - trava dos testes de aceite;
   - `no-release`;
   - decisão de flag do épico.

   O conteúdo do PR é lido como dado, e um link simbólico que sai dele recusa o PR.
6. **CI:** o check obrigatório é um só, `gate`. Ele junta check, rules e security e falha quando um job necessário
   foi pulado.
7. **Revisão:** independente, com contexto limpo (subagente `bb-revisor-pr` ou sessão nova), ou do dono com
   `review:human`. Quem escreveu não aprova o próprio raciocínio.
8. **Merge:** `bb merge PR` (botão *Merge PR*) exige a aprovação (nos dois idiomas de label) e o `gate` verde no
   SHA exato, e nunca mescla na `main`. No merge, a tarefa vai para Done, a issue fecha e a trava é liberada.
9. **Saída limpa:** posse liberada, pasta removida e nenhuma branch órfã. A faxina diária apaga as branches
   mescladas de issues fechadas ([delivery.md](delivery.md)). Quem trabalhou em cópias locais (`git worktree`,
   clones extras) as remove ao terminar, depois de conferir que não há alteração pendente nem commit fora do remoto
   (e de salvar o que houver); issues concluídas são fechadas.
