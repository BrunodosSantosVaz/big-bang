#!/usr/bin/env bash
# Own-framework recovery: trusted main, exact published tag, synchronized content and successful push CI.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

R="${GITHUB_REPOSITORY:?}"; SIMULAR="${SIMULAR:-false}"
[ "$R" = BrunodosSantosVaz/big-bang ] || { echo "::error::faxina-framework só roda no próprio Big Bang"; exit 1; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
aguardar() { echo "Faxina aguardando: $*. Nenhuma branch apagada."; exit 0; }

git fetch -q --prune origin "+refs/heads/*:refs/remotes/origin/*" --tags
main=$(git rev-parse origin/main); develop=$(git rev-parse origin/develop)
versao=$(git show origin/main:.bigbang/VERSION | tr -d '[:space:]')
[[ "$versao" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::VERSION inválido"; exit 1; }
tag="v$versao"
publicado=$(git rev-parse -q --verify "refs/tags/$tag^{commit}" || true)
[ "$publicado" = "$main" ] || aguardar "a ponta da main ainda não é a tag $tag"
[ "$(git rev-parse 'origin/main^{tree}')" = "$(git rev-parse 'origin/develop^{tree}')" ] \
  || aguardar "main e develop ainda têm conteúdo diferente"
git merge-base --is-ancestor "$main" "$develop" || aguardar "main ainda não foi sincronizada na develop"

# Missing publication is normal while the release workflow is creating its assets. API failures delete nothing.
release=$(gh api "repos/$R/releases/tags/$tag" --jq \
  '[.tag_name, .draft, .prerelease, ([.assets[].name] | sort)] | @json' 2>/dev/null || true)
if ! jq -e --arg tag "$tag" --arg pacote "bigbang-v$versao.tar.gz" \
  '.[0] == $tag and .[1] == false and .[2] == false and (.[3] | index($pacote)) != null
   and (.[3] | index($pacote + ".sha256")) != null' <<<"$release" >/dev/null 2>&1; then
  aguardar "release estável $tag e seus dois arquivos ainda não estão disponíveis"
fi
for branch in main develop; do
  sha="$main"; [ "$branch" = main ] || sha="$develop"
  ci=$(gh api "repos/$R/actions/workflows/bb-framework-ci.yml/runs?branch=$branch&head_sha=$sha&event=push&per_page=1" \
    --jq '.workflow_runs[0] | [.status, .conclusion, .head_sha, .head_branch, .event] | @tsv')
  [ "$ci" = "$(printf 'completed\tsuccess\t%s\t%s\tpush' "$sha" "$branch")" ] \
    || aguardar "CI completa do SHA exato da $branch ainda não passou"
done

echo "Portões da faxina aprovados: $tag publicada, main/develop sincronizadas e CI verde."
export SIMULAR FAXINA_EXIGIR_LIMPA=true
bash "$AQUI/faxina.sh"
