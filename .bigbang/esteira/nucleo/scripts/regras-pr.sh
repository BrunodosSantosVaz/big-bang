#!/usr/bin/env bash
# "Regras do PR" (job `regras`, spec 14.2 and 15.5): runs on every PR, with the scripts and bigbang.toml of the
# TARGET branch (the PR cannot change the rules that judge it).
#
# Errors (fail the check): branch name and target (spec 11.5); missing `Refs #n` or a closing keyword in the
# body; title outside Conventional Commits; epic `sem-release` with a PR that changes the artifact; PR into
# develop that would put unpublished artifact code there (invariant of spec 11.5).
# Effects: sensitive zone -> label `revisao-humana` on the PR (unless `dono:revisao-ia` on the PR or the issue);
# label `sem-release` on the PR and on its issue kept in sync with the artifact paths.
#
# Environment: HEAD_REF, BASE_REF, PR_TITLE, PR_BODY, PR_NUMBER, PR_HEAD_SHA, PR_LABELS (comma separated),
# GITHUB_REPOSITORY, GH_TOKEN. BB (default: python3 .bigbang/bin/bb.py). DIFF_ARQUIVOS (tests: changed files).
set -euo pipefail

R="${GITHUB_REPOSITORY:?}"
head="${HEAD_REF:?}"; base="${BASE_REF:?}"; pr="${PR_NUMBER:?}"
read -r -a BB <<<"${BB:-python3 .bigbang/bin/bb.py}"
erros=0
erro() { echo "::error::$*"; erros=$((erros + 1)); }
tem_label() { [[ ",${PR_LABELS:-}," == *",$1,"* ]]; }
editar() { gh "$@" >/dev/null 2>&1 || echo "::warning::sem permissão para mudar labels (PR de fork?): gh $*"; }

# ---- names
if msg=$("${BB[@]}" esteira regra-branch "$head" "$base"); then :; else erro "$msg"; fi
if msg=$("${BB[@]}" esteira titulo "${PR_TITLE:-}"); then :; else erro "$msg"; fi

issue=""
if [[ "$head" =~ ^(feature|teste|docs|bugfix|hotfix|fundacao)/([0-9]+)- ]]; then
  tipo="${BASH_REMATCH[1]}"; issue="${BASH_REMATCH[2]}"
  if ! grep -qiE "(^|[^a-z])refs[[:space:]]+#${issue}([^0-9]|$)" <<<"${PR_BODY:-}"; then
    erro "o corpo do PR precisa de 'Refs #${issue}' (a issue da branch)"
  fi
  if grep -qiE '\b(close[sd]?|fix(e[sd])?|resolve[sd]?)[[:space:]]+#[0-9]+' <<<"${PR_BODY:-}"; then
    erro "use 'Refs #n', nunca Closes/Fixes/Resolves: quem fecha as issues é a publicação"
  fi
fi

# ---- changed files
if [ -n "${DIFF_ARQUIVOS:-}" ]; then
  arquivos="$DIFF_ARQUIVOS"
else
  arquivos=$(gh pr diff "$pr" --repo "$R" --name-only)
fi

# ---- sensitive zone -> human review (the owner's dono:revisao-ia has the last word)
opcao_teste=(); [ "${tipo:-}" != teste ] || opcao_teste=(--pr-de-teste)
sensiveis=$(printf '%s\n' "$arquivos" | "${BB[@]}" esteira sensivel "${opcao_teste[@]}")
labels_issue=""
[ -z "$issue" ] || labels_issue=$(gh api "repos/$R/issues/$issue" --jq '[.labels[].name] | join(",")' 2>/dev/null || true)
if [ -n "$sensiveis" ]; then
  echo "Zona sensível neste PR:"; while IFS= read -r linha; do echo "  - $linha"; done <<<"$sensiveis"
  if tem_label dono:revisao-ia || [[ ",$labels_issue," == *",dono:revisao-ia,"* ]]; then
    echo "O dono pôs dono:revisao-ia: a revisão continua com a IA."
  elif ! tem_label revisao-humana; then
    editar pr edit "$pr" --repo "$R" --add-label revisao-humana --remove-label revisao-ia
    echo "Revisão trocada para humana (revisao-humana)."
  fi
fi

# ---- artifact paths: sem-release in sync, epic declared sem-release, invariant of develop
artefato=$(printf '%s\n' "$arquivos" | "${BB[@]}" esteira artefato)
if [ -n "$artefato" ]; then
  if [[ ",$labels_issue," == *",sem-release,"* ]] && [[ "${tipo:-}" =~ ^(feature|teste|docs)$ ]]; then
    erro "o épico desta tarefa é sem-release, mas o PR muda o artefato ($(head -n 3 <<<"$artefato" | tr '\n' ' ')). Tire sem-release do épico com o dono e refaça o planejamento da release"
  fi
  if tem_label sem-release; then editar pr edit "$pr" --repo "$R" --remove-label sem-release; fi
else
  tem_label sem-release || editar pr edit "$pr" --repo "$R" --add-label sem-release
  if [ -n "$issue" ] && [[ ",$labels_issue," != *",sem-release,"* ]] && [[ "${tipo:-}" != bugfix && "${tipo:-}" != hotfix ]]; then
    editar issue edit "$issue" --repo "$R" --add-label sem-release
  fi
fi

if [ "$base" = develop ] && [ -n "${PR_HEAD_SHA:-}" ]; then
  mapfile -t caminhos < <("${BB[@]}" config get entrega.caminhos_artefato)
  git fetch -q origin "+refs/heads/main:refs/remotes/origin/main"
  git fetch -q origin "+refs/pull/$pr/head:refs/remotes/origin/pr-$pr" 2>/dev/null || true  # forks: PR head
  fora=$(git diff --name-only origin/main "$PR_HEAD_SHA" -- "${caminhos[@]}" 2>/dev/null || echo "?")
  if [ -n "$fora" ]; then
    erro "a develop nunca recebe código de artefato que não está em produção (invariante da seção 11.5): $(head -n 3 <<<"$fora" | tr '\n' ' ')"
  fi
fi

[ "$erros" -eq 0 ] || { echo "PR fora das regras: $erros problema(s)."; exit 1; }
echo "PR dentro das regras do processo."
