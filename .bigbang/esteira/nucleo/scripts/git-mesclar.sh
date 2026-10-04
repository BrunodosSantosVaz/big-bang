#!/usr/bin/env bash
# Merges, ONE BY ONE and with a merge commit (--no-ff), refs of origin into a target branch (ported from CNABLens).
# Usage: git-mesclar.sh DESTINO BASE "rotulo=refspec" ["rotulo=refspec" ...]
#   DESTINO: branch that receives (created from origin/BASE when it does not exist on origin)
# Output per item: MESCLADO <rotulo> | JA_INCLUIDO <rotulo>. On conflict: aborts, prints "CONFLITO <rotulo>" and
# exits 3, leaving the local branch exactly as before the item. This script never pushes.
set -euo pipefail

destino="${1:?destino}"; base="${2:?base}"; shift 2
git config user.name >/dev/null 2>&1 || git config user.name "github-actions[bot]"
git config user.email >/dev/null 2>&1 || git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git fetch -q origin "+refs/heads/${base}:refs/remotes/origin/${base}"
if git fetch -q origin "+refs/heads/${destino}:refs/remotes/origin/${destino}" 2>/dev/null; then
  git checkout -q -B "$destino" "origin/${destino}"
else
  git checkout -q -B "$destino" "origin/${base}"
fi

for item in "$@"; do
  rotulo="${item%%=*}"; refspec="${item#*=}"
  git fetch -q origin "$refspec"
  sha=$(git rev-parse FETCH_HEAD)
  if git merge-base --is-ancestor "$sha" HEAD; then echo "JA_INCLUIDO $rotulo"; continue; fi
  if git merge --no-ff --no-edit -m "Merge $rotulo into $destino" "$sha" >/dev/null 2>&1; then
    echo "MESCLADO $rotulo"
  else
    git merge --abort >/dev/null 2>&1 || true
    echo "CONFLITO $rotulo"
    exit 3
  fi
done
