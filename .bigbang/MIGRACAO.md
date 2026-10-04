# Migração entre versões do Big Bang

O que muda em cada versão do framework e o que um projeto precisa fazer ao atualizar com `bb atualizar`.
SemVer: versão **maior** = o projeto precisa agir, e a seção diz como. A camada do projeto nunca é tocada.
Cada seção tem "O que muda" e "O que o projeto precisa fazer" ("Nada." quando não há passo manual).

## [0.10.0] - 2026-10-04

### O que muda

- Releases do framework com `bigbang-vX.Y.Z.tar.gz` (a pasta `.bigbang/`) e `.sha256`.
- `bb atualizar [versão]`: troca `.bigbang/` numa branch `framework/vX.Y.Z`, gera, verifica e abre o PR.

### O que o projeto precisa fazer

Nada.

## [0.9.0] - 2026-10-04

### O que muda

- Perfil deploy com o alvo vps-docker, candidata no staging, produção pelo digest e Voltar versão.

### O que o projeto precisa fazer

Nada.

## [0.8.0] - 2026-10-04

### O que muda

- As 20 skills, os hooks do Claude Code e `configurar-repositorio.sh`.

### O que o projeto precisa fazer

Nada.

## [0.7.0] - 2026-10-04

### O que muda

- Posse de tarefas por várias IAs (`bb assumir`, `bb liberar`).

### O que o projeto precisa fazer

Nada.

## [0.6.0] - 2026-10-04

### O que muda

- Trava de aceite, rastreabilidade, guarda da stack, segurança, CodeQL, `bb decisao`, `bb revisao aprovar`,
  `bb checklist producao`.

### O que o projeto precisa fazer

Nada.

## [0.5.0] - 2026-10-04

### O que muda

- Perfil compilado: candidata, promoção sem recompilar e tarefa de correção.

### O que o projeto precisa fazer

Nada.

## [0.4.0] - 2026-10-04

### O que muda

- Núcleo da esteira e as chaves `entrega.arquivo_versao` e `entrega.ecossistemas`.

### O que o projeto precisa fazer

Nada.

## [0.3.0] - 2026-10-03

### O que muda

- CLI `bb` (`init`, `config get`, `gerar`, `verificar`).

### O que o projeto precisa fazer

Nada.

## [0.2.0] - 2026-10-03

### O que muda

- Padrões obrigatórios e `AGENTS.base.md`.

### O que o projeto precisa fazer

Nada.

## [0.1.0] - 2026-10-03

### O que muda

- Primeira versão: estrutura, processo, modelos e ADRs.

### O que o projeto precisa fazer

Nada.
