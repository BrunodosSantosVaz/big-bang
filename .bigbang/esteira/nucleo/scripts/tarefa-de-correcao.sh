#!/usr/bin/env bash
# Epic rejected in homologation (spec 11.6 step 9; decision 16): ONE new correction task in the same epic, with the
# owner's reason. It inherits the epic's labels, enters the milestone, the Sprint and the "A fazer" column, gets its
# feature/<n>-<slug> branch from the epic branch, and follows the normal flow. When its PR is merged, the epic is
# complete again and "Integrar release" merges it into the same release/x.y.z: the next candidate is rc.N+1.
# Environment: EPICO, MOTIVO, SIMULAR, PROJETO_PLANEJAMENTO/EXECUCAO, GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN), BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
if [ -z "${BB_CACHE_DIR:-}" ]; then
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi
AQUI="$(cd "$(dirname "$0")" && pwd)"
PLAN="${PROJETO_PLANEJAMENTO:?}"; EXEC="${PROJETO_EXECUCAO:?}"; R="${GITHUB_REPOSITORY:?}"
epico="${EPICO:?}"; motivo="${MOTIVO:?informe o motivo da reprovação}"; SIMULAR="${SIMULAR:-false}"
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
projeto() { bash "$AQUI/projeto.sh" "$@"; }

IFS=$'\t' read -r titulo labels milestone node <<<"$(gh api "repos/$R/issues/$epico" \
  --jq '[.title, ([.labels[].name] | join(",")), (.milestone.title // ""), .node_id] | @tsv')"
[[ ",$labels," == *",epic,"* ]] || { echo "::error::#$epico não é um épico"; exit 1; }
[[ ",$labels," == *",reprovado,"* ]] || { echo "::error::o épico #$epico não está reprovado (label reprovado)"; exit 1; }
base=$(gh api "repos/$R/git/matching-refs/heads/epico/$epico-" --jq '.[0].ref // empty' | sed 's|^refs/heads/||')
[ -n "$base" ] || { echo "::error::épico #$epico sem branch epico/$epico-*"; exit 1; }
resumo=$(printf '%s' "$motivo" | head -n 1)
if [ "${#resumo}" -gt 60 ]; then resumo="${resumo:0:60}"; resumo="${resumo% *}…"; fi  # whole words only
nova="Correção: $resumo"
args=(--repo "$R" --title "$nova" --label task --body "### Épico

#$epico — ${titulo#\[Épico\] }

### O que fazer

Corrigir o que reprovou a homologação:

$motivo

### Critérios cobertos

Os do épico; o teste de aceite que cobre o motivo é escrito ou corrigido nesta tarefa, com o dono.")
for l in sem-release testes-revisao-ia testes-revisao-humana revisao-ia revisao-humana dono:revisao-ia; do
  if [[ ",$labels," == *",$l,"* ]]; then args+=(--label "$l"); fi
done
[ -z "$milestone" ] || args+=(--milestone "$milestone")
if [ "$SIMULAR" = true ]; then echo "[simulado] criar '$nova' no épico #$epico e a branch a partir de $base"; exit 0; fi

url=$(gh issue create "${args[@]}"); n="${url##*/}"
gh api graphql -H "GraphQL-Features: sub_issues" -f e="$node" -f t="$(gh api "repos/$R/issues/$n" --jq .node_id)" \
  -f query='mutation($e:ID!,$t:ID!){ addSubIssue(input:{issueId:$e, subIssueId:$t}){ issue{ number } } }' >/dev/null
projeto mover "$EXEC" "$n" "A fazer" "-" >/dev/null
sprint=$(projeto sprint-de "$PLAN" "$epico" || true)
[ -z "$sprint" ] || projeto sprint "$EXEC" "$n" "$sprint" >/dev/null || true
projeto texto "$EXEC" "$n" "Épico" "#$epico" >/dev/null
branch=$("${BB_CMD[@]}" esteira branch feature "$n" "$nova")
sha=$(gh api "repos/$R/git/ref/heads/$base" --jq '.object.sha')
gh api --silent -X POST "repos/$R/git/refs" -f ref="refs/heads/$branch" -f sha="$sha"
projeto mover "$EXEC" "$n" Feature "A fazer|-" >/dev/null
gh issue comment "$epico" --repo "$R" --body "Reprovado na homologação. Tarefa de correção: #$n (branch \`$branch\`)." >/dev/null
echo "Tarefa de correção #$n criada no épico #$epico ($branch)."
