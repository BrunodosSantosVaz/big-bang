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
sobras=0
[ "$SIMULAR" = true ] && export DRY_RUN=1
projeto() { bash "$AQUI/projeto.sh" "$@"; }
run() { if [ "$SIMULAR" = true ]; then echo "[simulado] $*"; else "$@" >/dev/null; fi; }

read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
# A sprint/release cannot be reported as finished while its canonical documentation is unpublished.
documentacao() { "${BB_CMD[@]}" esteira documentacao --publicada --comunidade --visibilidade-remota; }

apagar_se_seguro() { # <branch> <tag>
  local branch="$1" tag="$2" fora
  [[ " $branches_existentes " == *" $branch "* ]] || return 0
  if [[ "$prs_abertos" == *" $branch "* ]]; then
    echo "::warning::$branch mantida: PR aberto"; sobras=$((sobras + 1)); return 0
  fi
  fora=$(gh api "repos/$R/compare/$tag...$branch" --jq '.ahead_by')
  [ "$fora" = 0 ] || { echo "::warning::$branch mantida: $fora commit(s) fora da tag $tag"; sobras=$((sobras + 1)); return 0; }
  fora=$(gh api "repos/$R/compare/main...$branch" --jq '.ahead_by')
  [ "$fora" = 0 ] || { echo "::warning::$branch mantida: $fora commit(s) fora da main"; sobras=$((sobras + 1)); return 0; }
  run gh api -X DELETE "repos/$R/git/refs/heads/$branch"
  echo "branch apagada: $branch"
}

if [ -n "${VERSAO:-}" ]; then
  v="${VERSAO#v}"; tag="v$v"
  [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::versão '$v' inválida"; exit 2; }
  gh api "repos/$R/git/ref/tags/$tag" >/dev/null 2>&1 || { echo "::error::a tag $tag não existe: a versão não foi publicada"; exit 1; }
  gh release view "$tag" --repo "$R" >/dev/null 2>&1 || { echo "::error::a Release $tag não existe"; exit 1; }
  documentacao
  release=$(gh api "repos/$R/releases/tags/$tag")
  jq -e --arg tag "$tag" '.tag_name == $tag and .draft == false and .prerelease == false' <<< "$release" >/dev/null \
    || { echo "::error::a Release $tag não é estável"; exit 1; }
  prs_abertos=" $(gh pr list --repo "$R" --state open --limit 200 --json headRefName --jq '[.[].headRefName] | join(" ")') "
  branches_existentes=$(gh api "repos/$R/git/matching-refs/heads/" --jq '[.[].ref | ltrimstr("refs/heads/")] | join(" ")')
  m=$(gh api "repos/$R/milestones?state=all&per_page=100" --jq ".[] | select(.title == \"$tag\") | .number" | head -n 1)
  [ -n "$m" ] || { echo "::error::milestone $tag não encontrado"; exit 1; }
  issues=$(gh api --paginate "repos/$R/issues?milestone=$m&state=all&per_page=100" \
    --jq '.[] | select(has("pull_request") | not) | "\(.number)\t\(.state)\t\([.labels[].name] | join(","))"')
  echo "Encerrando $tag$([ "$SIMULAR" = true ] && echo " [SIMULAÇÃO]")"
  while IFS=$'\t' read -r n estado labels; do
    [ -n "$n" ] || continue
    [ "$estado" = closed ] || run gh issue close "$n" --repo "$R" --reason completed --comment "Publicado em produção na versão $tag."
    if [[ ",$labels," == *",epic,"* ]]; then projeto mover "$PLAN" "$n" "Concluída" >/dev/null || true
    elif [[ ",$labels," == *",bug,"* ]]; then projeto mover "$BUGS" "$n" "Corrigido" >/dev/null || true
    else projeto mover "$EXEC" "$n" "Concluído" >/dev/null || true; fi
    for branch in $branches_existentes; do
      [[ "$branch" =~ ^(epico|teste|feature|docs|bugfix|hotfix)/$n- ]] && apagar_se_seguro "$branch" "$tag"
    done
  done <<< "$issues"
  run gh api -X PATCH "repos/$R/milestones/$m" -f state=closed
  apagar_se_seguro "release/$v" "$tag"
fi

if [ "${SPRINT:-false}" = true ]; then
  [ -n "${VERSAO:-}" ] || documentacao
  atual=$(projeto sprints "$EXEC" | grep -E '^Sprint [0-9]+ · [0-9-]+$' | tail -n 1 || true)
  if [ -z "$atual" ]; then echo "Nenhuma sprint aberta."; else
    for painel in "$PLAN" "$EXEC"; do projeto sprint-renomear "$painel" "$atual" "$atual → $HOJE"; done
    echo "Sprint encerrada: $atual → $HOJE"
  fi
fi

# Closing is incomplete until reported leftovers are resolved; publication itself is not rolled back.
[ "$sobras" -eq 0 ] || { echo "::error::Encerrar incompleto: $sobras branch(es) preservada(s) precisam de revisão"; exit 1; }
SIMULAR="$SIMULAR" FAXINA_EXIGIR_LIMPA=true bash "$AQUI/faxina.sh"
