#!/usr/bin/env bash
# "Integrar release" (spec 11.6 step 7; 11.10; 11.12). One release unit at a time:
#   EPICO=<n>          the epic's test, tasks and documentation must be merged into epico/<n>-*.
#                      sem-release epic -> epico/* merged into develop (then "Publicar sem release").
#                      otherwise -> release/x.y.z from main (or the existing one, for rc.N+1 after a rejection),
#                      epico/* merged with --no-ff, version file, CHANGELOG, milestone vX.Y.Z, push (-> candidate).
#                      Refused while an epic it depends on (tem-dependencia) is not in production (closed).
#   BUG=<n>            bugfix/<n>-* or hotfix/<n>-* (born from main) -> release/x.y.z (patch).
#   DEPENDENCIAS=true  the open Dependabot PRs into main -> one maintenance release.
# The version comes from the merged PR titles (bb esteira versao); a VERSAO that disagrees needs
# CONFIRMAR_VERSAO=true. Conflict: nothing is pushed and the epic gets the label `conflito`.
#
# Environment: EPICO | BUG | DEPENDENCIAS, VERSAO, CONFIRMAR_VERSAO, SIMULAR, PROJETO_PLANEJAMENTO,
# GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN; the checkout must push with it), BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

if [ -z "${BB_CACHE_DIR:-}" ]; then  # board ids and options fetched once per run (projeto.sh)
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi

AQUI="$(cd "$(dirname "$0")" && pwd)"
R="${GITHUB_REPOSITORY:?}"; OWNER="${R%%/*}"; REPO="${R##*/}"
SIMULAR="${SIMULAR:-false}"
read -r -a BB <<<"${BB:-python3 .bigbang/bin/bb.py}"
[ "$SIMULAR" = true ] && export DRY_RUN=1
projeto() { bash "$AQUI/projeto.sh" "$@"; }
tem() { [[ ",$1," == *",$2,"* ]]; }
erro() { echo "::error::$*"; exit 1; }

