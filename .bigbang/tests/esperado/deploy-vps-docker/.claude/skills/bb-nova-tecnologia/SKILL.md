---
name: bb-nova-tecnologia
description: Use antes de instalar qualquer dependência de execução ou tecnologia ausente da tabela de STACK.md. Compara alternativas e espera aprovação do dono para ADR e mudança da tabela.
---
<!-- Gerado pelo Big Bang v0.10.2 a partir de .bigbang/skills/bb-nova-tecnologia/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Nova tecnologia

## Quando usar

Quando trabalho em projeto fundado exigir dependência de execução fora da tabela. Na Fundação, use `bb-escolher-stack`.

## Antes de começar

Leia `AGENTS.md`, `STACK.md`, `.bigbang/processo/12-tecnologia-nova.md`, padrões de segurança e ADRs existentes.

## Passos

1. Explique necessidade e por que a stack existente não resolve. Pesquise fontes oficiais atuais, preferindo
   `bb-pesquisador` com contexto separado, e compare alternativas inclusive sem dependência nova.
2. Apresente custo, licença, manutenção, risco, segurança, impacto e incertezas. Recomende, mas espere o sim do dono.
3. Aprovado: ADR com a frase/alternativas e nova linha na tabela de dependências de `STACK.md` no mesmo PR,
   seguido de instalação, lockfile, testes e revisão humana. Preserve blocos gerados; regenere pelo bb se necessário.
4. Recusado: registre decisão e use alternativa compatível, sem instalar a proposta recusada.

## Pare e pergunte quando

A escolha mudar escopo ou garantias SEG-IA, ou as fontes não confirmarem manutenção/licença/custo.

## Nunca

Instale antes do sim, esconda dependência transitiva de execução ou edite a guarda da stack para passar.

## Pronto quando

PR de ADR/tabela aprovado pelo dono, ou alternativa implementável sem nova dependência escolhida.
