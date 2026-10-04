#!/usr/bin/env bash
# Regression order of a bug PR (spec 11.7, TST-03): the FIRST commit after the target branch only adds/changes tests
# and the stack's tests FAIL on it; the fix comes in a later commit. Runs inside the `check` job (no secrets), because
# it executes the PR's code — never in a job that holds a token with write access (SEG-18).
# Environment: BASE_REF (main), PR_HEAD_SHA, BB. Needs the full history (fetch-depth 0).
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
base="${BASE_REF:?}"; head="${PR_HEAD_SHA:?}"
git fetch -q origin "+refs/heads/$base:refs/remotes/origin/$base"
mapfile -t commits < <(git rev-list --reverse --no-merges "origin/$base..$head")
if [ "${#commits[@]}" -lt 2 ]; then
  echo "::error::PR de bug precisa de pelo menos dois commits: primeiro o teste de regressão que falha, depois a correção"
  exit 1
fi
primeiro="${commits[0]}"
fora=$(git diff-tree --no-commit-id --name-only -r "$primeiro" | { grep -vE '^tests?/|(^|/)(test_[^/]+|[^/]+_test\.[a-z]+|[^/]+\.(test|spec)\.[a-z]+)$' || true; })
if [ -n "$fora" ]; then
  echo "::error::o primeiro commit (${primeiro:0:7}) deve ter só o teste de regressão; também mexe em: $(tr '\n' ' ' <<<"$fora")"
  exit 1
fi
pasta=$(mktemp -d)
git worktree add -q --detach "$pasta" "$primeiro"
trap 'git worktree remove --force "$pasta" >/dev/null 2>&1 || true' EXIT
comandos=$("${BB_CMD[@]}" config get comandos.testes)
aceite=$("${BB_CMD[@]}" config get comandos.testes_aceite)
cd "$pasta"
bash -c "${comandos:-true}" >/dev/null 2>&1 && passou=true || passou=false
if [ "$passou" = true ] && [ -n "$aceite" ]; then bash -c "$aceite" >/dev/null 2>&1 || passou=false; fi
if [ "$passou" = true ]; then
  echo "::error::os testes PASSAM no primeiro commit (${primeiro:0:7}): o teste de regressão precisa falhar sem a correção"
  exit 1
fi
echo "Ordem de regressão correta: o teste falha em ${primeiro:0:7} e a correção vem depois."