git fetch -q origin "+refs/heads/*:refs/remotes/origin/*" --tags
atual=$(git tag --merged origin/main --list 'v[0-9]*' | { grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' || true; } \
  | sed 's/^v//' | sort -t. -k1,1n -k2,2n -k3,3n | tail -n 1)
atual="${atual:-0.0.0}"

unidade=""; refs=(); titulos=""; itens=""; issues=(); epico=""
if [ -n "${EPICO:-}" ]; then
  epico="$EPICO"; unidade="épico #$epico"
  base=$(git for-each-ref --format='%(refname:strip=3)' "refs/remotes/origin/epico/$epico-*" | head -n 1)
  [ -n "$base" ] || erro "épico #$epico sem branch epico/$epico-* (rode Iniciar sprint)"
  labels=$(gh api "repos/$R/issues/$epico" --jq '[.labels[].name] | join(",")')
  # dependency between epics: the epic it depends on must already be in production
  for dep in $(gh api "repos/$R/issues/$epico" --jq '.body // ""' | "${BB[@]}" esteira dependencias); do
    [ "$(gh api "repos/$R/issues/$dep" --jq .state)" = closed ] \
      || erro "o épico #$epico depende do #$dep, que ainda não está em produção (use feature flag ou espere o #$dep)"
  done
  # completeness: test, tasks and documentation merged into the epic branch
  mesclados=$(gh pr list --repo "$R" --base "$base" --state merged --limit 200 --json number,headRefName,title,labels \
    --jq '.[] | "\(.number)\t\(.headRefName)\t\(.title)\t\([.labels[].name] | join(","))"')
  faltam=()
  while IFS=$'\t' read -r n rotulos; do
    [ -n "$n" ] || continue
    tem "$rotulos" teste-aceite || tem "$rotulos" task || tem "$rotulos" documentacao || continue
    issues+=("$n")
    cut -f2 <<<"$mesclados" | grep -qE "^(teste|feature|docs)/$n-" || faltam+=("#$n")
  done < <(gh api graphql -H "GraphQL-Features: sub_issues" -f o="$OWNER" -f r="$REPO" -F n="$epico" -f query='
    query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issue(number:$n){
      subIssues(first:100){ nodes{ number labels(first:20){ nodes{ name } } } } } } }' \
    --jq '.data.repository.issue.subIssues.nodes[] | "\(.number)\t\([.labels.nodes[].name] | join(","))"')
  [ "${#issues[@]}" -gt 0 ] || erro "épico #$epico sem teste, tarefas e documentação (rode Iniciar sprint)"
  [ "${#faltam[@]}" -eq 0 ] || erro "épico #$epico incompleto: ainda não mesclados no $base: ${faltam[*]}"
  refs=("épico #$epico=refs/heads/$base")
  titulos=$(cut -f3 <<<"$mesclados")
  itens=$(awk -F'\t' 'BEGIN { OFS = "\t" } { print $1, $3, $4 }' <<<"$mesclados")
  issues+=("$epico")

  if tem "$labels" sem-release; then
    caminhos=(); mapfile -t caminhos < <("${BB[@]}" config get entrega.caminhos_artefato)
    mudou=$(git diff --name-only origin/main "origin/$base" -- "${caminhos[@]}")
    [ -z "$mudou" ] || erro "o épico #$epico é sem-release, mas muda o artefato: $(tr '\n' ' ' <<<"$mudou")"
    if [ "$SIMULAR" = true ]; then echo "[simulado] mesclar $base na develop (épico sem-release)"; exit 0; fi
    rc=0; saida=$(bash "$AQUI/git-mesclar.sh" develop develop "${refs[0]}") || rc=$?
    echo "$saida"
    if [ "$rc" -eq 3 ]; then
      gh issue edit "$epico" --repo "$R" --add-label conflito >/dev/null
      erro "conflito ao mesclar $base na develop: o épico ganhou a label conflito"
    fi
    [ "$rc" -eq 0 ] || exit "$rc"
    git push -q origin develop
    echo "Épico sem-release #$epico mesclado na develop. Próximo passo: Publicar sem release."
    exit 0
  fi
elif [ -n "${BUG:-}" ]; then
  unidade="bug #$BUG"
  ramo=$(git for-each-ref --format='%(refname:strip=3)' "refs/remotes/origin/bugfix/$BUG-*" \
    "refs/remotes/origin/hotfix/$BUG-*" | head -n 1)
  [ -n "$ramo" ] || erro "bug #$BUG sem branch bugfix/$BUG-* ou hotfix/$BUG-*"
  pr=$(gh pr list --repo "$R" --head "$ramo" --state open --json number,title,labels \
    --jq '.[0] | "\(.number)\t\(.title)\t\([.labels[].name] | join(","))"')
  [ -n "$pr" ] || erro "o bug #$BUG não tem PR aberto de $ramo para a main"
  refs=("bug #$BUG=refs/heads/$ramo"); titulos=$(cut -f2 <<<"$pr"); itens="$pr"; issues=("$BUG")
elif [ "${DEPENDENCIAS:-false}" = true ]; then
  unidade="dependências"
  prs=$(gh pr list --repo "$R" --base main --state open --limit 100 --json number,headRefName,title,labels \
    --jq '.[] | select(.headRefName | startswith("dependabot/")) | "\(.number)\t\(.headRefName)\t\(.title)\t\([.labels[].name] | join(","))"')
  [ -n "$prs" ] || erro "nenhum PR do Dependabot aberto para a main"
  while IFS=$'\t' read -r n head _ _; do refs+=("PR #$n=refs/heads/$head"); done <<<"$prs"
  titulos=$(cut -f3 <<<"$prs"); itens=$(awk -F'\t' 'BEGIN { OFS = "\t" } { print $1, $3, $4 }' <<<"$prs")
else
  erro "informe epico=<n>, bug=<n> ou dependencias=true"
fi

# ---- version: from the PR titles; a different VERSAO needs confirmation
calculada=$(printf '%s\n' "$titulos" | "${BB[@]}" esteira versao --atual "$atual")
if [ "${BUG:-}" != "" ] || [ "${DEPENDENCIAS:-false}" = true ]; then
  IFS=. read -r ma mi pa <<<"$atual"; calculada="$ma.$mi.$((pa + 1))"  # bug and maintenance: last number
fi
v="${VERSAO:-$calculada}"; v="${v#v}"
[[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || erro "versão '$v' inválida (use x.y.z)"
if [ "$v" != "$calculada" ] && [ "${CONFIRMAR_VERSAO:-false}" != true ]; then
  erro "a versão $v não bate com a classificação dos títulos ($atual -> $calculada); confirme com confirmar_versao=true"
fi
branch="release/$v"; tag="v$v"
echo "Integrando $unidade como $tag (atual: v$atual) em $branch."

if [ "$SIMULAR" = true ]; then
  for item in "${refs[@]}"; do echo "[simulado] mesclar ${item%%=*} em $branch (--no-ff)"; done
  echo "[simulado] gravar a versão $v, a seção do CHANGELOG.md e o milestone $tag; enviar $branch (candidata)"
  exit 0
fi

rc=0; saida=$(bash "$AQUI/git-mesclar.sh" "$branch" main "${refs[@]}") || rc=$?
echo "$saida"
if [ "$rc" -eq 3 ]; then
  [ -z "$epico" ] || gh issue edit "$epico" --repo "$R" --add-label conflito >/dev/null
  erro "conflito ao integrar em $branch: nada foi enviado"
fi
[ "$rc" -eq 0 ] || exit "$rc"

if [ -n "$("${BB[@]}" config get entrega.arquivo_versao)" ]; then "${BB[@]}" esteira gravar-versao "$v"; fi
printf '%s\n' "$itens" | "${BB[@]}" esteira changelog --versao "$v" --data "$(date -u +%F)"
git add -A
git diff --cached --quiet || git commit -q -m "chore(release): v$v"
git push -q origin "$branch"

milestone=$(gh api "repos/$R/milestones?state=all&per_page=100" --jq ".[] | select(.title == \"$tag\") | .number" | head -n 1)
[ -n "$milestone" ] || milestone=$(gh api -X POST "repos/$R/milestones" -f title="$tag" \
  -f description="Release $tag: $unidade" --jq .number)
for n in "${issues[@]}"; do gh issue edit "$n" --repo "$R" --milestone "$tag" >/dev/null; done
[ -z "$epico" ] || projeto texto "${PROJETO_PLANEJAMENTO:?}" "$epico" "Versão" "$tag" >/dev/null || true
echo "Enviada: $branch ($tag). A candidata é gerada a partir dela."
