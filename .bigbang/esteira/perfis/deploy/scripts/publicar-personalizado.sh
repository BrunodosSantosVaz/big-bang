#!/usr/bin/env bash
# Runs project-owned production scripts in a workflow step that receives no publication credentials.
set -euo pipefail

rc="${RC_TAG:?}"
tag="${TAG:?}"
alvo_sha="${TARGET_SHA:?}"
[[ "$rc" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$ ]] || { echo "::error::candidata inválida"; exit 2; }
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "::error::versão inválida"; exit 2; }
[[ "$alvo_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "::error::SHA de destino inválido"; exit 2; }

alvo=".bigbang/esteira/perfis/deploy/alvos/personalizado/scripts/alvo.sh"
if [[ -n "${MANIFESTO:-}" ]]; then
  [[ -f "$MANIFESTO" && ! -L "$MANIFESTO" ]] || { echo "::error::manifesto ausente ou inseguro"; exit 2; }
  bash "$alvo" migrar producao "$MANIFESTO"
  bash "$alvo" publicar producao "$MANIFESTO"
else
  imagem="${IMAGEM:?}"
  [[ "$imagem" != *$'\n'* ]] || { echo "::error::manifesto inválido"; exit 2; }
  bash "$alvo" migrar producao "$imagem"
  bash "$alvo" publicar producao "$imagem"
fi
bash "$alvo" saude producao
