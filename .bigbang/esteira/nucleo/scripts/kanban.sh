#!/usr/bin/env bash
# "Kanban" (spec 11.1): moves the cards from GitHub events and turns the epic form answers into labels.
# Dragging a card triggers nothing (user Projects emit no events), so every owner decision is a label.
#
#   issue opened (epic|task|teste-aceite|documentacao|bug) -> Brainstorm | A fazer | Novo
#   epic opened/edited ............ form answers -> labels (on edit, only the answers that changed)
#   bug opened .................... Severidade answer -> severidade:*
#   label refinamento-aprovado .... epic -> Validar protótipo (com-prototipo) or Próxima sprint
#   label prototipo-aprovado ...... epic -> Próxima sprint
#   label reprovado ............... epic -> Em desenvolvimento | bug -> Em correção
#   push teste|feature|docs/<n>-* . created -> Feature, then Code | bugfix|hotfix/<n>-* -> Em correção
#   PR opened ..................... CI/PR
#   CI green (workflow_run) ....... PR needing human review -> Validar PR
#   PR merged into epico/* ........ Pronto | closed without merge -> Code / Em correção
#
# Environment: EVENT, ACTION, ISSUE, LABEL, BODY_FROM (previous body on "edited"), REF_NAME, CREATED, DELETED,
# HEAD_REF, BASE_REF, MERGED, DRAFT, PR_LABELS, PR_NUMBER (workflow_run), CONCLUSION (workflow_run),
# PROJETO_PLANEJAMENTO/EXECUCAO/BUGS, GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN). BB as in regras-pr.sh.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

if [ -z "${BB_CACHE_DIR:-}" ]; then  # board ids and options fetched once per run (projeto.sh)
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi

AQUI="$(cd "$(dirname "$0")" && pwd)"
PLAN="${PROJETO_PLANEJAMENTO:?}"; EXEC="${PROJETO_EXECUCAO:?}"; BUGS="${PROJETO_BUGS:?}"
R="${GITHUB_REPOSITORY:?}"
read -r -a BB <<<"${BB:-python3 .bigbang/bin/bb.py}"
mover() { bash "$AQUI/projeto.sh" mover "$@"; }
labels_de() { gh api "repos/$R/issues/$1" --jq '[.labels[].name] | join(",")'; }
tem() { [[ ",$1," == *",$2,"* ]]; }

# kind of an issue branch and its number: "feature 12"; empty when the branch is not an issue branch
branch_issue() {
  if [[ "$1" =~ ^(teste|feature|docs|bugfix|hotfix)/([0-9]+)- ]]; then echo "${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"; fi
}

formulario_do_epico() {
  local corpo antes="" mudancas args=()
  corpo=$(gh api "repos/$R/issues/$ISSUE" --jq '.body // ""')
  if [ "${ACTION:-}" = edited ]; then
    antes=$(mktemp); printf '%s' "${BODY_FROM:-}" >"$antes"; args=(--antes "$antes")
  fi
  mudancas=$(printf '%s' "$corpo" | "${BB[@]}" esteira formulario "${args[@]}")
  [ -z "$antes" ] || rm -f "$antes"
  local add=() remove=() linha
  while IFS= read -r linha; do
    case "$linha" in +*) add+=("${linha#+}") ;; -*) remove+=("${linha#-}") ;; esac
  done <<<"$mudancas"
  local editar=(gh issue edit "$ISSUE" --repo "$R")
  [ "${#add[@]}" -eq 0 ] || editar+=(--add-label "$(IFS=,; echo "${add[*]}")")
  [ "${#remove[@]}" -eq 0 ] || editar+=(--remove-label "$(IFS=,; echo "${remove[*]}")")
  if [ "${#editar[@]}" -gt 4 ]; then
    "${editar[@]}" >/dev/null
    echo "Épico #$ISSUE: labels do formulário: +${add[*]:-} -${remove[*]:-}"
  fi
}

severidade_do_bug() {
  local label
  label=$(gh api "repos/$R/issues/$ISSUE" --jq '.body // ""' | "${BB[@]}" esteira severidade)
  [ -z "$label" ] || gh issue edit "$ISSUE" --repo "$R" --add-label "$label" >/dev/null
}

