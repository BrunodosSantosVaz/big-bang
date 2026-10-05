#!/usr/bin/env bash
# "Encerrar" (spec 14.2): redoes or completes the cleanup after a publication, and/or ends the sprint.
#   VERSAO=x.y.z : closes the milestone's issues (cards -> Concluído / Corrigido; epics -> Concluída), closes the
#                  milestone and deletes the merged branches of the release unit and release/x.y.z — only with the
#                  locks of CNABLens: exact name, tag and Release vX.Y.Z exist, branch contained in the tag and in main.
#                  Tags are never deleted or moved.
#   SPRINT=true  : records the end of the current sprint: "Sprint N · <início>" -> "Sprint N · <início> → <hoje>".
# Idempotent. Environment: VERSAO, SPRINT, SIMULAR, PROJETO_PLANEJAMENTO/EXECUCAO/BUGS, GITHUB_REPOSITORY, GH_TOKEN.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

if [ -z "${BB_CACHE_DIR:-}" ]; then  # board ids and options fetched once per run (projeto.sh)
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi

AQUI="$(cd "$(dirname "$0")" && pwd)"
PLAN="${PROJETO_PLANEJAMENTO:?}"; EXEC="${PROJETO_EXECUCAO:?}"; BUGS="${PROJETO_BUGS:?}"
R="${GITHUB_REPOSITORY:?}"; SIMULAR="${SIMULAR:-false}"; HOJE="${HOJE:-$(date -u +%F)}"
[ "$SIMULAR" = true ] && export DRY_RUN=1
projeto() { bash "$AQUI/projeto.sh" "$@"; }
run() { if [ "$SIMULAR" = true ]; then echo "[simulado] $*"; else "$@" >/dev/null; fi; }

apagar_se_seguro() { # <branch> <tag>
  local branch="$1" tag="$2" fora
  gh api "repos/$R/git/ref/heads/$branch" >/dev/null 2>&1 || return 0
  fora=$(gh api "repos/$R/compare/$tag...$branch" --jq '.ahead_by' 2>/dev/null || echo "?")
  [ "$fora" = 0 ] || { echo "::warning::$branch mantida: $fora commit(s) fora da tag $tag"; return 0; }
  fora=$(gh api "repos/$R/compare/main...$branch" --jq '.ahead_by' 2>/dev/null || echo "?")
  [ "$fora" = 0 ] || { echo "::warning::$branch mantida: $fora commit(s) fora da main"; return 0; }
  run gh api -X DELETE "repos/$R/git/refs/heads/$branch"
  echo "branch apagada: $branch"
}

if [ -n "${VERSAO:-}" ]; then
  v="${VERSAO#v}"; tag="v$v"
  [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::versão '$v' inválida"; exit 2; }
  gh api "repos/$R/git/ref/tags/$tag" >/dev/null 2>&1 || { echo "::error::a tag $tag não existe: a versão não foi publicada"; exit 1; }
  gh release view "$tag" --repo "$R" >/dev/null 2>&1 || { echo "::error::a Release $tag não existe"; exit 1; }
  m=$(gh api "repos/$R/milestones?state=all&per_page=100" --jq ".[] | select(.title == \"$tag\") | .number" | head -n 1)
  [ -n "$m" ] || { echo "::error::milestone $tag não encontrado"; exit 1; }
  echo "Encerrando $tag$([ "$SIMULAR" = true ] && echo " [SIMULAÇÃO]")"
  while IFS=$'\t' read -r n estado labels; do
    [ -n "$n" ] || continue
    [ "$estado" = closed ] || run gh issue close "$n" --repo "$R" --reason completed --comment "Publicado em produção na versão $tag."
    if [[ ",$labels," == *",epic,"* ]]; then projeto mover "$PLAN" "$n" "Concluída" >/dev/null || true
    elif [[ ",$labels," == *",bug,"* ]]; then projeto mover "$BUGS" "$n" "Corrigido" >/dev/null || true
    else projeto mover "$EXEC" "$n" "Concluído" >/dev/null || true; fi
    for branch in $(gh api "repos/$R/git/matching-refs/heads/" --jq '.[].ref' | sed 's|^refs/heads/||' \
        | grep -E "^(epico|teste|feature|docs|bugfix|hotfix)/$n-" || true); do
      apagar_se_seguro "$branch" "$tag"
    done
  done < <(gh api "repos/$R/issues?milestone=$m&state=all&per_page=100" \
    --jq '.[] | select(has("pull_request") | not) | "\(.number)\t\(.state)\t\([.labels[].name] | join(","))"')
  run gh api -X PATCH "repos/$R/milestones/$m" -f state=closed
  apagar_se_seguro "release/$v" "$tag"
fi

if [ "${SPRINT:-false}" = true ]; then
  atual=$(projeto sprints "$EXEC" | grep -E '^Sprint [0-9]+ · [0-9-]+$' | tail -n 1 || true)
  if [ -z "$atual" ]; then echo "Nenhuma sprint aberta."; else
    for painel in "$PLAN" "$EXEC"; do projeto sprint-renomear "$painel" "$atual" "$atual → $HOJE"; done
    echo "Sprint encerrada: $atual → $HOJE"
  fi
fi

# Housekeeping (DOC/processo 05): merged branches, loose issues, old PRs and open claims; reports, never fails.
SIMULAR="$SIMULAR" bash "$AQUI/faxina.sh" || echo "::warning::faxina não concluída: rode-a de novo pelo Encerrar"
