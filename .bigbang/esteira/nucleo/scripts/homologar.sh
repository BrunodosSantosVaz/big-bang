#!/usr/bin/env bash
# After a candidate (spec 11.6 step 8): the release unit goes to "Homologação" — epics on Planejamento, bugs on
# Bugs — losing a previous `reprovado`; the epic gets a comment with the candidate and its acceptance criteria; and
# the PR release/x.y.z -> main is opened (once). The release does NOT go to develop: develop only gets artifact
# code after production (invariant of spec 11.5).
# Environment: BRANCH (release/x.y.z), RC_TAG, PROJETO_PLANEJAMENTO/BUGS, GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN).
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
if [ -z "${BB_CACHE_DIR:-}" ]; then
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi
AQUI="$(cd "$(dirname "$0")" && pwd)"
PLAN="${PROJETO_PLANEJAMENTO:?}"; BUGS="${PROJETO_BUGS:?}"; R="${GITHUB_REPOSITORY:?}"
branch="${BRANCH:?}"; rc="${RC_TAG:?}"; v="${branch#release/}"; tag="v$v"
projeto() { bash "$AQUI/projeto.sh" "$@"; }

m=$(gh api "repos/$R/milestones?state=all&per_page=100" --jq ".[] | select(.title == \"$tag\") | .number" | head -n 1)
[ -n "$m" ] || { echo "::error::milestone $tag não encontrado (o Integrar release o cria)"; exit 1; }
while IFS=$'\t' read -r n labels; do
  [ -n "$n" ] || continue
  if [[ ",$labels," == *",epic,"* ]]; then
    projeto mover "$PLAN" "$n" "Homologação" "Em desenvolvimento|Homologação|-"
    if [[ ",$labels," == *",reprovado,"* ]]; then gh issue edit "$n" --repo "$R" --remove-label reprovado >/dev/null; fi
    criterios=$(gh api "repos/$R/issues/$n" --jq '.body // ""' | awk '/^### /{d=($0 ~ /^### Critérios de aceite/); next} d')
    gh issue comment "$n" --repo "$R" --body "### Pronto para homologar: \`$rc\`

Baixe os arquivos em https://github.com/$R/releases/tag/$rc e teste o épico inteiro.

**Critérios de aceite**

$criterios

Decisão: label \`homologado\`, ou \`reprovado\` com o motivo num comentário (pela conversa: \`bb decisao\`)." >/dev/null
  elif [[ ",$labels," == *",bug,"* ]]; then
    projeto mover "$BUGS" "$n" "Homologação" "Em correção|CI/PR|Validar PR|Homologação|-"
    if [[ ",$labels," == *",reprovado,"* ]]; then gh issue edit "$n" --repo "$R" --remove-label reprovado >/dev/null; fi
  fi
done < <(gh api "repos/$R/issues?milestone=$m&state=open&per_page=100" \
  --jq '.[] | select(has("pull_request") | not) | "\(.number)\t\([.labels[].name] | join(","))"')

existente=$(gh pr list --repo "$R" --head "$branch" --base main --state open --json number --jq '.[0].number // empty')
if [ -z "$existente" ]; then
  gh pr create --repo "$R" --base main --head "$branch" --title "chore(release): $tag" --body "## Release $tag

Candidata em homologação: \`$rc\` (https://github.com/$R/releases/tag/$rc).

Este PR é mesclado pelo botão **Publicar em produção**, depois da homologação. Não mescle à mão."
else
  echo "PR #$existente da release já existe."
fi
echo "Homologação de $tag pronta ($rc)."
