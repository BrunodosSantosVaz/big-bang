#!/usr/bin/env bash
# Approval instructions for the human who supervises (spec 11.9; #153). Production is always a human click in the
# environment `producao`; whoever starts a real publication hands over the exact link and the steps.
#   link-aprovacao.sh <workflow.yml> [descrição]
#       for the AI, right after dispatching "Publicar em produção", "Publicar sem release" or "Voltar versão" with
#       simular=false: waits (APROVACAO_ESPERA seconds, default 180) for the newest run of the workflow to be waiting
#       for approval and prints the block to paste to the human. Exit 1 when no run is waiting (prints the list link).
#   link-aprovacao.sh --resumo <descrição>
#       inside the workflow (job "conferir", simular=false): the same block with the link of the current run, also
#       written to the run summary (GITHUB_STEP_SUMMARY).
# Environment: GITHUB_REPOSITORY (otherwise `gh repo view`), GITHUB_SERVER_URL, GITHUB_RUN_ID, APROVACAO_ESPERA.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

R="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
SERVIDOR="${GITHUB_SERVER_URL:-https://github.com}"

instrucoes() { # <link> <descrição>
  cat <<EOF
## Aprovação pendente: $2

Link: $1

1. Abra o link, logado na conta que aprova a produção.
2. Clique em **Review deployments**.
3. Marque **producao** e clique em **Approve and deploy**.
4. Para não publicar, clique em **Reject**: nada muda em produção.

Depois da aprovação, o job publica e o resultado aparece no mesmo link.
EOF
}

if [ "${1:-}" = --resumo ]; then
  descricao="${2:?informe a descrição}"
  link="$SERVIDOR/$R/actions/runs/${GITHUB_RUN_ID:?}"
  instrucoes "$link" "$descricao"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then instrucoes "$link" "$descricao" >>"$GITHUB_STEP_SUMMARY"; fi
  exit 0
fi

workflow="${1:?uso: $0 <workflow.yml> [descrição] | --resumo <descrição>}"
espera="${APROVACAO_ESPERA:-180}"
inicio=$SECONDS
while :; do
  linha=$(gh run list --repo "$R" --workflow "$workflow" --status waiting --limit 1 --json url,displayTitle \
    --jq '.[0] | select(. != null) | "\(.url)\t\(.displayTitle)"')
  if [ -n "$linha" ]; then
    IFS=$'\t' read -r link titulo <<<"$linha"
    instrucoes "$link" "${2:-$titulo}"
    exit 0
  fi
  if [ $((SECONDS - inicio)) -ge "$espera" ]; then break; fi
  sleep 10
done
echo "Nenhum run de $workflow está aguardando aprovação (esperei ${espera}s)."
echo "Confira a lista e o estado do run: $SERVIDOR/$R/actions/workflows/$workflow"
exit 1
