#!/usr/bin/env bash
# Deploy candidate, step 4: the pre-release vX.Y.Z-rc.N records WHAT was homologated — the image digest
# (imagem.txt) and its SBOM — so production publishes exactly that image (promover.sh) and "Voltar versão" can find
# the image of any version.
# Environment: TAG, IMAGEM (the image set: servico=imagem@sha256:…,… or a bare imagem@sha256:…), GITHUB_SHA,
# GITHUB_REPOSITORY, GH_TOKEN, BB. Files in candidata/ (candidata-sbom.sh).
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
tag="${TAG:?}"; imagem="${IMAGEM:?}"; R="${GITHUB_REPOSITORY:?}"
IFS=',' read -r -a itens <<<"$imagem"
for item in "${itens[@]}"; do
  [[ "$item" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "::error::IMAGEM sem digest: $item"; exit 1; }
done
if gh release view "$tag" --repo "$R" >/dev/null 2>&1; then echo "Pre-release $tag já existe."; exit 0; fi
registrado=$(tr -d ' \t\r' < candidata/imagem.txt | grep -v '^$' | paste -sd, -)
[ "$registrado" = "$imagem" ] || [ "app=$registrado" = "$imagem" ] \
  || { echo "::error::candidata/imagem.txt não confere com as imagens construídas"; exit 1; }
rm -f candidata/imagens.sha256
nome=$("${BB_CMD[@]}" config get projeto.nome)
url=$("${BB_CMD[@]}" config get deploy.url_staging)
{
  echo "## Candidata para homologação"
  echo
  echo "**Pre-release para testar no staging. Não é a versão de produção.** Depois de homologada, **estas mesmas imagens**"
  echo "(os mesmos digests) vão para produção, sem nova construção."
  echo
  echo "- Staging: $url"
  for item in "${itens[@]}"; do echo "- Imagem: \`$item\`"; done
  echo "- Commit: \`${GITHUB_SHA:-}\`"
  echo "- Procedência: \`gh attestation verify oci://<imagem@sha256:…> --repo $R\`"
} > notas.md
gh release create "$tag" candidata/* --repo "$R" --prerelease --target "${GITHUB_SHA:?}" \
  --title "$nome $tag (homologação)" --notes-file notas.md
echo "Pre-release $tag criada com os digests das imagens."
