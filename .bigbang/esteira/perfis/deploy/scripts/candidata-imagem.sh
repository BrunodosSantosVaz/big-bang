#!/usr/bin/env bash
# Deploy candidate, step 2 (spec 14.4): builds the image ONCE from the Dockerfile at the project root, pushes it with
# the tag vX.Y.Z-rc.N and writes its immutable reference (imagem@sha256:…) to $GITHUB_OUTPUT and to imagem.txt.
# Everything after this (Trivy, staging, production) uses that digest, never a tag. Then Trivy scans the pushed
# image: a HIGH or CRITICAL vulnerability fails the candidate (SEG-19). Trivy is pinned by version and SHA-256.
# Environment: TAG (vX.Y.Z-rc.N), GITHUB_OUTPUT, RUNNER_TEMP, BB. The runner is already logged in to the registry.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
TRIVY_VERSION=0.75.0
TRIVY_SHA256=c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f

tag="${TAG:?}"
repositorio=$("${BB_CMD[@]}" config get deploy.imagem)
[[ "$repositorio" == "${repositorio,,}" ]] || { echo "::error::deploy.imagem precisa estar em minúsculas: $repositorio"; exit 1; }
[ -f Dockerfile ] || { echo "::error::falta o Dockerfile na raiz do projeto (perfil deploy)"; exit 1; }

docker build --pull --label "org.opencontainers.image.version=$tag" \
  --label "org.opencontainers.image.revision=${GITHUB_SHA:-local}" -t "$repositorio:$tag" .
docker push -q "$repositorio:$tag"
imagem=$(docker inspect --format '{{index .RepoDigests 0}}' "$repositorio:$tag")
[[ "$imagem" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "::error::não consegui o digest da imagem enviada"; exit 1; }
printf '%s\n' "$imagem" > imagem.txt
if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "imagem=$imagem" >> "$GITHUB_OUTPUT"; fi
echo "Imagem da candidata: $imagem"

ferramentas="${RUNNER_TEMP:-$(mktemp -d)}/bb-trivy"; mkdir -p "$ferramentas"
curl -fsSL -o "$ferramentas/trivy.tar.gz" \
  "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"
echo "$TRIVY_SHA256  $ferramentas/trivy.tar.gz" | sha256sum -c - >/dev/null
tar -xzf "$ferramentas/trivy.tar.gz" -C "$ferramentas" trivy
"$ferramentas/trivy" image --quiet --severity HIGH,CRITICAL --exit-code 1 --scanners vuln "$imagem" \
  || { echo "::error::Trivy: vulnerabilidade alta ou crítica na imagem (SEG-19); corrija a base ou registre a exceção com ADR"; exit 1; }
echo "Trivy: nenhuma vulnerabilidade alta ou crítica."
