# 05 · Sprint

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

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
2. Registra a data de fim (botão *Encerrar*), que também roda a **faxina** (`faxina.sh`): apaga as branches
   mescladas cujo trabalho acabou (épico, tarefas, `framework/*`, `fundacao/*`, releases publicadas) e lista o que
   sobrou — branch fora do padrão ou sem PR, issue aberta num milestone já publicado, PR parado, posse aberta.
   A IA resolve cada ponto ou explica ao dono; nada fica para trás.
   Sobras fazem Encerrar falhar; resolva-as e repita o botão. O workflow Faxina também recupera a limpeza
   diariamente e por botão, complementando a faxina das publicações reais, sem apagar commits exclusivos ou branches com PR aberto.
3. Confere a documentação: o `README.md` descreve a versão em produção (DOC-15) e cada épico publicado teve a sua
   tarefa de documentação; o que faltar vira tarefa da próxima sprint.
4. Revisa os repositórios auxiliares do dono ligados ao sistema (testes, sandbox, protótipos): os sem uso são
   arquivados ou apagados com o ok do dono.
5. Roda `bb-retrospectiva`: o que funcionou, o que travou, o que mudar; atualiza `docs/memoria.md`.

## O que a automação faz sozinha

Cria branches e issues no *Iniciar sprint*; cria as branches das tarefas depois que o teste do épico é mesclado
(*Criar branches*); move os cartões.
