# 13 · Várias IAs ao mesmo tempo

Uma IA só começa uma tarefa depois de marcá-la como sua e confirmar que nenhuma outra marcou antes. Como todas as IAs
usam a conta do dono, o *assignee* (que continua sendo o dono) não distingue as IAs: a posse é a label `ia:<nome>`
mais um comentário.

## Nomes

Os nomes válidos estão em `ias.nomes` no `bigbang.toml` (por exemplo `claude-1`, `claude-2`, `codex-1`). Cada sessão
de IA usa um nome fixo durante o trabalho. O dono diz qual nome cada sessão usa.

## Protocolo de posse: `bb assumir <issue> <nome>`

É um comando, não uma instrução para a IA lembrar:

1. **Confere.** Relê a issue. Se já tem `ia:*` ou comentário de posse aberto, recusa e diz com quem está e desde
   quando. Se a tarefa está bloqueada (teste do épico não mesclado, dependência aberta) ou o nome não está em
   `ias.nomes`, recusa. Se a IA já tem `ias.tarefas_por_ia` tarefas abertas, recusa.
2. **Marca.** Põe `ia:<nome>` e comenta `<!-- bb:assumida nome=<nome> sessao=<uuid> -->` com o horário.
3. **Confirma.** Espera `ias.espera_confirmacao_segundos` e relê os comentários. Se outra IA marcou também, vale o
   comentário mais antigo (empate: ordem alfabética do nome); a perdedora retira a label e o comentário e pega outra
   tarefa. (Bloqueio otimista: marcar, depois verificar.)
4. **Isola.** Só então abre a branch da tarefa (criada pela esteira) numa pasta própria:

   ```
   git fetch origin && git worktree add ../<repo>-<nome> <branch-da-tarefa>
   ```

   Duas IAs na mesma pasta sobrescrevem os arquivos uma da outra.

## Liberação

- A label sai sozinha quando o PR é mesclado.
- `bb liberar <issue>` quando a IA desiste.
- Posse sem push há mais de `ias.trava_expira_horas` ganha a label `parada` e aparece no *Ver painéis*. Outra IA só a
  toma com `bb assumir --forcar`, por ordem do dono, registrada em comentário.

## Onde o paralelismo cabe

- O teste do épico é feito por **uma IA só**.
- As tarefas do mesmo épico podem andar em paralelo.
- O refinamento marca como dependentes as tarefas que mexem nos mesmos arquivos.
- Conflito na integração: o PR conflitante volta para *Code* com comentário.

## Limites

- No máximo `ias.tarefas_por_ia` tarefas abertas por IA (padrão 1).
- Uma IA nunca trabalha na pasta de outra.
- Revisão sempre com contexto limpo: a IA que escreveu não revisa (veja [08-revisao.md](08-revisao.md)).

## O que a automação faz sozinha

Retira a label de posse no merge do PR; marca `parada` nas posses vencidas; lista as posses no *Ver painéis*.
