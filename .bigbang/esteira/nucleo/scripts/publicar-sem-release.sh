#!/usr/bin/env bash
# "Publicar sem release" (spec 14.2): moves main forward to develop when nothing of the artifact changed, and
# closes what was finished without a version (sem-release epics and their issues, Foundation steps).
# GATE (refuses without changing anything):
#   - artifact paths (entrega.caminhos_artefato) differ between main and develop (that needs a release);
#   - main is not contained in develop (diverged: return main to develop first);
#   - the check `check` at the tip of develop is not green.
# THEN: fast-forward main to develop; close the open sem-release epics whose sub-issues are all merged into their
# epic branch (and those sub-issues), cards -> Concluído / Concluída; delete their merged epico/teste/feature/docs
# branches (only when contained in main). Idempotent.
# Environment: SIMULAR, PROJETO_PLANEJAMENTO/EXECUCAO, GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN), BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

if [ -z "${BB_CACHE_DIR:-}" ]; then  # board ids and options fetched once per run (projeto.sh)
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi

AQUI="$(cd "$(dirname "$0")" && pwd)"
PLAN="${PROJETO_PLANEJAMENTO:?}"; EXEC="${PROJETO_EXECUCAO:?}"
R="${GITHUB_REPOSITORY:?}"; OWNER="${R%%/*}"; REPO="${R##*/}"; SIMULAR="${SIMULAR:-false}"
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
projeto() { bash "$AQUI/projeto.sh" "$@"; }
falhas=0
falha() { echo "::error::$*"; falhas=$((falhas + 1)); }

git fetch -q origin "+refs/heads/*:refs/remotes/origin/*"
mapfile -t caminhos < <("${BB_CMD[@]}" config get entrega.caminhos_artefato)
mudou=$(git diff --name-only origin/main origin/develop -- "${caminhos[@]}")
[ -z "$mudou" ] || falha "a develop tem mudança no artefato que não está na main ($(tr '\n' ' ' <<<"$mudou")): isso exige release"
git merge-base --is-ancestor origin/main origin/develop || falha "a main tem commits que a develop não tem: devolva a main para a develop antes"
sha=$(git rev-parse origin/develop)
ci=$(gh api "repos/$R/commits/$sha/check-runs?per_page=100" --jq '[.check_runs[] | select(.name == "check")]
  | if length > 0 and (map(.status) | all(. == "completed")) and (map(.conclusion) | all(. == "success")) then "ok" else "pendente" end')
[ "$ci" = ok ] || falha "o check 'check' na ponta da develop (${sha:0:7}) está pendente ou falhando"
if [ "$falhas" -gt 0 ]; then echo "Publicação RECUSADA ($falhas problema(s)). Nada foi alterado."; exit 1; fi

# ---- sem-release epics finished (every sub-issue merged into the epic branch, already in develop)
finalizar=()
for ref in $(git for-each-ref --format='%(refname:strip=3)' 'refs/remotes/origin/epico/*'); do
  [[ "$ref" =~ ^epico/([0-9]+)- ]] || continue
  n="${BASH_REMATCH[1]}"
  [ "$(gh api "repos/$R/issues/$n" --jq '[.labels[].name] | index("sem-release") != null')" = true ] || continue
  git merge-base --is-ancestor "origin/$ref" origin/develop || { echo "#$n: $ref ainda não está na develop"; continue; }
  finalizar+=("$n:$ref")
done

atras=false; git merge-base --is-ancestor origin/develop origin/main || atras=true
echo "Portão aprovado. main $([ "$atras" = true ] && echo "avança até ${sha:0:7}" || echo "já está na develop"); épicos a concluir: ${#finalizar[@]}."
if [ "$SIMULAR" = true ]; then
  for item in "${finalizar[@]}"; do echo "[simulado] concluir o épico #${item%%:*} e apagar ${item#*:} e as branches das tarefas"; done
  echo "Simulação: nada foi alterado."; exit 0
fi
[ "$atras" = false ] || { git push -q origin "origin/develop:refs/heads/main"; echo "main avançada até ${sha:0:7}."; }
git fetch -q origin main

for item in "${finalizar[@]}"; do
  n="${item%%:*}"; ref="${item#*:}"
  while IFS=$'\t' read -r sub estado; do
    [ -n "$sub" ] || continue
    [ "$estado" = CLOSED ] || gh issue close "$sub" --repo "$R" --reason completed \
      --comment "Concluída sem release: está na \`main\` e não muda o artefato." >/dev/null
    projeto mover "$EXEC" "$sub" "Concluído" >/dev/null || true
  done < <(gh api graphql -H "GraphQL-Features: sub_issues" -f o="$OWNER" -f r="$REPO" -F n="$n" -f query='
    query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issue(number:$n){
      subIssues(first:100){ nodes{ number state } } } } }' --jq '.data.repository.issue.subIssues.nodes[] | "\(.number)\t\(.state)"')
  gh issue close "$n" --repo "$R" --reason completed --comment "Épico concluído sem release." >/dev/null
  projeto mover "$PLAN" "$n" "Concluída" >/dev/null || true
  for branch in $(gh pr list --repo "$R" --base "$ref" --state merged --limit 200 --json headRefName --jq '.[].headRefName') "$ref"; do
    if git merge-base --is-ancestor "origin/$branch" origin/main 2>/dev/null; then
      gh api -X DELETE "repos/$R/git/refs/heads/$branch" >/dev/null 2>&1 && echo "branch apagada: $branch"
    fi
  done
  echo "Épico #$n concluído."
done
echo "Publicar sem release concluído."
if [ "$SIMULAR" != true ]; then  # Foundation and framework branches merged by this publication, and anything else left
  bash "$AQUI/faxina.sh" || echo "::warning::faxina não concluída: rode o Encerrar"
fi
