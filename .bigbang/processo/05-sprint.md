# 05 · Sprint

Sprint é um **período de trabalho de duração livre**: começa quando o dono inicia e termina quando ele encerra. Sprint
não é versão; cada épico tem a sua release.

## Iniciar

O dono diz **"vamos rodar a sprint"**. A IA (skill `bb-rodar-sprint`):

1. Confere os pré-requisitos: épicos em *Próxima sprint* que cumprem a *Definition of Ready*
   ([03-planejamento.md](03-planejamento.md)); `PROJETO_TOKEN` válido; CI verde na `develop`; nada pendente da sprint
   anterior.
2. Roda o botão **Iniciar sprint** com `simular=true` e mostra o plano.
3. Roda de verdade. Para cada épico pronto, o botão:
   - cria a opção do campo *Sprint* (`Sprint N · AAAA-MM-DD`);
   - cria `epico/<n>-<slug>` a partir da `develop` e, a partir dela, `teste/<n>-<slug>`;
   - cria a issue `teste-aceite`, as tarefas (uma por linha de *Tarefas previstas*) e a issue `documentacao`, como
     sub-issues do épico, **herdando as labels do épico** (`sem-release`, revisão de testes, revisão de PR);
   - marca as tarefas como bloqueadas pelo teste;
   - move o épico para *Em desenvolvimento*.

O botão recusa, com o motivo no log, épico sem `refinamento-aprovado`, épico `com-prototipo` sem
`prototipo-aprovado` e épico sem tarefas. Rodar de novo não duplica nada. Não pede versão.

## Rodar

Para cada épico, em ordem: teste do épico → tarefas → documentação (veja [06-execucao.md](06-execucao.md)). A cada
parada, a IA lista **o que espera pelo dono**: revisar testes, validar PR, homologar.

## Encerrar

O dono diz **"vamos encerrar a sprint"**. A IA:

1. Mostra o que foi publicado e o que ficou em andamento (que segue para a próxima sprint).
2. Registra a data de fim (botão *Encerrar*).
3. Roda `bb-retrospectiva`: o que funcionou, o que travou, o que mudar; atualiza `docs/memoria.md`.

## O que a automação faz sozinha

Cria branches e issues no *Iniciar sprint*; cria as branches das tarefas depois que o teste do épico é mesclado
(*Criar branches*); move os cartões.
