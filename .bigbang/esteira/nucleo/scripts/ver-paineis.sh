#!/usr/bin/env bash
# "Ver painéis" (spec 14.2): read only. Every board column by column (number, title, Sprint) and what waits for the
# owner, in the log and in the run summary. In a public repository the summary is public too.
# Environment: PROJETO_PLANEJAMENTO/EXECUCAO/BUGS, GITHUB_REPOSITORY, GH_TOKEN, GITHUB_STEP_SUMMARY (optional).
set -euo pipefail
shopt -s inherit_errexit

AQUI="$(cd "$(dirname "$0")" && pwd)"
projeto() { bash "$AQUI/projeto.sh" "$@"; }

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

espera() { # what waits for the owner
  local p="${PROJETO_PLANEJAMENTO:-}" e="${PROJETO_EXECUCAO:-}" b="${PROJETO_BUGS:-}" itens=""
  [ -z "$p" ] || itens+=$(projeto quadro "$p" | awk -F'\t' '$1 == "Backlog Refinement" { printf "- Aprovar o refinamento do #%s %s\n", $2, $3 }
    $1 == "Validar protótipo" { printf "- Validar o protótipo do #%s %s\n", $2, $3 }
    $1 == "Homologação" { printf "- Homologar o épico #%s %s\n", $2, $3 }')
  [ -z "$e" ] || itens+=$(projeto quadro "$e" | awk -F'\t' '$1 == "Validar PR" { printf "\n- Revisar o PR da #%s %s", $2, $3 }')
  [ -z "$b" ] || itens+=$(projeto quadro "$b" | awk -F'\t' '$1 == "Validar PR" { printf "\n- Revisar o PR do bug #%s %s", $2, $3 }
    $1 == "Homologação" { printf "\n- Homologar o bug #%s %s", $2, $3 }')
  echo "## O que espera pelo dono"; echo
  if [ -n "$itens" ]; then printf '%s\n' "$itens" | sed '/^$/d'; else echo "Nada."; fi
  echo
}

saida=$(
  espera
  [ -z "${PROJETO_PLANEJAMENTO:-}" ] || painel "Planejamento" "$PROJETO_PLANEJAMENTO"
  [ -z "${PROJETO_EXECUCAO:-}" ] || painel "Execução" "$PROJETO_EXECUCAO"
  [ -z "${PROJETO_BUGS:-}" ] || painel "Bugs" "$PROJETO_BUGS"
)
printf '%s\n' "$saida"
[ -z "${GITHUB_STEP_SUMMARY:-}" ] || printf '%s\n' "$saida" >> "$GITHUB_STEP_SUMMARY"
