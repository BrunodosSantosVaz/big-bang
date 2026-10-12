#!/usr/bin/env bash
# Adaptador AWS S3 + CloudFront (site estático via OIDC) [BETA]
# Aviso: Não testado em conta AWS real. Relatos e melhorias: https://github.com/BrunodosSantosVaz/big-bang/issues/316
set -euo pipefail

echo "::warning::Adaptador AWS S3 + CloudFront em estágio BETA (não testado em conta AWS real). Relate resultados na issue #316: https://github.com/BrunodosSantosVaz/big-bang/issues/316"

read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
operacao="${1:?Uso: alvo.sh publicar|migrar|saude|voltar <ambiente> [manifesto|versao]}"
ambiente="${2:?informe o ambiente (staging ou producao)}"
[[ "$ambiente" =~ ^(staging|producao)$ ]] || { echo "::error::ambiente '$ambiente' inválido"; exit 2; }

case "$operacao" in
  migrar)
    echo "Alvo AWS (S3 + CloudFront): hospedagem estática não possui migrações de banco de dados."
    exit 0
    ;;

  publicar)
    AWS_REGION="${AWS_REGION:?defina a variável AWS_REGION}"
    AWS_S3_BUCKET="${AWS_S3_BUCKET:?defina a variável AWS_S3_BUCKET}"
    AWS_CLOUDFRONT_DISTRIBUTION_ID="${AWS_CLOUDFRONT_DISTRIBUTION_ID:?defina a variável AWS_CLOUDFRONT_DISTRIBUTION_ID}"

    artefato_entrada="${3:?informe a pasta ou manifesto do artefato estático}"
    origem="$artefato_entrada"
    if [ -f "$artefato_entrada" ]; then
      origem="$(dirname "$artefato_entrada")"
    fi

    echo "Sincronizando arquivos com s3://${AWS_S3_BUCKET} na região ${AWS_REGION}..."
    if [ "${AWS_SIMULAR:-false}" = true ] || ! command -v aws >/dev/null 2>&1; then
      echo "[simulado] aws s3 sync \"$origem\" \"s3://${AWS_S3_BUCKET}\" --delete --region \"${AWS_REGION}\""
      echo "[simulado] aws cloudfront create-invalidation --distribution-id \"${AWS_CLOUDFRONT_DISTRIBUTION_ID}\" --paths \"/*\""
    else
      aws s3 sync "$origem" "s3://${AWS_S3_BUCKET}" --delete --region "${AWS_REGION}"
      echo "Criando invalidação no CloudFront (${AWS_CLOUDFRONT_DISTRIBUTION_ID})..."
      aws cloudfront create-invalidation --distribution-id "${AWS_CLOUDFRONT_DISTRIBUTION_ID}" --paths "/*"
    fi
    echo "Publicação no S3 + CloudFront concluída."
    ;;

  saude)
    url=$("${BB_CMD[@]}" config get "deploy.url_$ambiente")
    caminho=$("${BB_CMD[@]}" config get deploy.caminho_saude)
    tentativas="${SAUDE_TENTATIVAS:-24}"; intervalo="${SAUDE_INTERVALO:-5}"
    [[ "$tentativas" =~ ^[1-9][0-9]*$ ]] && [[ "$intervalo" =~ ^[0-9]+$ ]] || exit 2
    for i in $(seq 1 "$tentativas"); do
      if curl -fsS -o /dev/null --max-time 5 "$url$caminho"; then
        echo "$ambiente saudável: $url$caminho"
        exit 0
      fi
      [ "$i" -ge "$tentativas" ] || sleep "$intervalo"
    done
    echo '::error::AWS CloudFront/S3 não respondeu à saúde no prazo.'; exit 1
    ;;

  voltar)
    versao="${3:?informe a versão (vX.Y.Z)}"
    [[ "$versao" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 2
    echo "Executando rollback estático para a versão $versao..."
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    if command -v gh >/dev/null 2>&1 && [ -n "${GITHUB_REPOSITORY:-}" ]; then
      gh release download "$versao" --repo "$GITHUB_REPOSITORY" --dir "$tmp" || true
    fi
    exec bash "$0" publicar "$ambiente" "$tmp"
    ;;

  *)
    echo "::error::Operação AWS inválida: $operacao. Use publicar, migrar, saude ou voltar."
    exit 2
    ;;
esac
