#!/usr/bin/env bash
# Runs one command of the stack from bigbang.toml [comandos] (defined in F2), e.g. `comando.sh lint`.
# An empty command is skipped with a notice (before F2 there is no stack yet); a failing one fails the step.
set -euo pipefail
chave="${1:?Uso: comando.sh <instalar|lint|tipos|testes|testes_aceite|arquitetura|cobertura|build>}"
read -r -a BB <<<"${BB:-python3 .bigbang/bin/bb.py}"
comando=$("${BB[@]}" config get "comandos.$chave")
if [ -z "$comando" ]; then
  echo "::notice::comandos.$chave vazio no bigbang.toml: etapa pulada (defina na Fundação F2)."
  exit 0
fi
echo "+ $comando"
bash -c "$comando"
