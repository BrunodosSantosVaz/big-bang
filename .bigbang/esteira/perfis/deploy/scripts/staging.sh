#!/usr/bin/env bash
# Deploy candidate, step 3 (spec 14.4): the candidate goes to staging exactly as it will go to production —
# migration with the new image first, then the switch, the health check, the smoke tests (deploy.smoke, with
# BB_URL pointing at staging) and a baseline ZAP scan (image pinned by digest; only FAIL rules fail).
# Environment: IMAGEM (imagem@sha256:…), the target's variables and secrets for `staging`, BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
ZAP_IMAGEM="ghcr.io/zaproxy/zaproxy@sha256:781a2bdaea47324e7bab583e2263f21d257b0aee61ed51521a5be45f5f5081ef"  # 2.17.0
imagem="${IMAGEM:?}"
alvo=".bigbang/esteira/perfis/deploy/alvos/$("${BB_CMD[@]}" config get entrega.alvo)/scripts/alvo.sh"
url=$("${BB_CMD[@]}" config get deploy.url_staging)
formato=$("${BB_CMD[@]}" config get deploy.artefato)

if [[ "$formato" == imagem ]]; then
  manifesto="$imagem"
else
  manifesto="candidata/manifesto.json"
  PYTHONPATH=.bigbang python3 -m bb.artifacts verify "$manifesto"
  manifesto_sha=$(sha256sum "$manifesto" | cut -d' ' -f1)
  [[ "$imagem" == "sha256:$manifesto_sha" ]] \
    || { echo "::error::identidade da candidata diverge do manifesto de staging"; exit 1; }
fi
bash "$alvo" migrar staging "$manifesto"
bash "$alvo" publicar staging "$manifesto"
bash "$alvo" saude staging
smoke=$("${BB_CMD[@]}" config get deploy.smoke)
echo "+ $smoke (BB_URL=$url)"
BB_URL="$url" bash -c "$smoke"
docker run --rm "$ZAP_IMAGEM" zap-baseline.py -t "$url" -I \
  || { echo "::error::ZAP baseline reprovou o staging (regra FAIL); veja o log acima"; exit 1; }
echo "Staging pronto para homologar: $imagem em $url"
