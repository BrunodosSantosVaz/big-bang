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
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

R="${GITHUB_REPOSITORY:?}"
head="${HEAD_REF:?}"; base="${BASE_REF:?}"; pr="${PR_NUMBER:?}"
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
erros=0
erro() { echo "::error::$*"; erros=$((erros + 1)); }
tem_label() { [[ ",${PR_LABELS:-}," == *",$1,"* ]]; }
editar() { gh "$@" >/dev/null 2>&1 || echo "::warning::sem permissão para mudar labels (PR de fork?): gh $*"; }

# ---- names
if msg=$("${BB_CMD[@]}" esteira regra-branch "$head" "$base"); then :; else erro "$msg"; fi
if msg=$("${BB_CMD[@]}" esteira titulo "${PR_TITLE:-}"); then :; else erro "$msg"; fi

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

# ---- changed files: the paginated files API (gh pr diff refuses PRs with more than 300 files, like a framework update)
if [ -n "${DIFF_ARQUIVOS:-}" ]; then
  arquivos="$DIFF_ARQUIVOS"
else
  arquivos=$(gh api --paginate "repos/$R/pulls/$pr/files" \
    --jq '.[] | .filename, (.previous_filename // empty)' | sort -u)
fi
# unified diff of tests/aceite/ only (the one part read line by line); a file without patch fails closed
diff_aceite() {
  if [ -n "${DIFF_TEXTO:-}" ]; then printf '%s\n' "$DIFF_TEXTO"; return; fi
  gh api --paginate "repos/$R/pulls/$pr/files" --jq '.[]
    | select((.filename | startswith("tests/aceite/")) or ((.previous_filename // "") | startswith("tests/aceite/")))
    | "diff --git a/\(.previous_filename // .filename) b/\(.filename)\n--- a/\(.previous_filename // .filename)\n+++ b/\(.filename)\n\(.patch // "BB-SEM-PATCH \(.filename)")"'
}

# ---- sensitive zone -> human review (the owner's dono:revisao-ia has the last word)
opcao_teste=(); [ "${tipo:-}" != teste ] || opcao_teste=(--pr-de-teste)
# a task that only releases the pending marks of its own tests (spec 11.7) is not a sensitive change
if [ -z "${opcao_teste[*]}" ] && [ -n "$issue" ] && grep -q '^tests/aceite/' <<<"$arquivos"; then
  diff_texto=$(diff_aceite)
  if printf '%s\n' "$diff_texto" | "${BB_CMD[@]}" esteira so-liberacao "$issue"; then
    opcao_teste=(--pr-de-teste); echo "tests/aceite/: só a retirada das marcas de pendente da #$issue."
  fi
fi
sensiveis=$(printf '%s\n' "$arquivos" | "${BB_CMD[@]}" esteira sensivel "${opcao_teste[@]}")
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

# ---- lock on tests/aceite/ (spec 11.7): the owner's teste-alterado-aprovado is the only way around it
if grep -q '^tests/aceite/' <<<"$arquivos"; then
  [ -n "${diff_texto:-}" ] || diff_texto=$(diff_aceite)
  if grep -q '^BB-SEM-PATCH ' <<<"$diff_texto"; then
    erro "tests/aceite/ com diff grande demais para conferir a trava; divida o PR"
  fi
  aprovado=(); if tem_label teste-alterado-aprovado; then aprovado=(--aprovado); fi
  if ! msg=$(printf '%s\n' "$diff_texto" | "${BB_CMD[@]}" esteira trava-aceite "${tipo:-outro}" ${issue:+"$issue"} "${aprovado[@]}"); then
    while IFS= read -r linha; do erro "$linha"; done <<<"$msg"
  fi
fi

# ---- content of the PR head (read as data by the target branch's bb): pending marks
dados="${DADOS_PR:-}"
if [ -z "$dados" ] && [ -n "${PR_HEAD_SHA:-}" ]; then
  git fetch -q origin "+refs/pull/$pr/head:refs/remotes/origin/pr-$pr" 2>/dev/null || true
  if git cat-file -e "${PR_HEAD_SHA}^{commit}" 2>/dev/null; then
    dados=$(mktemp -d); git worktree add -q --detach "$dados" "$PR_HEAD_SHA"
  fi
fi
if [ -n "$dados" ]; then
  pendentes=$("${BB_CMD[@]}" esteira pendentes --dados "$dados")
  if [ -n "$pendentes" ]; then
    mesclados=$(gh api "repos/$R/pulls?state=closed&per_page=100" \
      --jq '.[] | select(.merged_at != null) | .head.ref')
    while IFS=$'\t' read -r n onde; do
      if grep -qE "^(feature|docs)/$n-" <<<"$mesclados" \
         || [ "$(gh api "repos/$R/issues/$n" --jq .state 2>/dev/null || echo open)" = closed ]; then
        erro "$onde: teste ainda marcado como pendente da #$n, que já foi mesclada ou fechada"
      fi
    done <<<"$pendentes"
  fi
  mudados=$(mktemp); printf '%s\n' "$arquivos" > "$mudados"
  if ! msg=$("${BB_CMD[@]}" esteira rastreabilidade --dados "$dados" --mudados "$mudados"); then
    while IFS= read -r linha; do erro "rastreabilidade: $linha"; done <<<"$msg"
  fi
  if ! msg=$("${BB_CMD[@]}" esteira guarda-stack --dados "$dados"); then
    while IFS= read -r linha; do erro "guarda da stack: $linha"; done <<<"$msg"
  fi
else
  echo "::notice::conteúdo do PR indisponível: pendentes, rastreabilidade e guarda da stack não conferidos"
fi

# ---- artifact paths: sem-release in sync, epic declared sem-release, invariant of develop
artefato=$(printf '%s\n' "$arquivos" | "${BB_CMD[@]}" esteira artefato)
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
  mapfile -t caminhos < <("${BB_CMD[@]}" config get entrega.caminhos_artefato)
  git fetch -q origin "+refs/heads/main:refs/remotes/origin/main"
  git fetch -q origin "+refs/pull/$pr/head:refs/remotes/origin/pr-$pr" 2>/dev/null || true  # forks: PR head
  fora=$(git diff --name-only origin/main "$PR_HEAD_SHA" -- "${caminhos[@]}" 2>/dev/null || echo "?")
  if [ -n "$fora" ]; then
    erro "a develop nunca recebe código de artefato que não está em produção (invariante da seção 11.5): $(head -n 3 <<<"$fora" | tr '\n' ' ')"
  fi
fi

[ "$erros" -eq 0 ] || { echo "PR fora das regras: $erros problema(s)."; exit 1; }
echo "PR dentro das regras do processo."
