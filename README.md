# Big Bang

> Um framework para **uma pessoa, com uma ou mais IAs**, planejar, construir e manter sistemas profissionais:
> bem arquitetados, seguros, testados e 100% documentados.

**Versão:** 0.2.0 (em construção; a 1.0.0 sai depois do piloto) · **Licença do framework:** MIT

## O que é o Big Bang

O Big Bang é um repositório-modelo do GitHub que vira o próprio repositório do seu sistema. Você cria um
repositório a partir dele, abre qualquer IA para código na pasta e diz **"iniciar projeto"**. A partir daí, os
arquivos do framework conduzem a IA por todo o ciclo de vida do sistema, com você decidindo nos pontos de
controle. Ele não gera o sistema de uma vez: ele **governa** a construção, etapa por etapa, e cobra as regras por
ferramenta (CI, testes travados, portões), não por promessa.

| Etapa | O que a IA faz com você | O que fica gravado |
| --- | --- | --- |
| Fundação | Perguntas básicas do produto; escolha de stack, arquitetura e hospedagem; design kit com protótipo; guia de permissões e montagem do GitHub; geração da esteira; esqueleto andante até produção | `PRODUTO.md`, `STACK.md`, `DESIGN.md`, `bigbang.toml`, ADRs, diagramas C4, 3 painéis, workflows |
| Backlog | "Vamos refinar o backlog": perguntas por épico até o refinamento ser aprovado; protótipo quando o épico pede | Épicos refinados, regras de negócio, critérios de aceite, protótipos |
| Sprint | "Vamos rodar a sprint": confere pré-requisitos, cria o teste, as tarefas e a documentação de cada épico, programa, revisa | Issues, branches, PRs, testes, documentação |
| Entrega | Integração, candidata, homologação e publicação **por épico**; deploy ou compilação automáticos | Versões, Releases, changelog |
| Manutenção | Bugs, hotfix, auditoria de segurança, tecnologia nova só com você, atualização do próprio framework | Correções com teste de regressão, ADRs, relatórios |

## O que você precisa

- [Git](https://git-scm.com/)
- [GitHub CLI](https://cli.github.com/) (`gh`) autenticado (`gh auth login`)
- Python 3.11 ou superior
- Uma IA para código, como Claude Code, Codex ou Cursor
- Uma conta no GitHub

## Como começar

1. No GitHub, clique em **Use this template** → *Create a new repository*.
2. Clone o repositório novo: `gh repo clone <seu-usuario>/<seu-sistema>`.
3. Abra sua IA na pasta do repositório.
4. Diga: **"iniciar projeto"**.

## O que vai acontecer

A Fundação tem seis etapas. Cada uma vira uma issue e um PR, para ficar no histórico.

| Etapa | O que acontece | O que você decide |
| --- | --- | --- |
| **F0** · Ligar ao GitHub | A IA confere `git`, Python e `gh`, cria a `develop` e o `bigbang.toml` | Visibilidade (privado por padrão) e, se público, a licença |
| **F1** · Entrevista do produto | Até 10 perguntas, uma por vez, viram o `PRODUTO.md` | O que o sistema é, para quem, com quais dados |
| **F2** · Stack e arquitetura | A IA pesquisa e apresenta de 2 a 3 opções completas, com custo e riscos | A stack, a arquitetura e a hospedagem |
| **F3** · Design kit | Identidade, tokens, padrões de tela e protótipo navegável (se houver interface) | Aprovar o design e o protótipo |
| **F4** · Montar o GitHub | Passo a passo de permissões; painéis, labels, ambientes e travas | Executar cada passo de permissão (tokens e segredos são seus) |
| **F5** · Esteira e esqueleto andante | A IA gera a esteira e leva a menor versão do sistema até produção | Aprovar a publicação em produção |

## Depois da Fundação

O dia a dia é conversa. Você diz a intenção com as suas palavras; a IA reconhece o pedido, faz e termina dizendo o
próximo passo e o que depende de você.

| Você diz | O que acontece |
| --- | --- |
| "Ideia: …" | Vira um épico em *Brainstorm* |
| "Vamos refinar o backlog" | Perguntas por épico até o refinamento ser aprovado |
| "Vamos montar o protótipo" | Protótipo navegável no padrão do `DESIGN.md` |
| "Vamos rodar a sprint" | Teste de cada épico, tarefas, documentação, revisão |
| "Próxima tarefa" / "Codar #n" | A IA assume, programa e abre o PR |
| "Vamos homologar o épico N" | Link da candidata, o que testar e os critérios |
| "Vamos publicar o épico N" | Publicação em produção, com a sua aprovação no ambiente `producao` |
| "Vamos encerrar a sprint" | Resumo, pendências e retrospectiva |
| "Bug: …" / "Corrigir #n" / "Hotfix #n" | Teste que falha primeiro, depois a correção |
| "Audita a segurança" | Relatório e issues `[Segurança]` |
| "Como está o projeto?" | Resumo dos painéis e do que espera por você |
| "Atualizar o Big Bang" | PR com a versão nova do framework |

Tudo também pode ser feito pelos botões das GitHub Actions (*Run workflow*), sempre com `simular=true` por padrão.

## Documentação do framework

- Especificação completa: [`.bigbang/docs/especificacao.md`](.bigbang/docs/especificacao.md)
- Processo, passo a passo: [`.bigbang/processo/`](.bigbang/processo/)
- Decisões do framework (ADRs): [`.bigbang/docs/decisoes/`](.bigbang/docs/decisoes/)

## Licença

O **framework** Big Bang (tudo que está em `.bigbang/` e os arquivos gerados a partir dele) é distribuído sob a
[licença MIT](LICENSE).

O **sistema que você criar** a partir do Big Bang é seu: o código pertence a você, que escolhe a licença dele,
inclusive fechada. A única obrigação é manter o aviso de copyright do framework, que na Fundação vai para
`.bigbang/LICENSE`.
