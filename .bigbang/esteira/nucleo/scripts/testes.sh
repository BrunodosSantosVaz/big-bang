#!/usr/bin/env bash
# One execution after implementation/build: Flash selects affected tests; uncertain/structural changes run all.
set -euo pipefail
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
branch="${GITHUB_HEAD_REF:-${GITHUB_REF_NAME:-}}"
args=()
if [[ "$branch" =~ ^release/([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  args=(--base origin/main --fase candidata --versao "${BASH_REMATCH[1]}")
elif [ -n "${BB_BASE_TESTES:-}" ]; then
  args=(--base "$BB_BASE_TESTES")
fi
"${BB_CMD[@]}" testes "${args[@]}"
