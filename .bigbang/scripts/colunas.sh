#!/usr/bin/env bash
# Columns of the three boards (spec 11.1), as "Nome:COR" (GitHub colors: GRAY BLUE PURPLE YELLOW ORANGE GREEN RED
# PINK). Sourced by criar-paineis.sh; the pipeline scripts use these exact names.
# shellcheck disable=SC2034
COLUNAS_PLANEJAMENTO=(
  "Brainstorm:PURPLE" "Backlog:GRAY" "Backlog Refinement:YELLOW" "Validar protótipo:PINK"
  "Próxima sprint:BLUE" "Em desenvolvimento:ORANGE" "Homologação:ORANGE" "Concluída:GREEN"
)
COLUNAS_EXECUCAO=(
  "A fazer:GRAY" "Feature:BLUE" "Code:BLUE" "CI/PR:YELLOW" "Validar PR:PINK" "Pronto:GREEN" "Concluído:GREEN"
)
COLUNAS_BUGS=(
  "Novo:RED" "Em correção:BLUE" "CI/PR:YELLOW" "Validar PR:PINK" "Homologação:ORANGE" "Corrigido:GREEN"
)
