#!/usr/bin/env bash
# Candidate, step 3: only when EVERY system built. Checks the hashes and creates the pre-release vX.Y.Z-rc.N with
# the binaries, their SHA256SUMS, the SBOM and the notes. The owner tests exactly these files; production promotes
# the same bytes (promover.sh).
# Environment: TAG (vX.Y.Z-rc.N), GITHUB_SHA, GITHUB_REF_NAME, GITHUB_REPOSITORY, GH_TOKEN, BB. Files in candidata/.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
tag="${TAG:?}"; R="${GITHUB_REPOSITORY:?}"
if gh release view "$tag" --repo "$R" >/dev/null 2>&1; then echo "Pre-release $tag já existe."; exit 0; fi
(cd candidata && for soma in SHA256SUMS-*.txt; do sha256sum -c "$soma"; done)
nome=$("${BB_CMD[@]}" config get projeto.nome)
{
  echo "## Candidata para homologação"
  echo
  echo "**Pre-release para testar. Não é a versão de produção.** Depois de homologados, estes mesmos arquivos são"
  echo "publicados como \`${tag%-rc.*}\` sem recompilar (mesmo SHA-256; o nome só perde o \`-rc.N\`)."
  echo
  echo "- Branch: \`${GITHUB_REF_NAME:-}\` · Commit: \`${GITHUB_SHA:-}\`"
  echo "- Conferir: \`sha256sum -c SHA256SUMS-<sistema>.txt\`"
  echo "- Procedência: \`gh attestation verify <arquivo> --repo $R\`"
  echo "- Componentes (SBOM CycloneDX): \`sbom-cyclonedx.json\`"
} > notas.md
gh release create "$tag" candidata/* --repo "$R" --prerelease --target "${GITHUB_SHA:?}" \
  --title "$nome $tag (homologação)" --notes-file notas.md
echo "Pre-release $tag criada."
