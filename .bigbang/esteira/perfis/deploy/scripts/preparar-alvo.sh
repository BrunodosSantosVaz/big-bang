#!/usr/bin/env bash
# Runs approved network preparation and an installed target's optional tool setup only during a real deploy.
set -euo pipefail
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
rede=$("${BB_CMD[@]}" config get deploy.preparar_rede)
[ -z "$rede" ] || bash -c "$rede"
alvo=$("${BB_CMD[@]}" config get entrega.alvo)
preparo=".bigbang/esteira/perfis/deploy/alvos/$alvo/scripts/preparar.sh"
[ ! -f "$preparo" ] || bash "$preparo"
