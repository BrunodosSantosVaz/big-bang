#!/usr/bin/env bash
# Downloads Trivy pinned by version and SHA-256 (once per runner) and prints the path of the binary. Used for the
# vulnerability scan of the candidate's images (SEG-19) and for their SBOM (candidata-sbom.sh).
# Environment: RUNNER_TEMP.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
TRIVY_VERSION=0.75.0
TRIVY_SHA256=c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f

ferramentas="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/bb-trivy"; mkdir -p "$ferramentas"
if [ ! -x "$ferramentas/trivy" ]; then
  curl -fsSL -o "$ferramentas/trivy.tar.gz" \
    "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"
  echo "$TRIVY_SHA256  $ferramentas/trivy.tar.gz" | sha256sum -c - >/dev/null
  tar -xzf "$ferramentas/trivy.tar.gz" -C "$ferramentas" trivy
fi
echo "$ferramentas/trivy"
