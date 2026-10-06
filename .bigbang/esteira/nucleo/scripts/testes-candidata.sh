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
  estado=$(gh run list --repo "$repo" --workflow bb-ci.yml --commit "$sha" --event push --limit 100 \
    --json databaseId,status,conclusion,headSha \
    --jq '.[] | [.databaseId, .status, .conclusion // "", .headSha] | @tsv' \
    | sort -rn | sed -n '1p')
  IFS=$'\t' read -r _ status resultado confirmado <<<"$estado"
  if [ -n "$confirmado" ] && [ "$confirmado" != "$sha" ]; then
    echo "::error::CI retornou outro commit; candidata recusada."; exit 1
  fi
  if [ "$status" = completed ]; then
    if [ "$resultado" = success ] && [ "$confirmado" = "$sha" ]; then
      echo "CI de $sha reutilizada: testes validados; a candidata não repete a mesma rodada."
      exit 0
    fi
    echo "::error::CI de $sha terminou com $resultado; candidata recusada."; exit 1
  fi
  if [ "$i" -lt "$((tentativas - 1))" ]; then sleep 10; fi
done
echo "::error::CI verde ausente para $sha; candidata recusada."; exit 1
