#!/usr/bin/env bash
# Deploy target vps-docker (spec 14.4): a server reached by SSH that runs Docker Compose. Five operations:
#   alvo.sh publicar <ambiente> <conjunto>  switches every published service to its exact image (keeps the previous set)
#   alvo.sh checar   <ambiente> <conjunto>  runs the pre-check service (deploy.servico_checar), when there is one
#   alvo.sh migrar   <ambiente> <conjunto>  pre-check, then the migration service (deploy.servico_migrar) of the NEW
#                                           images, BEFORE the switch; a failure leaves the running version untouched
#   alvo.sh saude    <ambiente>             GET <url><deploy.caminho_saude> until 200 (2 minutes)
#   alvo.sh voltar   <ambiente> <vX.Y.Z>    publishes the image set recorded in the Release vX.Y.Z (never migrates)
# <conjunto> is the image set of a candidate: "servico=imagem@sha256:…" items separated by commas, one per service of
# deploy.servicos (a bare "imagem@sha256:…" is accepted when there is a single service). Always by digest, never a tag.
# The project describes the app in deploy/compose.yaml: each published service with `image: ${BB_IMAGEM_<SERVICO>}`
# (with one service, `${BB_IMAGEM}` also works), the migration service (profile with its own name) and, optionally, the
# pre-check service. Services that are not in deploy.servicos (a database, a proxy) are never recreated by a deploy.
# App secrets stay on the server (runbook).
#
# Environment (GitHub environment variables and secrets): VPS_HOST, VPS_USUARIO, VPS_CHAVE_SSH (private key),
# VPS_KNOWN_HOSTS (the server's host key line: never trust on first use), VPS_PORTA (22), VPS_PASTA
# (/opt/<slug>/<ambiente>), VPS_DOCKER_SUDO (true: runs `sudo -n docker`), VPS_ENV_ARQUIVO (extra env-file on the
# server, passed to every compose command), REGISTRY_USUARIO/REGISTRY_TOKEN (optional, private images), BB,
# GITHUB_REPOSITORY.
set -euo pipefail
shopt -s inherit_errexit
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
operacao="${1:?Uso: alvo.sh publicar|checar|migrar|saude|voltar <ambiente> [conjunto|versão]}"
ambiente="${2:?informe o ambiente (staging ou producao)}"
[[ "$ambiente" =~ ^(staging|producao)$ ]] || { echo "::error::ambiente '$ambiente' inválido"; exit 2; }
slug=$("${BB_CMD[@]}" config get projeto.slug)
compose="${COMPOSE_ARQUIVO:-deploy/compose.yaml}"
mapfile -t servicos < <("${BB_CMD[@]}" config get deploy.servicos | cut -d= -f1)
servico_migrar=$("${BB_CMD[@]}" config get deploy.servico_migrar)
servico_checar=$("${BB_CMD[@]}" config get deploy.servico_checar)

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
docker="docker"
if [ "${VPS_DOCKER_SUDO:-false}" = true ]; then docker="sudo -n docker"; fi
dc="$docker compose -p $(printf '%q' "$slug-$ambiente")"  # + --env-file <imagens> [--env-file VPS_ENV_ARQUIVO]
extra=""
if [ -n "${VPS_ENV_ARQUIVO:-}" ]; then extra=" --env-file $(printf '%q' "$VPS_ENV_ARQUIVO")"; fi
login=""
if [ -n "${REGISTRY_TOKEN:-}" ]; then
  login="printf '%s' $(printf '%q' "$REGISTRY_TOKEN") | $docker login $(printf '%q' "${REGISTRY_HOST:-ghcr.io}") -u $(printf '%q' "${REGISTRY_USUARIO:?}") --password-stdin >/dev/null"
