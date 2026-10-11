#!/usr/bin/env bash
set -euo pipefail

read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
operacao="${1:?publicar|migrar|saude|voltar <ambiente> [manifesto|versao]}"
ambiente="${2:?staging|producao}"
[[ "$ambiente" =~ ^(staging|producao)$ ]] || { echo "::error::ambiente inválido"; exit 2; }

case "$operacao" in
  publicar) chave=deploy.script_publicar ;;
  migrar) chave=deploy.script_migrar ;;
  saude) chave=deploy.script_saude ;;
  voltar) chave=deploy.script_voltar ;;
  *) echo "::error::operação personalizada inválida"; exit 2 ;;
esac

script=$("${BB_CMD[@]}" config get "$chave")
[[ "$script" =~ ^[A-Za-z0-9_./-]+\.sh$ ]] || { echo "::error::script do alvo personalizado inválido"; exit 2; }
case "/$script/" in
  *"/../"*|*"/./"*|*"/.bigbang/"*) echo "::error::script deve ficar fora de .bigbang e sem travessia"; exit 2 ;;
esac
[[ -f "$script" && -s "$script" ]] || { echo "::error::script obrigatório ausente ou vazio: $script"; exit 1; }
raiz=$(pwd -P)
script_real=$(realpath -e -- "$script")
[[ "$script_real" == "$raiz/"* && "$script_real" != "$raiz/.bigbang/"* ]] \
  || { echo "::error::script fora da raiz do projeto"; exit 2; }

project_environment=("PATH=${PATH:-/usr/bin:/bin}")
for variable in LANG LC_ALL TZ TMPDIR TMP TEMP; do
  if [[ -n "${!variable:-}" ]]; then
    project_environment+=("$variable=${!variable}")
  fi
done
run_project_script() {
  env -i "${project_environment[@]}" bash "$@"
}

if [[ "$operacao" == saude ]]; then
  exec env -i "${project_environment[@]}" bash "$script" "$ambiente"
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
manifesto="$tmp/imagem.txt"
if [[ "$operacao" == voltar ]]; then
  versao="${3:?informe a versão publicada}"
  [[ "$versao" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::versão inválida"; exit 2; }
  gh release download "$versao" --repo "${GITHUB_REPOSITORY:?}" --pattern imagem.txt --output "$manifesto"
else
  printf '%s\n' "${3:?informe o manifesto imutável}" | tr ',' '\n' >"$manifesto"
fi

configurados=$("${BB_CMD[@]}" config get deploy.servicos)
declare -A esperados=() recebidos=()
while IFS= read -r item; do
  nome="${item%%=*}"
  [[ -n "$nome" ]] || { echo "::error::serviço inválido em deploy.servicos"; exit 2; }
  esperados["$nome"]=1
done <<<"$configurados"

normalizado="$tmp/manifesto-validado.txt"
while IFS= read -r item || [[ -n "$item" ]]; do
  item="${item//$'\r'/}"
  [[ -n "$item" ]] || continue
  if [[ "$item" == *=* ]]; then
    nome="${item%%=*}"
    imagem="${item#*=}"
  elif [[ "${#esperados[@]}" == 1 ]]; then
    nome="${!esperados[*]}"
    imagem="$item"
  else
    echo "::error::manifesto exige serviço=imagem@sha256:… para cada serviço"; exit 2
  fi
  [[ "$nome" =~ ^[a-z][a-z0-9_-]*$ ]] || { echo "::error::nome de serviço inválido no manifesto"; exit 2; }
  [[ -n "${esperados[$nome]:-}" ]] || { echo "::error::serviço desconhecido no manifesto: $nome"; exit 2; }
  [[ -z "${recebidos[$nome]:-}" ]] || { echo "::error::serviço duplicado no manifesto: $nome"; exit 2; }
  [[ "$imagem" =~ ^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}$ ]] \
    || { echo "::error::identidade do manifesto não é imutável: $imagem"; exit 2; }
  recebidos["$nome"]=1
  printf '%s=%s\n' "$nome" "$imagem" >>"$normalizado"
done <"$manifesto"
[[ "${#recebidos[@]}" == "${#esperados[@]}" ]] \
  || { echo "::error::manifesto incompleto para deploy.servicos"; exit 2; }

if [[ "$operacao" == voltar ]]; then
  if run_project_script "$script" "$ambiente" "$normalizado" "$versao"; then status=0; else status=$?; fi
else
  if run_project_script "$script" "$ambiente" "$normalizado"; then status=0; else status=$?; fi
fi
exit "$status"
