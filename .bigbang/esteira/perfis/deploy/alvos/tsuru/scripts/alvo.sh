#!/usr/bin/env bash
# Tsuru apps/jobs are provisioned explicitly; this adapter imports immutable images and never creates a server.
set -euo pipefail
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
operacao="${1:?publicar|migrar|saude|voltar <ambiente> [imagem|versao]}"
ambiente="${2:?staging|producao}"
[[ "$ambiente" =~ ^(staging|producao)$ ]] || exit 2
case "$operacao" in
  publicar|migrar)
    python3 .bigbang/esteira/perfis/deploy/alvos/tsuru/scripts/tsuru.py "$operacao" "$ambiente" "${3:?imagem por digest}"
    ;;
  saude)
    url=$("${BB_CMD[@]}" config get "deploy.url_$ambiente")
    caminho=$("${BB_CMD[@]}" config get deploy.caminho_saude)
    tentativas="${SAUDE_TENTATIVAS:-24}"; intervalo="${SAUDE_INTERVALO:-5}"
    [[ "$tentativas" =~ ^[1-9][0-9]*$ ]] && [[ "$intervalo" =~ ^[0-9]+$ ]] || exit 2
    for i in $(seq 1 "$tentativas"); do
      if curl -fsS -o /dev/null --max-time 5 "$url$caminho"; then echo "$ambiente saudável: $url$caminho"; exit 0; fi
      [ "$i" -ge "$tentativas" ] || sleep "$intervalo"
    done
    echo '::error::Tsuru não respondeu à saúde no prazo.'; exit 1
    ;;
  voltar)
    versao="${3:?vX.Y.Z}"
    [[ "$versao" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 2
    imagem=$(gh release download "$versao" --repo "${GITHUB_REPOSITORY:?}" --pattern imagem.txt --output - | tr -d '\r\n')
    # The same release digest is reimported; migration is deliberately never executed on rollback.
    exec bash "$0" publicar "$ambiente" "$imagem"
    ;;
  *) echo '::error::Operação Tsuru inválida.'; exit 2 ;;
esac
