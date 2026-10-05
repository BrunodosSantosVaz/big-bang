# ADR-0015: Release por sprint ou por épico

- **Situação:** aceita (complementa a ADR-0004)
- **Data:** 2026-10-05
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

A ADR-0004 fez uma release por épico. No piloto ScreenFakeCam, uma sprint com dois épicos virou duas candidatas,
duas homologações e duas publicações, e um épico que dependia do outro esperou a publicação inteira do primeiro. O
dono: "falar pra vc um epico por vez ficou páia em, ta demorando muito, era mais dinamico quando rodava todos epicos
na sprint" e "o framework poderia ser flexível e perguntar ao rodar cada sprint".

## Decisão e justificativa

- *Integrar release* aceita `epico=<n>`, uma lista (`epico=36,37`) ou `epico=sprint` (todos os épicos em *Em
  desenvolvimento* ou *Homologação* no painel Planejamento, menos os `sem-release`). Cada épico passa pela mesma
  conferência de completude; todos entram na mesma `release/x.y.z` (um merge `--no-ff` por épico), no mesmo
  milestone e no mesmo changelog.
- Um épico que depende de outro **da mesma release** não é recusado.
- Publicar em produção e Encerrar já tratam todas as unidades do milestone: cada épico precisa de `homologado`.
- A skill `bb-rodar-sprint` pergunta ao dono, no início de cada sprint, se a entrega é por sprint ou por épico.

## Consequências

### Positivas

- Uma candidata, uma homologação e uma publicação por sprint, quando o dono quer.

### Negativas

- Uma reprovação segura a release inteira até a correção (rc.N+1), como já acontecia com um épico só.

## Referências

- ADR-0004; piloto ScreenFakeCam, Sprint 2 (#36, #37); issue #152.
