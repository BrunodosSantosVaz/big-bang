#!/usr/bin/env bash
# Deploy target vps-docker (spec 14.4): a server reached by SSH that runs Docker Compose. Four operations:
#   alvo.sh publicar <ambiente> <imagem@sha256:…>  switches the app to that exact image (keeps the previous reference)
#   alvo.sh migrar   <ambiente> <imagem@sha256:…>  runs the `migrar` service of that image BEFORE the switch
#   alvo.sh saude    <ambiente>                    GET <url>/api/health until 200 (2 minutes)
#   alvo.sh voltar   <ambiente> <vX.Y.Z>           publishes the image recorded in the Release vX.Y.Z (never migrates)
# The project describes the app in deploy/compose.yaml: service `app` with `image: ${BB_IMAGEM}` and service
# `migrar` (same image, the migration command, profile "migrar"). App secrets stay on the server (runbook).
#
# Environment (GitHub environment variables and secrets): VPS_HOST, VPS_USUARIO, VPS_CHAVE_SSH (private key),
# VPS_KNOWN_HOSTS (the server's host key line: never trust on first use), VPS_PORTA (22), VPS_PASTA
# (/opt/<slug>/<ambiente>), REGISTRY_USUARIO/REGISTRY_TOKEN (optional, private images), BB, GITHUB_REPOSITORY.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
operacao="${1:?Uso: alvo.sh publicar|migrar|saude|voltar <ambiente> [imagem|versão]}"
ambiente="${2:?informe o ambiente (staging ou producao)}"
[[ "$ambiente" =~ ^(staging|producao)$ ]] || { echo "::error::ambiente '$ambiente' inválido"; exit 2; }
slug=$("${BB_CMD[@]}" config get projeto.slug)
compose="${COMPOSE_ARQUIVO:-deploy/compose.yaml}"

remoto() { # <script>: runs on the server with bash, every value passed already quoted
  local chave conhecidos
  chave=$(mktemp); conhecidos=$(mktemp)
  printf '%s\n' "${VPS_CHAVE_SSH:?defina o segredo VPS_CHAVE_SSH}" >"$chave"; chmod 600 "$chave"
  printf '%s\n' "${VPS_KNOWN_HOSTS:?defina VPS_KNOWN_HOSTS (a chave do servidor; nunca aceite no primeiro contato)}" >"$conhecidos"
  local opcoes=(-i "$chave" -p "${VPS_PORTA:-22}" -o "UserKnownHostsFile=$conhecidos" -o StrictHostKeyChecking=yes
                -o BatchMode=yes -o ConnectTimeout=20)
  local rc=0
  if [ -n "${COPIAR:-}" ]; then
    scp -q -i "$chave" -P "${VPS_PORTA:-22}" -o "UserKnownHostsFile=$conhecidos" -o StrictHostKeyChecking=yes \
      -o BatchMode=yes "$COPIAR" "${VPS_USUARIO:?}@${VPS_HOST:?}:$pasta/compose.yaml" || rc=$?
  fi
  [ "$rc" -ne 0 ] || ssh "${opcoes[@]}" "${VPS_USUARIO:?}@${VPS_HOST:?}" bash -s <<<"$1" || rc=$?
  rm -f "$chave" "$conhecidos"
  return "$rc"
}

pasta="${VPS_PASTA:-/opt/$slug/$ambiente}"
projeto_compose="$slug-$ambiente"
login=""
if [ -n "${REGISTRY_TOKEN:-}" ]; then
  login="printf '%s' $(printf '%q' "$REGISTRY_TOKEN") | docker login $(printf '%q' "${REGISTRY_HOST:-ghcr.io}") -u $(printf '%q' "${REGISTRY_USUARIO:?}") --password-stdin >/dev/null"
fi
exige_digest() {
  [[ "$1" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "::error::use a imagem pelo digest (imagem@sha256:…), nunca por tag: $1"; exit 2; }
}

case "$operacao" in
  publicar)
    imagem="${3:?informe a imagem@sha256:…}"; exige_digest "$imagem"
    [ -f "$compose" ] || { echo "::error::$compose não existe (o projeto descreve o app e a migração nele)"; exit 1; }
    remoto "set -euo pipefail; mkdir -p $(printf '%q' "$pasta")" >/dev/null
    COPIAR="$compose" remoto "set -euo pipefail
cd $(printf '%q' "$pasta")
$login
if [ -f imagem.env ]; then cp imagem.env imagem.anterior.env; fi
printf 'BB_IMAGEM=%s\n' $(printf '%q' "$imagem") > imagem.env
docker compose -p $(printf '%q' "$projeto_compose") --env-file imagem.env pull app
docker compose -p $(printf '%q' "$projeto_compose") --env-file imagem.env up -d --remove-orphans app
echo publicada: \$(cut -d= -f2- imagem.env)"
    echo "$ambiente: $imagem publicada em $VPS_HOST:$pasta"
    ;;
  migrar)
    imagem="${3:?informe a imagem@sha256:…}"; exige_digest "$imagem"
    [ -f "$compose" ] || { echo "::error::$compose não existe"; exit 1; }
    remoto "set -euo pipefail; mkdir -p $(printf '%q' "$pasta")" >/dev/null
    COPIAR="$compose" remoto "set -euo pipefail
cd $(printf '%q' "$pasta")
$login
BB_IMAGEM=$(printf '%q' "$imagem") docker compose -p $(printf '%q' "$projeto_compose") --profile migrar run --rm migrar"
    echo "$ambiente: migração de $imagem concluída (antes da troca de versão)"
    ;;
  saude)
    url="${SAUDE_URL:-$("${BB_CMD[@]}" config get "deploy.url_$ambiente")}"  # SAUDE_URL: local tests only
    for _ in $(seq 1 "${SAUDE_TENTATIVAS:-24}"); do
      if curl -fsS -o /dev/null --max-time 5 "$url/api/health"; then echo "$ambiente saudável: $url/api/health"; exit 0; fi
      sleep "${SAUDE_INTERVALO:-5}"
    done
    echo "::error::$ambiente não respondeu em $url/api/health"; exit 1
    ;;
  voltar)
    versao="${3:?informe a versão (vX.Y.Z)}"
    imagem=$(gh release download "$versao" --repo "${GITHUB_REPOSITORY:?}" --pattern imagem.txt --output - | tr -d '[:space:]')
    exige_digest "$imagem"
    echo "Voltando $ambiente para $versao ($imagem). Migrações não são desfeitas (expandir-e-contrair, DAD-02)."
    exec bash "$0" publicar "$ambiente" "$imagem"
    ;;
  *) echo "::error::operação '$operacao' desconhecida (publicar, migrar, saude, voltar)"; exit 2 ;;
esac
