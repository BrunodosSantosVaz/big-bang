#!/usr/bin/env bash
# Runs project-owned production scripts in a workflow step that receives no publication credentials.
set -euo pipefail

rc="${RC_TAG:?}"
tag="${TAG:?}"
alvo_sha="${TARGET_SHA:?}"
imagem="${IMAGEM:?}"
[[ "$rc" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$ ]] || { echo "::error::candidata inválida"; exit 2; }
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::versão inválida"; exit 2; }
[[ "$alvo_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "::error::SHA de destino inválido"; exit 2; }
[[ "$imagem" != *$'\n'* && -n "$imagem" ]] || { echo "::error::manifesto inválido"; exit 2; }

alvo=".bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh"
bash "$alvo" migrar producao "$imagem"
bash "$alvo" publicar producao "$imagem"
bash "$alvo" saude producao
