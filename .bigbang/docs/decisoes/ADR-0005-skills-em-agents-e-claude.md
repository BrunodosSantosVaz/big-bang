# ADR-0005: Skills em `.agents/skills/`, com cópia em `.claude/skills/`

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

O Big Bang precisa funcionar com **qualquer IA** (decisão 7). As skills seguem o padrão aberto
[Agent Skills](https://agentskills.io), e várias ferramentas usam `.agents/skills/` como convenção comum. A
especificação (seção 5.6) pede para verificar, na documentação oficial, se o Claude Code lê `.agents/skills/`; se não
ler, o gerador escreve também uma cópia em `.claude/skills/`.

## Verificação (2026-10-03)

A documentação oficial do Claude Code ([Skills](https://code.claude.com/docs/en/skills)) lista onde as skills são
descobertas: `~/.claude/skills/<nome>/SKILL.md` (pessoal), `.claude/skills/<nome>/SKILL.md` (projeto),
`<subpasta>/.claude/skills/` (aninhadas), a pasta `skills/` de plugins, as pastas passadas com `--add-dir` e as
configurações gerenciadas da empresa. **A página não menciona `.agents/skills/`.** A mesma página confirma que as
skills do Claude Code seguem o padrão aberto Agent Skills e que um `SKILL.md` que usa só os campos do padrão carrega
no Claude Code sem mudanças.

Conclusão: **o Claude Code não lê `.agents/skills/`** nesta data.

## Fatores de decisão

- Qualquer IA encontra as skills na primeira sessão.
- Funciona no Windows (links simbólicos no Git exigem permissão especial lá).
- Uma única fonte de verdade.

## Opções consideradas

1. Gerar em `.agents/skills/bb-*/` e uma **cópia** idêntica em `.claude/skills/bb-*/`, conferida pelo `bb verificar`.
2. Gerar só em `.claude/skills/` e apontar as outras IAs para lá pelo `AGENTS.md`.
3. Link simbólico de `.claude/skills` para `.agents/skills`.

## Decisão e justificativa

Escolhida: **opção 1**. A fonte é `.bigbang/skills/`; o gerador escreve as duas cópias, e o `bb verificar` reprova
na CI se elas divergirem. A opção 3 falha no Windows; a opção 2 depende de cada IA seguir uma instrução de texto.

Para manter a portabilidade, o cabeçalho das skills usa **só os campos do padrão Agent Skills** (`name` igual ao nome
da pasta e `description`), sem extensões exclusivas do Claude Code.

## Consequências

### Positivas

- Claude Code e as IAs que seguem `.agents/skills/` encontram as mesmas skills.
- Nenhum link simbólico.

### Negativas

- Duas cópias no repositório (camada gerada). Mitigação: ambas geradas e conferidas pelo `bb verificar`.
- Se o Claude Code passar a ler `.agents/skills/`, as skills podem aparecer duplicadas; esta decisão deve ser revista a
  cada versão do Big Bang (a verificação é repetida antes de cada release do framework).

## Referências

- Claude Code — Skills: https://code.claude.com/docs/en/skills (consultada em 2026-10-03)
- Agent Skills: https://agentskills.io
- Especificação, seções 5.6 e 17 (E1 e E3).
