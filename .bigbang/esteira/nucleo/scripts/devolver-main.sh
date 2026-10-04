#!/usr/bin/env bash
# Returns main to develop and to every open epico/* after a publication (spec 11.5), so the epics in progress build
# on what is in production. Idempotent (a branch that already contains main is skipped).
#   develop conflict -> error (resolve by hand in a PR); epico/* conflict -> label `conflito` on the epic and a
#   comment: an AI resolves it in a sync/<n>-<slug> PR.
# Environment: SIMULAR, GITHUB_REPOSITORY, GH_TOKEN (PROJETO_TOKEN, to push), TAG (optional, for the messages).
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

AQUI="$(cd "$(dirname "$0")" && pwd)"
R="${GITHUB_REPOSITORY:?}"; SIMULAR="${SIMULAR:-false}"
git fetch -q origin "+refs/heads/*:refs/remotes/origin/*"
falhou=0

devolver() { # <branch>
  local destino="$1" saida rc=0
  if git merge-base --is-ancestor origin/main "origin/$destino"; then echo "$destino já contém a main."; return 0; fi
  if [ "$SIMULAR" = true ]; then echo "[simulado] devolver a main para $destino"; return 0; fi
  saida=$(bash "$AQUI/git-mesclar.sh" "$destino" "$destino" "main${TAG:+ ($TAG)}=refs/heads/main") || rc=$?
  if [ "$rc" -eq 0 ]; then
    git push -q origin "$destino"; echo "main devolvida para $destino."
  elif [ "$rc" -eq 3 ]; then
    return 3
  else
    echo "$saida"; return "$rc"
  fi
}

if ! devolver develop; then
  echo "::error::Conflito ao devolver a main para a develop: resolva num PR (a develop não recebe artefato não publicado)."
  falhou=1
fi
for ref in $(git for-each-ref --format='%(refname:strip=3)' 'refs/remotes/origin/epico/*'); do
  rc=0; devolver "$ref" || rc=$?
  if [ "$rc" -eq 3 ]; then
    if [[ "$ref" =~ ^epico/([0-9]+)-(.+)$ ]]; then
      n="${BASH_REMATCH[1]}"
      gh issue edit "$n" --repo "$R" --add-label conflito >/dev/null
      gh issue comment "$n" --repo "$R" --body "A \`main\` não entrou sozinha em \`$ref\` (conflito). Uma IA resolve num PR \`sync/$n-${BASH_REMATCH[2]}\` → \`$ref\`." >/dev/null
    fi
    echo "::warning::Conflito ao devolver a main para $ref: épico marcado com conflito."
  elif [ "$rc" -ne 0 ]; then
    falhou=1
  fi
done
exit "$falhou"
