# 08 · Revisão

Nenhum PR é mesclado sem revisão. Quem escreveu o código não aprova o próprio raciocínio.

## Revisão pela IA (padrão: `revisao-ia`)

1. A IA roda o procedimento [`.bigbang/agents/revisor-pr.md`](../agents/README.md) com **contexto limpo** e
   ferramentas só de leitura: no Claude Code, o subagente `bb-revisor-pr`; nas outras IAs, uma sessão nova.
2. O revisor é hostil e trabalha com "evidência acima da narrativa": cada alegação do PR é marcada como
   **confirmada**, **parcial** ou **sem suporte**, com arquivo:linha ou teste.
3. Ele confere escopo, testes (nenhum enfraquecido), padrões (citando o número da regra), as cinco `SEG-IA-*`, a lista
   do nível ASVS, dependências, documentação, front, migrações e "slop".
4. Veredito **aprovado**: a IA roda `bb revisao aprovar <pr>`, que só põe `pr-aprovado` se o PR não exigir revisão
   humana. Veredito **reprovado**: a tarefa volta para *Code* com o comentário.

## Revisão humana (`revisao-humana`)

O cartão para em *Validar PR* e **só o dono** põe `pr-aprovado`.

## Troca automática por criticidade

- No refinamento, a IA marca `revisao-humana` no épico quando o trabalho é crítico (dinheiro, dado pessoal,
  autenticação). As tarefas herdam.
- A *Regras do PR* troca para `revisao-humana` pelo diff, quando o PR toca **zona sensível**: os caminhos de
  `seguranca.zonas_sensiveis` e, sempre, `.github/**`, `tests/aceite/**` (exceto no PR de teste do épico, que segue as
  labels `testes-revisao-*`), `STACK.md`, `DESIGN.md`, `PRODUTO.md`, `bigbang.toml`, `flags.toml` e os arquivos de
  dependência da stack.

## A última palavra é do dono

Se o dono puser `dono:revisao-ia` na issue ou no PR (ou disser na conversa), a revisão volta para a IA e **a troca
automática não é refeita**.

## Decisões do dono como labels

| O dono decide | Label | Onde | Libera |
| --- | --- | --- | --- |
| Refinamento aprovado | `refinamento-aprovado` | épico | protótipo ou *Próxima sprint* |
| Protótipo aprovado | `prototipo-aprovado` | épico | *Próxima sprint* |
| Testes aprovados (se `testes-revisao-humana`) | `testes-aprovados` | PR de teste | merge do teste e branches das tarefas |
| PR aprovado (se `revisao-humana`) | `pr-aprovado` | PR | merge no `epico/…` |
| Teste alterado | `teste-alterado-aprovado` | PR | a mudança em `tests/aceite/` |
| Homologado ou reprovado | `homologado` / `reprovado` | épico ou bug | *Publicar em produção* ou correção |
| Revisão de volta para a IA | `dono:revisao-ia` | issue ou PR | revisão pela IA |
| Produção | aprovação do ambiente `producao` | Actions | a publicação |

## `bb decisao`

Quando o dono decide na conversa, a IA roda:

```
bb decisao <label> <issue|pr> --frase "<palavras do dono>"
```

O comando comenta na issue a frase citada, com data e nome da IA, e só então põe a label.

## Limite de usar a mesma conta

Todas as IAs usam a conta do dono no GitHub, e o GitHub não distingue label posta pelo dono de label posta por uma
IA. A garantia vem de três camadas: a regra de ferro no `AGENTS.md`; o hook `proteger_comandos.py` no Claude Code, que
bloqueia pôr essas labels por fora do `bb decisao`/`bb revisao aprovar`; e o histórico da issue, que mostra cada
decisão com o comentário que a justifica. Para o GitHub cobrar isso por permissão, o caminho futuro é uma conta própria
(usuário robô) para as IAs, sem permissão de pôr labels de decisão.

## O que a automação faz sozinha

Troca para `revisao-humana` quando o diff toca zona sensível (salvo `dono:revisao-ia`); move o cartão para *Validar
PR* quando a CI fica verde num PR `revisao-humana`; mescla quando o PR tem `pr-aprovado` (ou `testes-aprovados`) e
checks verdes.
