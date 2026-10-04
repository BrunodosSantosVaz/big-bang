#!/usr/bin/env bash
# "Publicar em produção" (spec 11.6 step 10). GATE (always, also when simulating) — refuses when:
#   - the release unit (epics and bugs of milestone vX.Y.Z) is not `homologado` (or is `reprovado`);
#   - an epic's documentation issue was not merged into the release;
#   - an issue `bloqueia-producao` is open;
#   - `bb checklist producao` fails on the release branch;
#   - the PR release/x.y.z -> main is missing, conflicting, or not green on its exact head commit;
#   - there is no candidate vX.Y.Z-rc.N, or the release branch changed after it;
#   - CHANGELOG.md has no section for the version.
# THEN (simular=false, after the owner approved the `producao` environment): merges the PR with a merge commit,
# publishes the SAME artifact through the profile's promover.sh (tag + Release vX.Y.Z, Latest), closes and cleans up
# (encerrar.sh) and returns main to develop and to the open epics (devolver-main.sh).
# Idempotent: when the Release vX.Y.Z already exists, only the cleanup runs again.
# Environment: VERSAO, SIMULAR, CHECKS_OBRIGATORIOS, PROJETO_*, GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN), BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
if [ -z "${BB_CACHE_DIR:-}" ]; then
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi
AQUI="$(cd "$(dirname "$0")" && pwd)"
R="${GITHUB_REPOSITORY:?}"; SIMULAR="${SIMULAR:-false}"
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
read -r -a CHECKS <<<"${CHECKS_OBRIGATORIOS:-check regras seguranca}"
v="${VERSAO:?informe a versão (x.y.z)}"; v="${v#v}"; tag="v$v"; branch="release/$v"
[[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::versão '$v' inválida"; exit 2; }
perfil=$("${BB_CMD[@]}" config get entrega.perfil)
falhas=0
falha() { echo "::error::$*"; falhas=$((falhas + 1)); }

finalizar() {
  VERSAO="$v" SIMULAR="$SIMULAR" bash "$AQUI/encerrar.sh"
  TAG="$tag" SIMULAR="$SIMULAR" bash "$AQUI/devolver-main.sh"
}

echo "Publicar $tag em produção$([ "$SIMULAR" = true ] && echo " [SIMULAÇÃO]")"
git fetch -q origin "+refs/heads/*:refs/remotes/origin/*" --tags
if gh release view "$tag" --repo "$R" >/dev/null 2>&1; then
  echo "A Release $tag já existe: só a limpeza e a devolução da main (retomada)."
  finalizar; exit 0
fi

# ---- release unit homologated, documentation merged, nothing blocking
m=$(gh api "repos/$R/milestones?state=all&per_page=100" --jq ".[] | select(.title == \"$tag\") | .number" | head -n 1)
unidades=0
if [ -z "$m" ]; then falha "milestone $tag não encontrado (o Integrar release o cria)"; else
  while IFS=$'\t' read -r n labels; do
    [ -n "$n" ] || continue
    if [[ ",$labels," == *",epic,"* || ",$labels," == *",bug,"* ]]; then
      unidades=$((unidades + 1))
      [[ ",$labels," == *",reprovado,"* ]] && falha "#$n está reprovado: a correção precisa de uma candidata nova"
      [[ ",$labels," == *",homologado,"* ]] || falha "#$n não foi homologado (label homologado, decisão do dono)"
    fi
    if [[ ",$labels," == *",documentacao,"* ]] && ! git log --format=%s "origin/$branch" | grep -E "/docs/$n-" >/dev/null; then
      falha "a documentação #$n não foi mesclada na release"
    fi
  done < <(gh api "repos/$R/issues?milestone=$m&state=all&per_page=100" \
    --jq '.[] | select(has("pull_request") | not) | "\(.number)\t\([.labels[].name] | join(","))"')
  [ "$unidades" -gt 0 ] || falha "o milestone $tag não tem épico nem bug"
fi
bloqueios=$(gh api "repos/$R/issues?labels=bloqueia-producao&state=open&per_page=100" \
  --jq '[.[] | select(has("pull_request") | not) | "#\(.number)"] | join(" ")')
[ -z "$bloqueios" ] || falha "issues que bloqueiam produção abertas: $bloqueios"
if git rev-parse -q --verify "origin/$branch" >/dev/null; then
  release_dir=$(mktemp -d); git worktree add -q --detach "$release_dir" "origin/$branch"
  "${BB_CMD[@]}" checklist producao --dados "$release_dir" || falha "bb checklist producao reprovado (na $branch)"
  git worktree remove --force "$release_dir" >/dev/null 2>&1 || true
fi

# ---- the release PR, its checks and the candidate
IFS=$'\t' read -r pr mergeable head_sha <<<"$(gh pr list --repo "$R" --head "$branch" --base main --state open \
  --json number,mergeable,headRefOid --jq '.[0] | "\(.number // "")\t\(.mergeable // "")\t\(.headRefOid // "")"')"
if [ -z "$pr" ]; then falha "não há PR aberto de $branch para a main (a candidata o abre)"; else
  [ "$mergeable" != CONFLICTING ] || falha "o PR #$pr tem conflito com a main"
  runs=$(gh api "repos/$R/commits/$head_sha/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.status)\t\(.conclusion)"')
  for check in "${CHECKS[@]}"; do
    linhas=$(awk -F'\t' -v c="$check" '$1 == c' <<<"$runs")
    if [ -z "$linhas" ] || awk -F'\t' '$2 != "completed" || $3 != "success" { f = 1 } END { exit !f }' <<<"$linhas"; then
      falha "o check $check não está verde no ${head_sha:0:7} (PR #$pr)"
    fi
  done
fi
rc=$(git tag -l "$tag-rc.*" | sort -t. -k4,4n | tail -n 1)
if [ -z "$rc" ]; then falha "não há candidata $tag-rc.N"
elif [ "$(git rev-parse "$rc^{commit}")" != "$(git rev-parse "origin/$branch")" ]; then
  falha "a $branch mudou depois da candidata $rc: gere uma candidata nova antes de publicar"
fi
git show "origin/$branch:CHANGELOG.md" 2>/dev/null | grep -F "## [$v]" >/dev/null || falha "CHANGELOG.md da $branch sem a seção [$v]"

if [ "$falhas" -gt 0 ]; then echo "Publicação RECUSADA ($falhas problema(s)). Nada foi alterado."; exit 1; fi
echo "Portão aprovado: $tag a partir de $rc (PR #$pr, ${head_sha:0:7})."
if [ "$SIMULAR" = true ]; then
  echo "[simulado] mesclar o PR #$pr; publicar o artefato de $rc como $tag (perfil $perfil); limpar; devolver a main"
  exit 0
fi

gh pr merge "$pr" --repo "$R" --merge --match-head-commit "$head_sha" \
  --subject "chore(release): merge $tag" >/dev/null
git fetch -q origin main
alvo=$(git rev-parse origin/main)
echo "PR #$pr mesclado na main (${alvo:0:7})."
RC_TAG="$rc" TAG="$tag" TARGET_SHA="$alvo" bash "$AQUI/../../perfis/$perfil/scripts/promover.sh"
finalizar
echo "$tag publicada em produção."
