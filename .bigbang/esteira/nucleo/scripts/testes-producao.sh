#!/usr/bin/env bash
# The already-published release only resumes cleanup; a new publication binds full tests to an immutable SHA.
set -euo pipefail
versao="${VERSAO:?}"; repo="${GITHUB_REPOSITORY:?}"
[[ "$versao" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 2
if gh release view "v$versao" --repo "$repo" >/dev/null 2>&1; then
  echo "v$versao já publicada: retomada da limpeza, sem redeploy nem nova rodada de testes."
  [ -z "${GITHUB_OUTPUT:-}" ] || echo "sha=retomada" >> "$GITHUB_OUTPUT"
  exit 0
fi
git fetch -q origin "refs/heads/release/$versao"
sha=$(git rev-parse FETCH_HEAD)
git checkout -q --detach "$sha"
bash .bigbang/esteira/nucleo/scripts/comando.sh instalar
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
"${BB_CMD[@]}" testes --fase producao
[ -z "${GITHUB_OUTPUT:-}" ] || echo "sha=$sha" >> "$GITHUB_OUTPUT"
echo "Suíte completa validada para $sha."
