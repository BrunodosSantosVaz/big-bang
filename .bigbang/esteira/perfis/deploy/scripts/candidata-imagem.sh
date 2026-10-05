#!/usr/bin/env bash
# Deploy candidate, step 2 (spec 14.4): builds each image ONCE (deploy.servicos: servico=Dockerfile, always from the
# project root) for the platforms in deploy.plataformas, pushes it with the tag vX.Y.Z-rc.N and records its immutable
# reference (imagem@sha256:…; with several platforms, the digest of the multi-platform index). The image set goes to
# $GITHUB_OUTPUT (imagem=servico=ref,servico=ref) and to imagem.txt (one "servico=ref" line per service; a single
# service "app" keeps the bare one-line format). Everything after this (Trivy, staging, production) uses those
# digests, never a tag. Then Trivy scans each pushed image: a HIGH or CRITICAL vulnerability fails the candidate
# (SEG-19). Trivy is pinned by version and SHA-256 (trivy.sh).
# Image name: deploy.imagem with one service; deploy.imagem-<servico> with several.
# Environment: TAG (vX.Y.Z-rc.N), GITHUB_OUTPUT, RUNNER_TEMP, BB. The runner is already logged in to the registry and
# has buildx (and QEMU when a platform is not the runner's).
set -euo pipefail
shopt -s inherit_errexit
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

tag="${TAG:?}"
repositorio=$("${BB_CMD[@]}" config get deploy.imagem)
[[ "$repositorio" == "${repositorio,,}" ]] || { echo "::error::deploy.imagem precisa estar em minúsculas: $repositorio"; exit 1; }
mapfile -t servicos < <("${BB_CMD[@]}" config get deploy.servicos)
plataformas=$("${BB_CMD[@]}" config get deploy.plataformas | paste -sd, -)
tmp="${RUNNER_TEMP:-$(mktemp -d)}"

conjunto=(); linhas=()
for item in "${servicos[@]}"; do
  nome="${item%%=*}"; dockerfile="${item#*=}"
  [ -f "$dockerfile" ] || { echo "::error::falta $dockerfile (serviço $nome em deploy.servicos)"; exit 1; }
  destino="$repositorio"; [ "${#servicos[@]}" -eq 1 ] || destino="$repositorio-$nome"
  echo "== $nome: $dockerfile → $destino:$tag ($plataformas)"
  docker buildx build --pull --push --platform "$plataformas" -f "$dockerfile" \
    --label "org.opencontainers.image.version=$tag" --label "org.opencontainers.image.revision=${GITHUB_SHA:-local}" \
    --metadata-file "$tmp/bb-meta-$nome.json" -t "$destino:$tag" .
  digest=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["containerimage.digest"])' "$tmp/bb-meta-$nome.json")
  imagem="$destino@$digest"
  [[ "$imagem" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "::error::não consegui o digest da imagem enviada ($nome)"; exit 1; }
  conjunto+=("$nome=$imagem"); linhas+=("$nome=$imagem")
done
if [ "${#servicos[@]}" -eq 1 ] && [ "${conjunto[0]%%=*}" = app ]; then linhas=("${conjunto[0]#*=}"); fi
printf '%s\n' "${linhas[@]}" > imagem.txt
saida=$(IFS=,; echo "${conjunto[*]}")
if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "imagem=$saida" >> "$GITHUB_OUTPUT"; fi
echo "Imagens da candidata: $saida"

trivy=$(bash "$AQUI/trivy.sh")
for item in "${conjunto[@]}"; do
  "$trivy" image --quiet --platform "${plataformas%%,*}" --severity HIGH,CRITICAL --exit-code 1 --scanners vuln "${item#*=}" \
    || { echo "::error::Trivy: vulnerabilidade alta ou crítica em ${item%%=*} (SEG-19); corrija a base ou registre a exceção com ADR"; exit 1; }
done
echo "Trivy: nenhuma vulnerabilidade alta ou crítica."
