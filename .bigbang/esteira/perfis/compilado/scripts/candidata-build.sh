#!/usr/bin/env bash
# Candidate, step 2: builds ONE system with compilado.build_<sistema> from bigbang.toml. Contract of the build
# command: it writes exactly one file (the binary or installer) into $BB_SAIDA (dist/<sistema>); it may read
# BB_VERSAO, BB_RC and BB_SISTEMA. The file is copied to candidata/<slug>-vX.Y.Z-rc.N-<sistema><ext> with its
# SHA256SUMS-<sistema>.txt. Runs on the system's own runner (Windows runs it in Git Bash).
# Environment: BB_SISTEMA, BB_VERSAO, BB_RC, BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
sistema="${BB_SISTEMA:?}"; versao="${BB_VERSAO:?}"; rc="${BB_RC:?}"
saida="dist/$sistema"
rm -rf "$saida" candidata && mkdir -p "$saida" candidata
comando=$("${BB_CMD[@]}" config get "compilado.build_$sistema")
echo "+ $comando"
BB_SAIDA="$saida" BB_VERSAO="$versao" BB_RC="$rc" BB_SISTEMA="$sistema" bash -c "$comando"
mapfile -t arquivos < <(find "$saida" -maxdepth 1 -type f)
if [ "${#arquivos[@]}" -ne 1 ]; then
  echo "::error::o build de $sistema deve deixar exatamente um arquivo em $saida (deixou ${#arquivos[@]})"; exit 1
fi
nome=$("${BB_CMD[@]}" esteira nome-candidata "$versao" "$rc" "$sistema" "$(basename "${arquivos[0]}")" | tr -d '\r')
cp "${arquivos[0]}" "candidata/$nome"
hash=$(sha256sum < "candidata/$nome" | cut -d' ' -f1)
printf '%s  %s\n' "$hash" "$nome" > "candidata/SHA256SUMS-$sistema.txt"
echo "$sistema: $nome ($hash)"
