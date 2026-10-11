# Modos de trabalho

`project.mode` aceita `normal`, `flash` e `autonomous` (ADR-0025). Em todos os modos continuam obrigatórios:

- testes antes do código;
- revisão independente;
- scanners;
- documentação;
- rastreabilidade.

| Modo | Quem aprova os portões |
| --- | --- |
| normal | O dono, sempre, por decisão registrada |
| flash | O agente aprova o trabalho comum. Ficam com o dono a seleção e o cancelamento; refinamento, protótipo, testes e PR passam ao dono a partir do risco crítico; backlog, QA, publicação e flag, a partir do alto; com `qa:human`, a homologação também |
| autonomous | O agente aprova só o que o contrato `autonomy.toml` permite. Fora dele, o portão fica bloqueado e só a decisão registrada do dono libera |

## Flash

- A IA trata as reprovações comuns e chama o dono para as críticas.
- A suíte completa roda antes da candidata.
- A promoção do mesmo artefato reaproveita o recibo válido; integridade e saúde são sempre conferidas.

## Autonomous e o contrato

O `autonomy.toml` fica na raiz, em zona sensível, e o dono o revisa. Exemplo:

```toml
version = 1
targets = ["production"]          # ambientes em que o agente pode publicar
risk = ["low", "medium"]          # classes de risco delegadas
gates = ["backlog", "refinement", "prototype", "tests", "pr", "qa", "publish"]
flags = "owner"                   # quem liga feature flags: agent ou owner
wip = 2                           # épicos em andamento
attempts = 3                      # reprovações antes de blocked
max_cost_usd = 20
publish_window = "12:00-21:00"    # UTC
expires = "2027-03-31"            # o dono renova o contrato
```

- O contrato é lido do checkout que roda o `bb`. Na CI, esse checkout é a branch de destino, então um PR não
  amplia o contrato que o julga.
- Contrato ausente, inválido ou vencido bloqueia todos os portões.
- `wip` e `attempts` substituem os limites padrão.
- A publicação exige o alvo em `targets`, o portão `publish` e a hora dentro da janela.
- `bb autonomy check` (e `bb board create` no modo autonomous) recusa o repositório sem estes controles:
  - um ruleset que exige `gate` na `main` e na `develop`;
  - o ambiente `production` aceitando só a `main`.

  Também recusa repositório privado numa conta pessoal Free, onde essas proteções não são aplicadas.
- O agente nunca se apresenta como o dono: os recibos gravam `agent:<nome>`. Com o token compartilhado de uma conta
  pessoal, o nome do agente é declarado por quem roda o comando. A separação forte exige uma conta-bot por agente,
  que é opcional.
