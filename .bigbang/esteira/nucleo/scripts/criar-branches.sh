#!/usr/bin/env bash
# "Criar branches" (spec 11.6, step 4): for each epic in development (or only EPICO), creates from its epico/* branch
#   - feature/<n>-<slug> for every open task that is unblocked: never before the epic's test PR is merged, and only
#     when each task it depends on (blocked-by) is closed or already merged into the epic;
#   - docs/<n>-<slug> for the documentation issue when every task is merged into the epic.
# Moves the card to "Feature" and comments the branch on the issue. Idempotent. Also runs after every merge into
# an epic branch (mesclar-pr.sh).
#
# Environment: EPICO (optional), SIMULAR, PROJETO_PLANEJAMENTO/EXECUCAO, GITHUB_REPOSITORY, GH_TOKEN, BB.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
PLAN="${PROJETO_PLANEJAMENTO:?}"; EXEC="${PROJETO_EXECUCAO:?}"
R="${GITHUB_REPOSITORY:?}"; OWNER="${R%%/*}"; REPO="${R##*/}"; SIMULAR="${SIMULAR:-false}"
read -r -a BB <<<"${BB:-python3 .bigbang/bin/bb.py}"
[ "$SIMULAR" = true ] && export DRY_RUN=1
projeto() { bash "$AQUI/projeto.sh" "$@"; }
tem() { [[ ",$1," == *",$2,"* ]]; }
criadas=0

if [ -n "${EPICO:-}" ]; then epicos=("$EPICO"); else mapfile -t epicos < <(projeto cartoes "$PLAN" "Em desenvolvimento"); fi

criar() { # <issue> <tipo> <titulo> <branch do épico>
  local branch sha
  branch=$("${BB[@]}" esteira branch "$2" "$1" "$3")
  if gh api "repos/$R/git/ref/heads/$branch" >/dev/null 2>&1; then return 0; fi
  if [ "$SIMULAR" = true ]; then echo "  [simulado] criar $branch a partir de $4"; return 0; fi
  sha=$(gh api "repos/$R/git/ref/heads/$4" --jq '.object.sha')
  gh api --silent -X POST "repos/$R/git/refs" -f ref="refs/heads/$branch" -f sha="$sha"
  gh issue comment "$1" --repo "$R" --body "Branch criada a partir de \`$4\`: \`$branch\`. Assuma com \`bb assumir $1 <seu-nome>\`, trabalhe numa pasta própria e abra o PR para \`$4\` com \`Refs #$1\`." >/dev/null
  projeto mover "$EXEC" "$1" Feature "A fazer|-" >/dev/null
  echo "  #$1: $branch criada"
  criadas=$((criadas + 1))
}

for epico in "${epicos[@]}"; do
  [ -n "$epico" ] || continue
  base=$(gh api "repos/$R/git/matching-refs/heads/epico/$epico-" --jq '.[0].ref // empty' | sed 's|^refs/heads/||')
  if [ -z "$base" ]; then echo "Épico #$epico sem branch epico/$epico-*: rode Iniciar sprint."; continue; fi
  echo "== Épico #$epico ($base)"
  mesclados=$(gh pr list --repo "$R" --base "$base" --state merged --limit 200 --json headRefName --jq '.[].headRefName')
  subs=$(gh api graphql -H "GraphQL-Features: sub_issues" -f o="$OWNER" -f r="$REPO" -F n="$epico" -f query='
    query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issue(number:$n){
      subIssues(first:100){ nodes{ number title state labels(first:20){ nodes{ name } } } } } } }' \
    --jq '.data.repository.issue.subIssues.nodes[] | "\(.number)\t\(.state)\t\([.labels.nodes[].name] | join(","))\t\(.title)"')
  feito() { grep -qE "^(teste|feature|docs)/$1-" <<<"$mesclados"; }

  teste_mesclado=false
  while IFS=$'\t' read -r n estado labels titulo; do
    tem "$labels" teste-aceite || continue
    if feito "$n" || [ "$estado" = CLOSED ]; then teste_mesclado=true
    else criar "$n" teste "$titulo" "$base"; fi
  done <<<"$subs"
  if [ "$teste_mesclado" != true ]; then echo "  o teste do épico ainda não foi mesclado: nenhuma tarefa começa antes."; continue; fi

  tarefas_abertas=0; doc=""; doc_titulo=""
  while IFS=$'\t' read -r n estado labels titulo; do
    [ -n "$n" ] || continue
    if tem "$labels" documentacao; then doc="$n"; doc_titulo="$titulo"; continue; fi
    tem "$labels" task || continue
    if feito "$n" || [ "$estado" = CLOSED ]; then continue; fi
    tarefas_abertas=$((tarefas_abertas + 1))
    livre=true
    while IFS=$'\t' read -r bloqueio estado_bloqueio; do
      [ -n "$bloqueio" ] || continue
      if [ "$estado_bloqueio" != closed ] && ! feito "$bloqueio"; then livre=false; fi
    done < <(gh api "repos/$R/issues/$n/dependencies/blocked_by" --jq '.[] | "\(.number)\t\(.state)"')
    if [ "$livre" = true ]; then criar "$n" feature "$titulo" "$base"; else echo "  #$n espera as tarefas das quais depende"; fi
  done <<<"$subs"

  if [ -n "$doc" ] && [ "$tarefas_abertas" -eq 0 ] && ! feito "$doc"; then criar "$doc" docs "$doc_titulo" "$base"; fi
done
echo "Branches criadas: $criadas."
