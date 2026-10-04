#!/usr/bin/env bash
# "Iniciar sprint" (spec 11.6, step 1). For every epic in "Próxima sprint" that meets the Definition of Ready:
#   - Sprint option "Sprint N · AAAA-MM-DD" (single select, created once; reused on the same day);
#   - branch epico/<n>-<slug> from develop;
#   - sub-issues: the epic's acceptance-test issue (teste-aceite), one task per line of "Tarefas previstas" and the
#     documentation issue, all inheriting the epic's labels (sem-release, testes-revisao-*, revisao-*, dono:revisao-ia);
#   - blocked-by: tasks wait for the test issue and for the tasks they depend on; documentation waits for all tasks;
#   - branch teste/<t>-<slug> from the epic branch; cards in "A fazer" with Sprint and Épico; epic -> Em desenvolvimento.
# Refuses (reason in the log) epics without refinamento-aprovado, com-prototipo without prototipo-aprovado, or without
# tasks. Running again duplicates nothing. Asks for no version (the version comes out of the PR titles).
#
# Environment: SIMULAR (true: only the plan), DATA (AAAA-MM-DD, default today), PROJETO_PLANEJAMENTO/EXECUCAO,
# GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN), BB, BRANCH_DEVELOP (develop).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
PLAN="${PROJETO_PLANEJAMENTO:?}"; EXEC="${PROJETO_EXECUCAO:?}"
R="${GITHUB_REPOSITORY:?}"; OWNER="${R%%/*}"; REPO="${R##*/}"
DEVELOP="${BRANCH_DEVELOP:-develop}"; SIMULAR="${SIMULAR:-false}"; DATA="${DATA:-$(date -u +%F)}"
read -r -a BB <<<"${BB:-python3 .bigbang/bin/bb.py}"
[ "$SIMULAR" = true ] && export DRY_RUN=1
projeto() { bash "$AQUI/projeto.sh" "$@"; }
gql() { gh api graphql -H "GraphQL-Features: sub_issues" "$@"; }
run() { if [ "$SIMULAR" = true ]; then echo "  [simulado] $*"; else "$@"; fi; }
HERDADAS=(sem-release testes-revisao-ia testes-revisao-humana revisao-ia revisao-humana dono:revisao-ia)

criar_branch() { # <nova> <a partir de>
  if gh api "repos/$R/git/ref/heads/$1" >/dev/null 2>&1; then echo "  branch $1 já existe"; return 0; fi
  local sha
  if [ "$SIMULAR" = true ]; then echo "  [simulado] criar branch $1 a partir de $2"; return 0; fi
  sha=$(gh api "repos/$R/git/ref/heads/$2" --jq '.object.sha')
  gh api --silent -X POST "repos/$R/git/refs" -f ref="refs/heads/$1" -f sha="$sha"
  echo "  branch $1 criada a partir de $2"
}

bloquear() { # <issue> <bloqueada por>
  local id
  [ "$SIMULAR" = true ] && { echo "  [simulado] #$1 bloqueada por #$2"; return 0; }
  id=$(gh api "repos/$R/issues/$2" --jq '.id')
  gh api --silent -X POST "repos/$R/issues/$1/dependencies/blocked_by" -F issue_id="$id" 2>/dev/null \
    || echo "  ::warning::não consegui registrar #$1 bloqueada por #$2"
}

# ---- epics of "Próxima sprint" and the Definition of Ready
mapfile -t candidatos < <(projeto cartoes "$PLAN" "Próxima sprint")
if [ "${#candidatos[@]}" -eq 0 ]; then
  echo "::error::Nenhum épico em 'Próxima sprint'. Refine e aprove os épicos antes de iniciar a sprint."; exit 1
fi
prontos=()
for n in "${candidatos[@]}"; do
  labels=$(gh api "repos/$R/issues/$n" --jq '[.labels[].name] | join(",")')
  if problemas=$(gh api "repos/$R/issues/$n" --jq '.body // ""' | "${BB[@]}" esteira pronto --labels "$labels"); then
    prontos+=("$n")
  else
    echo "::warning::Épico #$n recusado (Definition of Ready): $(tr '\n' ';' <<<"$problemas")"
  fi
done
if [ "${#prontos[@]}" -eq 0 ]; then echo "::error::Nenhum épico cumpre a Definition of Ready. Nada foi iniciado."; exit 1; fi

# ---- Sprint option (one per run; reused if one with today's date exists)
sprint=$(projeto sprints "$EXEC" | grep -E "^Sprint [0-9]+ · $DATA\$" | head -n 1 || true)
if [ -z "$sprint" ]; then
  ultimo=$(projeto sprints "$EXEC" | sed -nE 's/^Sprint ([0-9]+) · .*/\1/p' | sort -n | tail -n 1)
  sprint="Sprint $(( ${ultimo:-0} + 1 )) · $DATA"
fi
for painel in "$PLAN" "$EXEC"; do projeto sprint-criar "$painel" "$sprint"; done
echo "Sprint: $sprint"

