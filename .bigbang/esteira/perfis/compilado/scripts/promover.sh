#!/usr/bin/env bash
# Promotion of the compiled profile (spec 14.3): publishes the candidate RC_TAG as TAG WITHOUT recompiling. Downloads
# every asset of the candidate, checks the hashes, renames the binaries without "-rc.N" (same bytes, same SHA-256),
# rewrites the SHA256SUMS with the new names and creates the tag + Release TAG (Latest) on TARGET_SHA, with the
# version's CHANGELOG section and the hash table as notes.
# Environment: RC_TAG, TAG, TARGET_SHA, GITHUB_REPOSITORY, GH_TOKEN, BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
R="${GITHUB_REPOSITORY:?}"; rc="${RC_TAG:?}"; tag="${TAG:?}"; alvo="${TARGET_SHA:?}"; v="${tag#v}"
if gh release view "$tag" --repo "$R" >/dev/null 2>&1; then echo "Release $tag já existe."; exit 0; fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
baixado="$tmp/rc"; pub="$tmp/pub"; mkdir -p "$baixado" "$pub"
gh release download "$rc" --repo "$R" --dir "$baixado"
somas=("$baixado"/SHA256SUMS-*.txt)
[ -e "${somas[0]}" ] || { echo "::error::a candidata $rc não tem SHA256SUMS: nada foi publicado"; exit 1; }
(cd "$baixado" && for soma in SHA256SUMS-*.txt; do sha256sum -c "$soma"; done)

tabela=""
for soma in "${somas[@]}"; do
  nova_soma="$pub/$(basename "$soma")"
  while read -r hash nome; do
    novo=$("${BB_CMD[@]}" esteira nome-producao "$nome")
    cp "$baixado/$nome" "$pub/$novo"
    printf '%s  %s\n' "$hash" "$novo" >> "$nova_soma"
    tabela+="| \`$novo\` | \`$hash\` |"$'\n'
  done < "$soma"
done
for extra in "$baixado"/*; do
  nome=$(basename "$extra")
  [[ "$nome" == SHA256SUMS-* ]] || [ -e "$pub/$("${BB_CMD[@]}" esteira nome-producao "$nome")" ] || cp "$extra" "$pub/$nome"
done
(cd "$pub" && for soma in SHA256SUMS-*.txt; do sha256sum -c "$soma" >/dev/null; done)

{ git show "$alvo:CHANGELOG.md" 2>/dev/null || true; } | awk -v v="$v" '
  index($0, "## [" v "]") == 1 { dentro = 1; next }
  dentro && /^## \[/ { exit }
  dentro { print }' > "$tmp/notas.md"
{
  echo
  echo "### Origem e conferência"
  echo
  echo "Os **mesmos arquivos** da candidata \`$rc\`, homologados e aprovados (SHA-256 idêntico; o nome só perdeu o \`-rc.N\`)."
  echo
  echo "| Arquivo | SHA-256 |"
  echo "| --- | --- |"
  printf '%s' "$tabela"
  echo
  echo "Conferir: \`sha256sum -c SHA256SUMS-<sistema>.txt\` · Procedência: \`gh attestation verify <arquivo> --repo $R\`"
} >> "$tmp/notas.md"

gh release create "$tag" "$pub"/* --repo "$R" --target "$alvo" --latest \
  --title "$("${BB_CMD[@]}" config get projeto.nome) $tag" --notes-file "$tmp/notas.md"
echo "Publicada: $tag (os mesmos arquivos de $rc)."
