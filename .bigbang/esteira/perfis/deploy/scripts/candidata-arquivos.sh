#!/usr/bin/env bash
# Build package/static files once, without GitHub or deployment credentials, then pin them in a SHA-256 manifest.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
build_tmp=$(mktemp -d)
trap 'rm -rf "$build_tmp"' EXIT
mkdir -p "$build_tmp/home" "$build_tmp/tmp"
project_environment=("PATH=${PATH:-/usr/bin:/bin}" "HOME=$build_tmp/home" "TMPDIR=$build_tmp/tmp" "CI=true"
                     "BB=${BB:-python3 .bigbang/bin/bb.py}")
for variable in LANG LC_ALL TZ; do
  if [[ -n "${!variable:-}" ]]; then project_environment+=("$variable=${!variable}"); fi
done
for variable in GITHUB_SHA GITHUB_REF TAG; do
  if [[ -n "${!variable:-}" ]]; then project_environment+=("$variable=${!variable}"); fi
done
env -i "${project_environment[@]}" bash .bigbang/esteira/nucleo/scripts/comando.sh build
PYTHONPATH=.bigbang python3 -m bb.artifacts build --root . --output candidata
manifest_sha=$(awk '{print $1}' candidata/manifesto.sha256)
[[ "$manifest_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "::error::SHA-256 do manifesto inválido"; exit 1; }
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then echo "imagem=sha256:$manifest_sha" >> "$GITHUB_OUTPUT"; fi
echo "Manifesto imutável: sha256:$manifest_sha"
