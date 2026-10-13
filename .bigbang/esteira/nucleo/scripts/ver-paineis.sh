#!/usr/bin/env bash
# "Ver painéis" (spec 14.2): read only. Every board column by column (number, title, Sprint) and what waits for the
# owner, in the log and in the run summary. In a public repository the summary is public too.
# Environment: PROJETO_QUADRO, PROJECT_NUMBER, GITHUB_REPOSITORY, GH_TOKEN, GITHUB_STEP_SUMMARY (optional).
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

if [ -z "${BB_CACHE_DIR:-}" ]; then  # board ids and options fetched once per run (projeto.sh)
  BB_CACHE_DIR=$(mktemp -d); export BB_CACHE_DIR; trap 'rm -rf "$BB_CACHE_DIR"' EXIT
fi
shopt -s inherit_errexit

AQUI="$(cd "$(dirname "$0")" && pwd)"
projeto() { bash "$AQUI/projeto.sh" "$@"; }
if [ -n "${BB:-}" ]; then
  read -r -a BB_CMD <<<"$BB"
else
  BB_CMD=("${PYTHON:-python3}" "${BB_ENTRY:-$AQUI/../../../bin/bb.py}")
  [ -z "${BB_ROOT:-}" ] || BB_CMD+=(--raiz "$BB_ROOT")
fi
bb() { "${BB_CMD[@]}" esteira resumo-posses; }

painel() { # <nome> <numero>
  local nome="$1" numero="$2" colunas quadro coluna linhas
  colunas=$(projeto colunas "$numero"); quadro=$(projeto quadro "$numero")
  echo "## $nome (painel $numero)"; echo
  [ -n "$quadro" ] || { echo "Nenhuma issue aberta."; echo; return 0; }
  while IFS= read -r coluna; do
    linhas=$(awk -F'\t' -v c="$coluna" '$1 == c' <<<"$quadro")
    [ -n "$linhas" ] || continue
    if [ "$coluna" = "-" ]; then echo "### (sem coluna)"; else echo "### $coluna"; fi; echo
    awk -F'\t' '{ printf "- #%s %s", $2, $3; if ($4 != "-") printf " (%s)", $4; print "" }' <<<"$linhas"; echo
  done <<<"$colunas"$'\n-'
}

obter_quadro() {
  local num="${PROJETO_QUADRO:-${PROJECT_NUMBER:-}}"
  if [ -z "$num" ] || [ "$num" = "0" ]; then
    num=$("${BB_CMD[@]}" config get paineis.quadro 2>/dev/null || true)
  fi
  if [ "$num" = "0" ]; then
    num=""
  fi
  printf '%s' "$num"
}

espera() { # what waits for the owner
  local q; q=$(obter_quadro)
  local itens=""
  if [ -n "$q" ]; then
    itens+=$(projeto quadro "$q" | awk -F'\t' '
      $1 ~ /^(Refinement|Backlog Refinement)$/ { printf "- Aprovar o refinamento do #%s %s\n", $2, $3 }
      $1 ~ /^(Prototyping|Validar protótipo)$/ { printf "- Validar o protótipo do #%s %s\n", $2, $3 }
      $1 ~ /^(In Review|Validar PR)$/ { printf "- Revisar o PR da #%s %s\n", $2, $3 }
      $1 ~ /^(QA|Homologação)$/ { printf "- Homologar o #%s %s\n", $2, $3 }
    ')
  fi
  echo "## O que espera pelo dono"; echo
  if [ -n "$itens" ]; then printf '%s\n' "$itens" | sed '/^$/d'; else echo "Nada."; fi
  echo
}

saida=$(
  espera
  num=$(obter_quadro)
  if [ -n "$num" ]; then
    painel "Quadro" "$num"
  fi
  bb
)
printf '%s\n' "$saida"
[ -z "${GITHUB_STEP_SUMMARY:-}" ] || printf '%s\n' "$saida" >> "$GITHUB_STEP_SUMMARY"
