#!/usr/bin/env bash
# Candidate, step 1 (spec 14.3): version of release/x.y.z and the next rc number. Writes versao, rc, tag and pular to
# $GITHUB_OUTPUT. Skips (pular=true, with a warning) while the version file or the CHANGELOG are not at the branch's
# version yet; refuses when vX.Y.Z is already published.
# Environment: GITHUB_REF_NAME (release/x.y.z), GITHUB_OUTPUT, BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
saida() { if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "$1" >> "$GITHUB_OUTPUT"; fi; echo "$1"; }

[[ "${GITHUB_REF_NAME:?}" =~ ^release/([0-9]+\.[0-9]+\.[0-9]+)$ ]] || { echo "::error::branch $GITHUB_REF_NAME não é release/x.y.z"; exit 1; }
v="${BASH_REMATCH[1]}"
git fetch -q --tags origin
if git rev-parse -q --verify "refs/tags/v$v" >/dev/null; then
  echo "::error::v$v já foi publicada: uma correção precisa de uma versão nova (Integrar release)."; exit 1
fi
arquivo=$("${BB_CMD[@]}" config get entrega.arquivo_versao)
if [ -n "$arquivo" ] && ! grep -qF "$v" "$arquivo"; then
  echo "::warning::$arquivo ainda não está na versão $v: candidata pulada."; saida "pular=true"; exit 0
fi
if ! "${BB_CMD[@]}" documentacao ler CHANGELOG.md | grep -F "## [$v]" >/dev/null; then
  echo "::warning::CHANGELOG.md sem a seção [$v]: candidata pulada."; saida "pular=true"; exit 0
fi
n=$(( $(git tag -l "v$v-rc.*" | wc -l) + 1 ))
saida "pular=false"; saida "versao=$v"; saida "rc=$n"; saida "tag=v$v-rc.$n"