evento_issue() {
  local labels; labels=$(labels_de "$ISSUE")
  case "${ACTION:-}" in
    opened|reopened)
      if tem "$labels" epic; then mover "$PLAN" "$ISSUE" Brainstorm "-"; formulario_do_epico; fi
      if tem "$labels" task || tem "$labels" teste-aceite || tem "$labels" documentacao; then
        mover "$EXEC" "$ISSUE" "A fazer" "-"
      fi
      if tem "$labels" bug; then mover "$BUGS" "$ISSUE" Novo "-"; severidade_do_bug; fi
      ;;
    edited)
      if tem "$labels" epic; then formulario_do_epico; fi
      ;;
    labeled)
      case "${LABEL:-}" in
        refinamento-aprovado)
          if tem "$labels" epic; then
            if tem "$labels" com-prototipo; then
              mover "$PLAN" "$ISSUE" "Validar protótipo" "Brainstorm|Backlog|Backlog Refinement|-"
            else
              mover "$PLAN" "$ISSUE" "Próxima sprint" "Brainstorm|Backlog|Backlog Refinement|-"
            fi
          fi ;;
        prototipo-aprovado)
          if tem "$labels" epic; then mover "$PLAN" "$ISSUE" "Próxima sprint" "Validar protótipo"; fi ;;
        reprovado)
          if tem "$labels" epic; then mover "$PLAN" "$ISSUE" "Em desenvolvimento" "Homologação"; fi
          if tem "$labels" bug; then mover "$BUGS" "$ISSUE" "Em correção" "Homologação"; fi ;;
        epic) mover "$PLAN" "$ISSUE" Brainstorm "-" ;;
        task|teste-aceite|documentacao) mover "$EXEC" "$ISSUE" "A fazer" "-" ;;
        bug) mover "$BUGS" "$ISSUE" Novo "-" ;;
      esac
      ;;
  esac
}

evento_push() {
  [ "${DELETED:-false}" = true ] && return 0
  local tipo n
  read -r tipo n <<<"$(branch_issue "${REF_NAME:?}")"
  [ -n "${n:-}" ] || return 0
  case "$tipo" in
    teste|feature|docs)
      if [ "${CREATED:-false}" = true ]; then mover "$EXEC" "$n" Feature "A fazer|-"
      else mover "$EXEC" "$n" Code "A fazer|Feature"; fi ;;
    *) mover "$BUGS" "$n" "Em correção" "Novo|-" ;;
  esac
}

evento_pr() {
  local tipo n
  read -r tipo n <<<"$(branch_issue "${HEAD_REF:?}")"
  [ -n "${n:-}" ] || return 0
  local painel="$EXEC" voltar=Code inicio="A fazer|Feature|Code|-"
  if [ "$tipo" = bugfix ] || [ "$tipo" = hotfix ]; then painel="$BUGS"; voltar="Em correção"; inicio="Novo|Em correção|-"; fi
  case "${ACTION:?}" in
    opened|reopened|ready_for_review)
      if [ "${DRAFT:-false}" = true ] && [ "$ACTION" != ready_for_review ]; then return 0; fi
      mover "$painel" "$n" "CI/PR" "$inicio" ;;
    closed)
      if [ "${MERGED:-false}" = true ]; then
        if [[ "${BASE_REF:-}" == epico/* ]]; then mover "$EXEC" "$n" Pronto "A fazer|Feature|Code|CI/PR|Validar PR|-"; fi
      else
        mover "$painel" "$n" "$voltar" "CI/PR|Validar PR"
      fi ;;
  esac
}

# CI finished on a PR branch: green + human review -> "Validar PR" (the owner is the next to act)
evento_ci() {
  [ "${CONCLUSION:-}" = success ] || return 0
  local tipo n labels issue_labels
  read -r tipo n <<<"$(branch_issue "${HEAD_REF:?}")"
  [ -n "${n:-}" ] && [ -n "${PR_NUMBER:-}" ] || return 0
  labels=$(labels_de "$PR_NUMBER"); issue_labels=$(labels_de "$n")
  tem "$labels,$issue_labels" dono:revisao-ia && return 0
  local humana=false
  if [ "$tipo" = teste ]; then tem "$issue_labels" testes-revisao-humana && humana=true
  elif tem "$labels" revisao-humana; then humana=true; fi
  [ "$humana" = true ] || return 0
  local painel="$EXEC"
  if [[ "$tipo" =~ ^(bugfix|hotfix)$ ]]; then painel="$BUGS"; fi
  mover "$painel" "$n" "Validar PR" "CI/PR"
}

case "${EVENT:?}" in
  issues) evento_issue ;;
  push) evento_push ;;
  pull_request|pull_request_target) evento_pr ;;
  workflow_run) evento_ci ;;
  *) echo "Evento $EVENT ignorado." ;;
esac