nova_issue() { # <titulo> <corpo> <label> <herdadas...>; prints the number (existing sub-issue reused)
  local titulo="$1" corpo="$2" label="$3"; shift 3
  local existente
  existente=$(awk -F'\t' -v t="$titulo" '$2 == t { print $1; exit }' <<<"$subs")
  if [ -n "$existente" ]; then echo "$existente"; return 0; fi
  if [ "$SIMULAR" = true ]; then echo "  [simulado] criar '$titulo' ($label${*:+, $*})" >&2; echo "?"; return 0; fi
  local args=(--repo "$R" --title "$titulo" --body "$corpo" --label "$label") url num
  for l in "$@"; do args+=(--label "$l"); done
  url=$(gh issue create "${args[@]}"); num="${url##*/}"
  gql -f e="$epico_node" -f t="$(gh api "repos/$R/issues/$num" --jq .node_id)" -f query='
    mutation($e:ID!,$t:ID!){ addSubIssue(input:{issueId:$e, subIssueId:$t}){ issue{ number } } }' >/dev/null
  echo "  criada #$num: $titulo" >&2
  echo "$num"
}

cartao() { # <issue> : A fazer, Sprint and Épico on the Execução board
  [ "$1" != "?" ] || return 0
  projeto mover "$EXEC" "$1" "A fazer" "-" >/dev/null
  projeto sprint "$EXEC" "$1" "$sprint" >/dev/null
  projeto texto "$EXEC" "$1" "Épico" "#$n" >/dev/null
}

for n in "${prontos[@]}"; do
  IFS=$'\t' read -r titulo epico_node labels <<<"$(gh api "repos/$R/issues/$n" \
    --jq '[.title, .node_id, ([.labels[].name] | join(","))] | @tsv')"
  corpo=$(gh api "repos/$R/issues/$n" --jq '.body // ""')
  echo "== Épico #$n: $titulo"
  herdadas=()
  for l in "${HERDADAS[@]}"; do [[ ",$labels," == *",$l,"* ]] && herdadas+=("$l"); done
  subs=$(gql -f o="$OWNER" -f r="$REPO" -F n="$n" -f query='
    query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issue(number:$n){
      subIssues(first:100){ nodes{ number title } } } } }' --jq '.data.repository.issue.subIssues.nodes[] | "\(.number)\t\(.title)"')

  base_epico=$("${BB[@]}" esteira branch epico "$n" "$titulo")
  criar_branch "$base_epico" "$DEVELOP"

  criterios=$(printf '%s' "$corpo" | awk '/^### /{d=($0 ~ /^### Critérios de aceite/); next} d')
  regras=$(printf '%s' "$corpo" | awk '/^### /{d=($0 ~ /^### Regras de negócio envolvidas/); next} d')
  mapfile -t tarefas < <(printf '%s' "$corpo" | "${BB[@]}" esteira tarefas)
  lista_tarefas=$(for t in "${tarefas[@]}"; do printf -- '- %s\n' "$(cut -f2 <<<"$t")"; done)

  teste=$(nova_issue "Testes de aceite · $titulo" "### Épico

#$n — $titulo

### Critérios cobertos

$criterios

### Regras de negócio

$regras

### Tarefas que vão implementar cada critério

$lista_tarefas" teste-aceite "${herdadas[@]}")
  cartao "$teste"

  declare -A numero_da_tarefa=()
  for t in "${tarefas[@]}"; do
    IFS=$'\t' read -r indice nome deps <<<"$t"
    num=$(nova_issue "$nome" "### Épico

#$n — $titulo

### O que fazer

$nome

### Critérios cobertos

(ver os critérios do épico e o teste #$teste)

### Depende de

${deps:-nenhuma}" task "${herdadas[@]}")
    numero_da_tarefa[$indice]="$num"
    cartao "$num"
    [ "$num" = "?" ] || [ "$teste" = "?" ] || bloquear "$num" "$teste"
    for d in ${deps//,/ }; do
      [ "$num" = "?" ] || [ "${numero_da_tarefa[$d]:-?}" = "?" ] || bloquear "$num" "${numero_da_tarefa[$d]}"
    done
  done

  doc=$(nova_issue "Documentação · $titulo" "### Épico

#$n — $titulo

### Checklist

- [ ] Regras de negócio novas ou alteradas em docs/negocio/regras/
- [ ] Glossário com os termos novos
- [ ] Diagramas C4 e arc42, se a arquitetura mudou
- [ ] Contrato da API, se mudou
- [ ] Inventário LGPD, se há dado pessoal novo
- [ ] Runbook, se a operação mudou
- [ ] Guia de quem usa, se a tela ou o fluxo mudou
- [ ] ADR de cada decisão tomada no épico
- [ ] Rascunho da entrada do CHANGELOG.md (a versão é preenchida na integração)" documentacao "${herdadas[@]}")
  cartao "$doc"
  for num in "${numero_da_tarefa[@]}"; do
    [ "$num" = "?" ] || [ "$doc" = "?" ] || bloquear "$doc" "$num"
  done
  unset numero_da_tarefa

  if [ "$teste" != "?" ]; then criar_branch "$("${BB[@]}" esteira branch teste "$teste" "Testes de aceite · $titulo")" "$base_epico"; fi
  projeto sprint "$PLAN" "$n" "$sprint" >/dev/null || true
  projeto mover "$PLAN" "$n" "Em desenvolvimento" "Próxima sprint"
done
echo "$sprint iniciada com ${#prontos[@]} épico(s). Próximo passo: os testes de aceite de cada épico (bb-escrever-testes-aceite)."
