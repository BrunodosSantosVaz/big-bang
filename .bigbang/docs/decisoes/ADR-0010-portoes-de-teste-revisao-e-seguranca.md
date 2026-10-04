# ADR-0010: Portões de testes, revisão e segurança

- **Situação:** aceita
- **Data:** 2026-10-04
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

O E6 transforma em ferramenta as regras de teste, revisão e segurança (seções 11.7 a 11.9 e 15.5). Várias exigem
escolhas que a especificação não fixa: como reconhecer a retirada de uma marca de pendente, onde rodar código do PR,
como verificar um checklist que depende da stack e como fixar ferramentas instaladas por `pip`.

## Decisão e justificativa

- **Trava de aceite** (`bb/acceptance.py`): PR de tarefa ou documentação só pode **retirar as marcas de pendente que
  citam a própria issue** (`bb aceite liberar` faz exatamente isso: uma marca-decorador some; uma marca embutida como
  `test.failing(` vira `test(`). PR de teste, de bug ou de hotfix pode **acrescentar** testes, nunca alterar ou apagar
  linha existente. Qualquer outra mudança precisa de `teste-alterado-aprovado`. A retirada das próprias marcas não
  conta como zona sensível (senão toda tarefa iria para o dono).
- **Conteúdo do PR lido como dado:** pendentes, rastreabilidade e guarda da stack rodam no job `regras`, com o `bb` e o
  `bigbang.toml` da branch de **destino** sobre um *worktree* da ponta do PR. O PR não muda as regras que o julgam;
  o `STACK.md` vem do PR (a linha nova vai no mesmo PR, com revisão do dono).
- **Rastreabilidade** (`bb/traceability.py`): uma declaração de teste (`testes.padrao_teste`) em `tests/aceite/` cita
  `RN-0042`, `RN0042` ou `rn0042` (sem letra antes); toda RN vigente é citada; RN nunca é apagada.
- **Guarda da stack** (`bb/stack_guard.py`): confere o **nome** de cada dependência direta de execução contra a tabela
  (npm, PyPI, Go, Cargo, Maven/Gradle, Composer, NuGet), ignorando as de desenvolvimento; ecossistema que ela não lê
  (Ruby, Elixir, Dart, Swift…) **falha explicitamente**. A faixa de versão da tabela é documentação; atualização maior
  passa pelo portão de tecnologia.
- **Regressão de bug** (`regressao.sh`) roda no `check`, não no `regras`: ela executa o código do primeiro commit do
  PR, e isso nunca acontece num job com token de escrita (SEG-18).
- **Decisões do dono** (`bb decisao`): comenta a frase do dono **antes** de pôr a label; `homologado`/`reprovado` se
  excluem; `dono:revisao-ia` tira `revisao-humana`. `bb revisao aprovar` recusa quando a revisão é do dono
  (`revisao-humana`, zona sensível, ou testes com `testes-revisao-humana`), salvo `dono:revisao-ia`.
- **Checklist de produção** (`bb/checklist.py`): cada um dos 11 itens diz em `docs/operacao/checklist-producao.md` como
  o projeto o verifica (`cmd:`, `portao:` ou `nao-se-aplica:`); item sem verificação reprova. Sempre ligados: o
  `.env.example` sem valores e documentado no README, e nenhum achado de segurança crítico ou alto aberto. Roda sobre a
  `release/x.y.z`.
- **Segurança** (`seguranca.sh`): Gitleaks, Opengrep e OSV-Scanner baixados por versão e **SHA-256** (o Opengrep não
  publica checksums; o hash foi calculado na versão fixada); regras do `opengrep-rules` fixadas por **commit**, só
  severidade ERROR; Bandit `1.9.4` num `venv` próprio, fixado por versão (o `pip` não fixa o hash das dependências
  transitivas — limitação registrada); **exceção ou falha da ferramenta conta como reprovação**; OSV reprova CVSS ≥ 7.
- **CodeQL** só em repositório público (em privado exige GitHub Advanced Security), com as linguagens detectadas.
- O merge e a publicação passam a exigir `check`, `regras` e `seguranca`.

## Consequências

### Positivas

- Cada portão tem teste que recusa o caso errado e aceita o certo; a varredura de segurança foi validada contra um
  segredo e código perigoso plantados.

### Negativas

- A guarda da stack não confere a faixa de versão.
- O Bandit fica fixado por versão, não por hash.

## Referências

- Especificação, seções 8.2, 11.7 a 11.9, 15.3 e 15.5.
- Opengrep: https://github.com/opengrep/opengrep · OSV-Scanner: https://google.github.io/osv-scanner/
