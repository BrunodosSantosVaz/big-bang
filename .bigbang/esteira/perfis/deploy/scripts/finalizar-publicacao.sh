#!/usr/bin/env bash
# Creates the release after deployment has succeeded. This trusted framework script does not invoke project code.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

R="${GITHUB_REPOSITORY:?}"
rc="${RC_TAG:?}"
tag="${TAG:?}"
alvo_sha="${TARGET_SHA:?}"
imagem="${IMAGEM:?}"
saude="${SAUDE:-ok}"
v="${tag#v}"
[[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::versão inválida"; exit 2; }
[[ "$alvo_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "::error::SHA de destino inválido"; exit 2; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
gh release download "$rc" --repo "$R" --dir "$tmp" --pattern imagem.txt --pattern 'sbom-*.json'
registrado=$(tr -d ' \t\r' < "$tmp/imagem.txt" | grep -v '^$' | paste -sd, -)
[[ "$registrado" == "$imagem" ]] || { echo "::error::manifesto da candidata mudou"; exit 1; }

{ git show "$alvo_sha:CHANGELOG.md" 2>/dev/null || true; } | awk -v v="$v" '
  index($0, "## [" v "]") == 1 { dentro = 1; next }
  dentro && /^## \[/ { exit }
  dentro { print }' > "$tmp/notas.md"
{
  echo
  echo "### Origem e conferência"
  echo
  echo "As mesmas imagens da candidata $rc, homologadas no staging: $imagem."
  echo "Health check depois da publicação: $saude."
} >> "$tmp/notas.md"
shopt -s nullglob
arquivos=("$tmp"/imagem.txt "$tmp"/sbom-*.json)
shopt -u nullglob
gh release create "$tag" "${arquivos[@]}" --repo "$R" --target "$alvo_sha" --latest \
  --title "$(python3 .bigbang/bin/bb.py config get projeto.nome) $tag" --notes-file "$tmp/notas.md"
echo "Publicada: $tag ($imagem)."
