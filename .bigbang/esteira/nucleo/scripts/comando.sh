#!/usr/bin/env bash
# Runs one command of the stack from bigbang.toml [comandos] (defined in F2), e.g. `comando.sh lint`.
# An empty command is skipped with a notice (before F2 there is no stack yet); so is every command while NONE of
# entrega.caminhos_artefato exists: the artifact code only reaches develop through the walking skeleton epic
# (invariant 11.5), after the Foundation PR that installs the pipeline. A failing command fails the step.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
chave="${1:?Uso: comando.sh <instalar|lint|tipos|testes|testes_aceite|arquitetura|cobertura|build>}"
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
comando=$("${BB_CMD[@]}" config get "comandos.$chave")
if [ -z "$comando" ]; then
  echo "::notice::comandos.$chave vazio no bigbang.toml: etapa pulada (defina na Fundação F2)."
  exit 0
fi
existe=""
while IFS= read -r caminho; do
  [ -n "$caminho" ] && [ -e "${caminho%/}" ] && { existe="$caminho"; break; }
done < <("${BB_CMD[@]}" config get entrega.caminhos_artefato)
if [ -z "$existe" ]; then
  echo "::notice::nenhum caminho do artefato (entrega.caminhos_artefato) existe ainda: comandos.$chave pulado; o código chega pelo épico Esqueleto andante."
  exit 0
fi
echo "+ $comando"
bash -c "$comando"
