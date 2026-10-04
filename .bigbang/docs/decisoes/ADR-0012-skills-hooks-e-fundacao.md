# ADR-0012: Skills, hooks e a montagem do GitHub na Fundação

- **Situação:** aceita
- **Data:** 2026-10-04
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code; Codex

## Contexto e problema

O E8 entrega as 20 skills, os hooks do Claude Code e a prova de que o dono chega ao fim da F4 só conversando com a
IA. A revisão e a validação num repositório novo mostraram três lacunas: os hooks dependiam de um executável `python`
que nada conferia; os itens 3 a 7 da F4 não tinham script (a seção 5.2 lista `configurar-repositorio`); e exigir os
checks nos rulesets antes de a esteira existir bloqueava todos os PRs seguintes da Fundação.

## Decisão e justificativa

- **Skills** (`.bigbang/skills/bb-*`): só os campos do padrão Agent Skills (`name`, `description`), as seções da
  seção 15.1 e até ~150 linhas; procedimento longo fica em `.bigbang/processo/`. Toda ação no GitHub usa os comandos
  `bb` e os scripts, nunca reimplementa a lógica (conferido por `test_skills.py`).
- **Hooks** (`proteger_arquivos.py`, `proteger_comandos.py`): `PreToolUse` registrado no `.claude/settings.json`
  gerado, em *exec form* (`command` + `args`, sem shell, caminho ancorado em `CLAUDE_PROJECT_DIR`). Negam edição de
  `tests/aceite/`, `.bigbang/` e gerados; pedem confirmação para os arquivos de decisão; negam push forçado ou direto
  nas branches protegidas, apagar/mover tag e labels de decisão fora do `bb decisao`. O que não conseguem interpretar
  vira confirmação. São ajuda local: a garantia continua sendo a CI.
- **Python dos hooks:** o *exec form* chama `python`. O `bb init` confere que ele existe e é 3.11+ e diz como corrigir
  (no Ubuntu/Debian, `python-is-python3`), porque um hook que não sobe não bloqueia nada.
- **`configurar-repositorio.sh`** aplica, idempotente e com `--simular`, secret scanning, ambientes, rulesets
  (administradores do repositório ignoram as regras, porque a esteira empurra com o `PROJETO_TOKEN` do dono),
  variáveis e opções de merge. Os checks `check`/`regras`/`seguranca` só são exigidos depois da F5; o script é rodado
  de novo ao fim dela. Proteção que o plano não aplica é avisada, nunca simulada. Os segredos (itens 2 e 6) são do dono.
- **`criar-paineis.sh --simular`**, como a skill pede.

## Validação (2026-10-04)

No repositório `big-bang-fundacao-teste`, criado com o conteúdo do template, as skills conduziram F0 (`bb init`,
`develop`, licença), F1 (PRODUTO.md, ASVS L1), F2 (STACK.md, ADR-0001, pesquisa, C4, `bigbang.toml` completo), F3
(não se aplica: sem interface) e F4 (labels, painéis, proteções e variáveis), cada etapa com issue `fundacao`, branch,
PR e a frase do dono registrada antes do merge; o `bb status` leu os três painéis. As decisões do dono foram
simuladas; fica com o dono o `PROJETO_TOKEN`.

## Consequências

### Positivas

- A F4 deixa de ser um roteiro manual: o mesmo script vale para qualquer projeto e mostra o que o plano não oferece.

### Negativas

- Os hooks exigem o comando `python` no PATH.
- Entre a F4 e a F5, os rulesets ainda não exigem os checks.

## Referências

- Especificação, seções 5.2, 10/F4, 15.1 e 15.4. Hooks: https://code.claude.com/docs/en/hooks
