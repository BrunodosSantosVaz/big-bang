#!/usr/bin/env bash
# "Mesclar PR" (spec 14.2): merges a PR when it is approved and green, always with a merge commit.
#   into epico/*  : teste/* needs testes-aprovados when the epic is testes-revisao-humana, otherwise pr-aprovado;
#                   feature/*, docs/* and sync/* need pr-aprovado.
#   into develop  : only fundacao/*, framework/* and Dependabot updates of GitHub Actions, with pr-aprovado.
#   into main     : never (main only receives releases, merged by "Publicar em produção").
# Green = the required checks (CHECKS_OBRIGATORIOS, default "check regras") completed with success on the PR head.
# After a merge into epico/<n>-*: creates the branches the merge unblocked (criar-branches.sh) and, when the epic's
# test, tasks and documentation are all merged, starts "Integrar release" for the epic.
#
# Environment: PR_NUMBER, SIMULAR (true: only explain), CHECKS_OBRIGATORIOS, GITHUB_REPOSITORY,
# GH_TOKEN (PROJETO_TOKEN: its merge events trigger the next workflows).
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

if [ -z "${BB_CACHE_DIR:-}" ]; then  # board ids and options fetched once per run (projeto.sh)
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi

AQUI="$(cd "$(dirname "$0")" && pwd)"
R="${GITHUB_REPOSITORY:?}"; PR="${PR_NUMBER:?}"; SIMULAR="${SIMULAR:-false}"
read -r -a CHECKS <<<"${CHECKS_OBRIGATORIOS:-check regras seguranca}"
tem() { [[ ",$1," == *",$2,"* ]]; }
espera() { echo "PR #$PR não será mesclado agora: $1"; exit 0; }

IFS=$'\t' read -r estado rascunho base head sha labels <<<"$(gh pr view "$PR" --repo "$R" \
  --json state,isDraft,baseRefName,headRefName,headRefOid,labels \
  --jq '[.state, (.isDraft | tostring), .baseRefName, .headRefName, .headRefOid, ([.labels[].name] | join(","))] | @tsv')"
[ "$estado" = OPEN ] || espera "não está aberto ($estado)"
[ "$rascunho" = false ] || espera "é rascunho"

# ---- which approval this PR needs
case "$base" in
  main|release/*) espera "a $base só recebe releases (Publicar em produção)" ;;
  epico/*)
    aprovacao=pr-aprovado
    if [[ "$head" =~ ^teste/([0-9]+)- ]]; then
      tem "$(gh api "repos/$R/issues/${BASH_REMATCH[1]}" --jq '[.labels[].name] | join(",")')" testes-revisao-humana \
        && aprovacao=testes-aprovados
    elif ! [[ "$head" =~ ^(feature|docs)/[0-9]+- || "$head" =~ ^sync/ ]]; then
      espera "a branch $head não entra num épico"
    fi ;;
  develop)
    aprovacao=pr-aprovado
    [[ "$head" =~ ^(fundacao/|framework/v|dependabot/github_actions/) ]] \
      || espera "na develop só entram fundacao/*, framework/* e Dependabot de actions (o resto vem pelo épico)" ;;
  *) espera "destino $base fora do modelo de branches" ;;
esac
tem "$labels" "$aprovacao" || espera "falta a label $aprovacao"

# ---- required checks green on the exact head commit
# Only the latest run of each check counts (highest id): a check re-run after a decision label, or one cancelled by
# the concurrency group, leaves older runs of the same name on the commit.
runs=$(gh api "repos/$R/commits/$sha/check-runs?per_page=100" \
  --jq '[.check_runs[]] | group_by(.name) | map(max_by(.id // 0))[] | "\(.name)\t\(.status)\t\(.conclusion)"')
for check in "${CHECKS[@]}"; do
  linhas=$(awk -F'\t' -v c="$check" '$1 == c' <<<"$runs")
  [ -n "$linhas" ] || espera "o check $check ainda não rodou no ${sha:0:7}"
  if awk -F'\t' '$2 != "completed" { found = 1 } END { exit !found }' <<<"$linhas"; then espera "o check $check está rodando"; fi
  if awk -F'\t' '$3 != "success" { found = 1 } END { exit !found }' <<<"$linhas"; then espera "o check $check falhou"; fi
done

if [ "$SIMULAR" = true ]; then
  echo "[simulado] mesclar o PR #$PR ($head -> $base, merge commit, ${sha:0:7})"; exit 0
fi
gh pr merge "$PR" --repo "$R" --merge --match-head-commit "$sha" >/dev/null
echo "PR #$PR mesclado: $head -> $base."

# ---- after a merge into an epic branch
[[ "$base" =~ ^epico/([0-9]+)- ]] || exit 0
epico="${BASH_REMATCH[1]}"
if [ -f "$AQUI/criar-branches.sh" ]; then EPICO="$epico" SIMULAR=false bash "$AQUI/criar-branches.sh"; fi

mesclados=$(gh pr list --repo "$R" --base "$base" --state merged --limit 200 --json headRefName --jq '.[].headRefName')
faltam=0
while IFS=$'\t' read -r n rotulos; do
  [ -n "$n" ] || continue
  tem "$rotulos" teste-aceite || tem "$rotulos" task || tem "$rotulos" documentacao || continue
  grep -qE "^(teste|feature|docs)/$n-" <<<"$mesclados" || faltam=$((faltam + 1))
done < <(gh api graphql -H "GraphQL-Features: sub_issues" -f o="${R%%/*}" -f r="${R##*/}" -F n="$epico" -f query='
  query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issue(number:$n){
    subIssues(first:100){ nodes{ number labels(first:20){ nodes{ name } } } } } } }' \
  --jq '.data.repository.issue.subIssues.nodes[] | "\(.number)\t\([.labels.nodes[].name] | join(","))"')
if [ "$faltam" -eq 0 ]; then
  gh workflow run bb-integrar-release.yml --repo "$R" -f epico="$epico" -f simular=false
  echo "Épico #$epico completo (teste, tarefas e documentação mesclados): Integrar release disparado."
else
  echo "Épico #$epico: faltam $faltam issue(s) do épico para integrar."
fi
