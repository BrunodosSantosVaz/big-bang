# ADR-0011: Posse de tarefas, isolamento e inatividade das IAs

- **Situação:** aceita
- **Data:** 2026-10-04
- **Decisores:** Bruno dos Santos Vaz (decisões da especificação); Codex (implementação)

## Contexto e problema

O E7 implementa a seção 13. Todas as IAs usam a conta do dono; o assignee não identifica a sessão.
Labels e comentários precisam coordenar a disputa, a liberação e a retomada de uma tarefa sem sobrescrever arquivos.

## Decisão e justificativa

- `bb assumir` confere nome, estado, bloqueadores e limite por IA; marca a label e o comentário com UUID;
  aguarda a janela configurada; ganha o comentário mais antigo, com nome e ID como desempates.
- A confirmação exige pelo menos um segundo, pois o horário de comentários do GitHub tem resolução de segundos.
  Espera zero permitia duas confirmações antes do desempate; o caso foi corrigido e coberto por regressão.
- Bloqueadores mesclados só contam no épico correto; fechar a issue de teste sem mesclar seu PR não libera a tarefa.
- O rollback procura o próprio UUID, mesmo quando o POST foi aceito e sua resposta se perdeu. Comentários de terceiros
  são ignorados. Tentativas perdedoras não apagam a label de outra sessão com o mesmo nome.
- O worktree só nasce depois da posse. A branch local acompanha o remoto apenas por avanço direto condicional;
  divergência, pasta existente ou branch já aberta causam erro e liberação da posse. O recibo da sessão fica nos
  metadados do Git; `bb liberar` exige esse recibo e preserva a pasta e o histórico.
- O Kanban acrescenta um comentário de atividade por push, com UUID da sessão e horário do servidor do GitHub.
  A telemetria é somente acrescentada: um push concorrente com a liberação não reabre o comentário de posse.
  A data do commit não indica quando ele foi enviado.
- O cron marca `parada` depois do prazo configurado, conferindo a sessão antes e depois da alteração; também
  retira uma marca antiga se a sessão já recebeu push. A label é informativa; `--forcar` exige a frase do dono e
  recalcula a inatividade após registrar a ordem, recusando a retomada se a sessão mudou ou recebeu push.
- `bb status` e Ver painéis só leem. Alertam sobre posses, flags e segurança; a criação da tarefa de limpeza da flag
  continua sendo responsabilidade da IA. Datas/estados inválidos em `flags.toml` reprovam a leitura.
- O registro de flags tem criação e expiração, sem data de ativação. O alerta de flag antiga em produção usa a criação
  como referência conservadora, informando a data explicitamente.

## Evidência no sandbox

Na issue [#20 do sandbox](https://github.com/BrunodosSantosVaz/big-bang-sandbox/issues/20), dois processos independentes
executaram `bb assumir 20`, com os nomes `claude-1` e `codex-1` e espera de 10 segundos.
`claude-1` confirmou a posse e criou seu worktree; `codex-1` perdeu a disputa (código 7).
O estado final tinha uma label e um comentário ativo (ID 5976560737).
`bb liberar 20` retirou a posse e preservou o histórico. O worktree estava limpo e foi removido depois da conferência.
A validação completa foi registrada em comentário na issue, fechada ao fim do teste.

## Consequências

- A garantia é um protocolo otimista, com releitura e desempate; não é uma transação distribuída do GitHub.
  As IAs só começam depois de o comando confirmar e criar o worktree.
- Os workflows de atividade e inatividade precisam do `PROJETO_TOKEN`. O sandbox foi validado com autenticação local
  do dono, executando os mesmos comandos; os disparos automáticos em Actions ainda dependem desse segredo.
- Falha total de comunicação impede garantir a limpeza remota; o CLI informa a falha, e uma sessão só retoma
  a posse vencida por ordem do dono. Ninguém deve programar após uma confirmação que falhou.
- O protocolo e o CLI têm testes de concorrência, bloqueios, limite, rollback, isolamento, retomada e relatórios.

## Referências

- [Especificação, seção 13](../especificacao.md#13-várias-ias-ao-mesmo-tempo)
- [API de comentários](https://docs.github.com/en/rest/issues/comments)
- [API de dependências de issues](https://docs.github.com/en/rest/issues/issue-dependencies)