fi
exige_digest() {
  [[ "$1" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "::error::use a imagem pelo digest (imagem@sha256:…), nunca por tag: $1"; exit 2; }
}
variavel() { local v="${1^^}"; echo "BB_IMAGEM_${v//-/_}"; }
# Turns the image set into the env-file lines the compose file reads; refuses a set that does not cover every service.
ambiente_das_imagens() { # <conjunto>
  local itens item nome ref primeiro="" s
  declare -A refs=()
  IFS=',' read -r -a itens <<<"$1"
  for item in "${itens[@]}"; do
    if [[ "$item" == *=* ]]; then nome="${item%%=*}"; ref="${item#*=}"
    elif [ "${#servicos[@]}" -eq 1 ]; then nome="${servicos[0]}"; ref="$item"
    else echo "::error::com vários serviços, informe servico=imagem@sha256:… para cada um: $item"; exit 2; fi
    exige_digest "$ref"
    [[ " ${servicos[*]} " == *" $nome "* ]] || { echo "::error::serviço '$nome' não está em deploy.servicos"; exit 2; }
    refs[$nome]="$ref"
  done
  for s in "${servicos[@]}"; do
    [ -n "${refs[$s]:-}" ] || { echo "::error::falta a imagem do serviço '$s' (deploy.servicos)"; exit 2; }
    [ -n "$primeiro" ] || primeiro="${refs[$s]}"
    printf '%s=%s\n' "$(variavel "$s")" "${refs[$s]}"
  done
  printf 'BB_IMAGEM=%s\n' "$primeiro"
}
lista_servicos() { local s r=""; for s in "${servicos[@]}"; do r+=" $(printf '%q' "$s")"; done; echo "$r"; }
# Remote lines that run a one-off service (pre-check or migration) with the images in imagem.novo.env. Its stdin is
# /dev/null: the remote script itself arrives on stdin, and `compose run` would swallow the lines after it.
rodar() { # <servico> <o que faz>
  echo "echo '+ $2 ($1)'
$dc --env-file imagem.novo.env$extra --profile $(printf '%q' "$1") run --rm -T $(printf '%q' "$1") </dev/null"
}
preparar_novo() { # <conjunto>: remote lines that enter the folder, log in and write imagem.novo.env
  local conteudo
  conteudo=$(ambiente_das_imagens "$1")
  printf '%s\n' "set -euo pipefail" "cd $(printf '%q' "$pasta")" "$login" \
    "printf '%s\\n' $(printf '%q' "$conteudo") > imagem.novo.env"
}
exige_compose() { [ -f "$compose" ] || { echo "::error::$compose não existe (o projeto descreve os serviços nele)"; exit 1; }; }

case "$operacao" in
  publicar)
    exige_compose; preparo=$(preparar_novo "${3:?informe o conjunto de imagens (servico=imagem@sha256:…)}")
    remoto "set -euo pipefail; mkdir -p $(printf '%q' "$pasta")" >/dev/null
    COPIAR="$compose" remoto "$preparo
if [ -f imagem.env ]; then cp imagem.env imagem.anterior.env; fi
mv imagem.novo.env imagem.env
$dc --env-file imagem.env$extra pull$(lista_servicos)
$dc --env-file imagem.env$extra up -d --remove-orphans$(lista_servicos)
echo publicada:; grep '^BB_IMAGEM_' imagem.env"
    echo "$ambiente: ${servicos[*]} publicados em $VPS_HOST:$pasta"
    ;;
  checar|migrar)
    exige_compose; preparo=$(preparar_novo "${3:?informe o conjunto de imagens (servico=imagem@sha256:…)}")
    passos=""
    if [ -n "$servico_checar" ]; then passos+="$(rodar "$servico_checar" "pré-checagem do servidor")"$'\n'; fi
    if [ "$operacao" = migrar ]; then passos+="$(rodar "$servico_migrar" "migração com a imagem nova")"$'\n'; fi
    if [ -z "$passos" ]; then echo "$ambiente: sem pré-checagem (deploy.servico_checar vazio)"; exit 0; fi
    remoto "set -euo pipefail; mkdir -p $(printf '%q' "$pasta")" >/dev/null
    if ! COPIAR="$compose" remoto "$preparo
$passos"; then
      echo "::error::$ambiente: $operacao falhou; a versão no ar não foi trocada"; exit 1
    fi
    echo "$ambiente: $operacao concluída (antes da troca de versão)"
    ;;
  saude)
    url="${SAUDE_URL:-$("${BB_CMD[@]}" config get "deploy.url_$ambiente")}"  # SAUDE_URL: local tests only
    caminho=$("${BB_CMD[@]}" config get deploy.caminho_saude)
    for _ in $(seq 1 "${SAUDE_TENTATIVAS:-24}"); do
      if curl -fsS -o /dev/null --max-time 5 "$url$caminho"; then echo "$ambiente saudável: $url$caminho"; exit 0; fi
      sleep "${SAUDE_INTERVALO:-5}"
    done
    echo "::error::$ambiente não respondeu em $url$caminho"; exit 1
    ;;
  voltar)
    versao="${3:?informe a versão (vX.Y.Z)}"
    conjunto=$(gh release download "$versao" --repo "${GITHUB_REPOSITORY:?}" --pattern imagem.txt --output - \
      | tr -d ' \t\r' | grep -v '^$' | paste -sd, -)
    ambiente_das_imagens "$conjunto" >/dev/null
    echo "Voltando $ambiente para $versao ($conjunto). Migrações não são desfeitas (expandir-e-contrair, DAD-02)."
    exec bash "$0" publicar "$ambiente" "$conjunto"
    ;;
  *) echo "::error::operação '$operacao' desconhecida (publicar, checar, migrar, saude, voltar)"; exit 2 ;;
esac
