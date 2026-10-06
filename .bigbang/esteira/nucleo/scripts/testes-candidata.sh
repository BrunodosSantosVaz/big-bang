#!/usr/bin/env bash
# Flash candidates reuse the complete/selected test execution of CI at the EXACT candidate SHA.
# Default mode keeps the existing candidate test execution. No success at another commit can authorize a build.
set -euo pipefail
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
modo=$("${BB_CMD[@]}" config get projeto.modo)
if [ "$modo" != flash ]; then
  bash .bigbang/esteira/nucleo/scripts/comando.sh testes
  bash .bigbang/esteira/nucleo/scripts/comando.sh testes_aceite
  exit 0
fi
sha="${GITHUB_SHA:?}"; repo="${GITHUB_REPOSITORY:?}"
tentativas="${BB_CHECK_TENTATIVAS:-60}"
[[ "$tentativas" =~ ^[1-9][0-9]*$ ]] || exit 2
for ((i=0; i<tentativas; i++)); do
  estado=$(gh api --paginate "repos/$repo/commits/$sha/check-runs?per_page=100" \
    --jq '.check_runs[] | select(.name == "check") | [.id // 0, .status, .conclusion // ""] | @tsv' \
    | sort -rn | sed -n '1p')
  IFS=$'\t' read -r _ status resultado <<<"$estado"
  if [ "$status" = completed ]; then
    if [ "$resultado" = success ]; then
      echo "CI de $sha reutilizada: testes validados; a candidata não repete a mesma rodada."
      exit 0
    fi
    echo "::error::CI de $sha terminou com $resultado; candidata recusada."; exit 1
  fi
  if [ "$i" -lt "$((tentativas - 1))" ]; then sleep 10; fi
done
echo "::error::CI verde ausente para $sha; candidata recusada."; exit 1
