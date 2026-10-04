#!/usr/bin/env bash
# Deploy candidate, step 4: the pre-release vX.Y.Z-rc.N records WHAT was homologated — the image digest
# (imagem.txt) and its SBOM — so production publishes exactly that image (promover.sh) and "Voltar versão" can find
# the image of any version.
# Environment: TAG, IMAGEM (imagem@sha256:…), GITHUB_SHA, GITHUB_REPOSITORY, GH_TOKEN, BB. Files in candidata/.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
tag="${TAG:?}"; imagem="${IMAGEM:?}"; R="${GITHUB_REPOSITORY:?}"
[[ "$imagem" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "::error::IMAGEM sem digest: $imagem"; exit 1; }
if gh release view "$tag" --repo "$R" >/dev/null 2>&1; then echo "Pre-release $tag já existe."; exit 0; fi
[ "$(tr -d '[:space:]' < candidata/imagem.txt)" = "$imagem" ] || { echo "::error::candidata/imagem.txt não confere"; exit 1; }
nome=$("${BB_CMD[@]}" config get projeto.nome)
url=$("${BB_CMD[@]}" config get deploy.url_staging)
{
  echo "## Candidata para homologação"
  echo
  echo "**Pre-release para testar no staging. Não é a versão de produção.** Depois de homologada, **esta mesma imagem**"
  echo "(o mesmo digest) vai para produção, sem nova construção."
  echo
  echo "- Staging: $url"
  echo "- Imagem: \`$imagem\`"
  echo "- Commit: \`${GITHUB_SHA:-}\`"
  echo "- Procedência: \`gh attestation verify oci://$imagem --repo $R\`"
} > notas.md
gh release create "$tag" candidata/* --repo "$R" --prerelease --target "${GITHUB_SHA:?}" \
  --title "$nome $tag (homologação)" --notes-file notas.md
echo "Pre-release $tag criada com o digest da imagem."
