#!/usr/bin/env bash
# Promotion of the deploy profile (spec 14.4): production receives THE SAME images as the candidate, by digest — no
# rebuild (imagem.txt: one "servico=imagem@sha256:…" line per service, or a bare line with a single service). Migration runs with the new image before the switch; the health check runs after it, and a failure is
# reported as an alert without stopping the cleanup (the owner decides about "Voltar versão"). The Release vX.Y.Z (Latest) records the digest in
# imagem.txt, which is how "Voltar versão" finds the image of each version.
# Environment: RC_TAG, TAG, TARGET_SHA, GITHUB_REPOSITORY, GH_TOKEN, the target's variables/secrets for producao, BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
R="${GITHUB_REPOSITORY:?}"; rc="${RC_TAG:?}"; tag="${TAG:?}"; alvo_sha="${TARGET_SHA:?}"; v="${tag#v}"
if gh release view "$tag" --repo "$R" >/dev/null 2>&1; then echo "Release $tag já existe."; exit 0; fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
gh release download "$rc" --repo "$R" --dir "$tmp" --pattern imagem.txt --pattern 'sbom-*.json'
imagem=$(tr -d ' \t\r' < "$tmp/imagem.txt" | grep -v '^$' | paste -sd, -)
IFS=',' read -r -a itens <<<"$imagem"
[ "${#itens[@]}" -gt 0 ] || { echo "::error::a candidata $rc não registra imagens: nada foi publicado"; exit 1; }
for item in "${itens[@]}"; do
  [[ "$item" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "::error::a candidata $rc não registra um digest ($item): nada foi publicado"; exit 1; }
done
alvo=".bigbang/esteira/perfis/deploy/alvos/$("${BB_CMD[@]}" config get entrega.alvo)/scripts/alvo.sh"

bash "$alvo" migrar producao "$imagem"
bash "$alvo" publicar producao "$imagem"
saude="ok"
bash "$alvo" saude producao || { saude="FALHOU"; echo "::error::produção não respondeu ao health check depois de publicar $tag: avise o dono (Voltar versão)"; }

{ git show "$alvo_sha:CHANGELOG.md" 2>/dev/null || true; } | awk -v v="$v" '
  index($0, "## [" v "]") == 1 { dentro = 1; next }
  dentro && /^## \[/ { exit }
  dentro { print }' > "$tmp/notas.md"
{
  echo
  echo "### Origem e conferência"
  echo
  echo "As **mesmas imagens** da candidata \`$rc\`, homologadas no staging: \`${imagem//,/\`, \`}\`."
  echo "Health check depois da publicação: **$saude**."
} >> "$tmp/notas.md"
shopt -s nullglob
arquivos=("$tmp"/imagem.txt "$tmp"/sbom-*.json)
shopt -u nullglob
gh release create "$tag" "${arquivos[@]}" --repo "$R" --target "$alvo_sha" --latest \
  --title "$("${BB_CMD[@]}" config get projeto.nome) $tag" --notes-file "$tmp/notas.md"
echo "Publicada: $tag ($imagem)."
