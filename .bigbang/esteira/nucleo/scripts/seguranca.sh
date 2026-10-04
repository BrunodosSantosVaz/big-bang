#!/usr/bin/env bash
# Job `seguranca` (spec 14.2 and 15.5): fails on a secret in the code, the history or the built front bundle; on an
# Opengrep (OWASP rules) or Bandit finding; on a high or critical vulnerability in a dependency (OSV-Scanner); on a
# table without RLS when banco_no_navegador = true. Every tool is pinned by version and SHA-256 (SEG-18).
# An exception is never "turn the scan off": it is an ADR plus the tool's own ignore entry (docs/padroes/excecoes.md).
# Environment: EVENTO (pull_request|push|schedule), BASE_SHA and HEAD_SHA (pull_request), RUNNER_TEMP, BB.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"

GITLEAKS_VERSION=8.30.1
GITLEAKS_SHA256=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
OPENGREP_VERSION=1.30.0
OPENGREP_SHA256=35779bdd72e92129c8df2a77f0c55e8c08356801ea92591ef32108d6b28d564c
OPENGREP_RULES_COMMIT=f1d2b562b414783763fd02a6ed2736eaed622efa
OSV_VERSION=2.6.0
OSV_SHA256=ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108
BANDIT_VERSION=1.9.4

ferramentas="${RUNNER_TEMP:-$(mktemp -d)}/bb-ferramentas"
mkdir -p "$ferramentas"
falhas=0
arquivos() { git ls-files "$@" | { grep -vE '^(\.bigbang|tests|node_modules)/' || true; }; }  # no early-exit pipes
falha() { echo "::error::$*"; falhas=$((falhas + 1)); }

baixar() { # <url> <sha256> <destino>
  curl -fsSL -o "$3" "$1"
  echo "$2  $3" | sha256sum -c - >/dev/null || { echo "::error::hash inesperado em $1"; exit 1; }
}

echo "== Gitleaks (segredos no código e no histórico)"
baixar "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
  "$GITLEAKS_SHA256" "$ferramentas/gitleaks.tar.gz"
tar -xzf "$ferramentas/gitleaks.tar.gz" -C "$ferramentas" gitleaks
if [ "${EVENTO:-push}" = pull_request ] && [ -n "${BASE_SHA:-}" ]; then
  opcoes=(--log-opts="${BASE_SHA}..${HEAD_SHA:-HEAD}")
else
  opcoes=()  # push and the weekly run: the whole history
fi
"$ferramentas/gitleaks" git --redact --no-banner --exit-code 1 "${opcoes[@]}" . || falha "Gitleaks achou segredo (SEG-IA-04): revogue e troque o segredo; apagar o commit não basta"

echo "== Opengrep (regras OWASP da comunidade, commit fixo)"
baixar "https://github.com/opengrep/opengrep/releases/download/v${OPENGREP_VERSION}/opengrep_manylinux_x86" \
  "$OPENGREP_SHA256" "$ferramentas/opengrep"
chmod +x "$ferramentas/opengrep"
regras="$ferramentas/regras"
git init -q "$regras" && git -C "$regras" fetch -q --depth 1 https://github.com/opengrep/opengrep-rules "$OPENGREP_RULES_COMMIT" \
  && git -C "$regras" checkout -q FETCH_HEAD
configs=()
for par in "py:python" "js:javascript" "ts:typescript" "go:go" "java:java" "kt:kotlin" "php:php" "cs:csharp" "rb:ruby" "rs:rust"; do
  ext="${par%%:*}"; linguagem="${par##*:}"
  if [ -n "$(arquivos "*.$ext")" ]; then configs+=(--config "$regras/$linguagem"); fi
done
if [ "${#configs[@]}" -gt 0 ]; then
  "$ferramentas/opengrep" scan "${configs[@]}" --severity ERROR --error --quiet \
    --exclude .bigbang --exclude tests --exclude node_modules . || falha "Opengrep achou falha de segurança (OWASP)"
else
  echo "Nenhum código numa linguagem com regras do Opengrep."
fi

echo "== Bandit (Python)"
if [ -n "$(arquivos '*.py')" ]; then
  python3 -m venv "$ferramentas/venv" && "$ferramentas/venv/bin/python" -m pip install -q "bandit==${BANDIT_VERSION}"
  mapfile -t pastas < <(arquivos '*.py' | cut -d/ -f1 | sort -u)
  saida_bandit=$("$ferramentas/venv/bin/bandit" -q -r -ll "${pastas[@]}" 2>&1) && rc_bandit=0 || rc_bandit=$?
  printf '%s\n' "$saida_bandit"
  [ "$rc_bandit" -eq 0 ] || falha "Bandit achou falha de severidade média ou maior"
  # an analysis that crashed is not a pass: a file Bandit could not read was not checked
  if grep -F "Exception occurred" >/dev/null <<<"$saida_bandit"; then falha "Bandit não conseguiu analisar arquivos"; fi
else
  echo "Sem código Python."
fi

echo "== OSV-Scanner (vulnerabilidades conhecidas nas dependências)"
baixar "https://github.com/google/osv-scanner/releases/download/v${OSV_VERSION}/osv-scanner_linux_amd64" \
  "$OSV_SHA256" "$ferramentas/osv-scanner"
chmod +x "$ferramentas/osv-scanner"
relatorio="$ferramentas/osv.json"
"$ferramentas/osv-scanner" scan source -r --format json . >"$relatorio" 2>/dev/null || true  # exit 1 = findings
if ! msg=$("${BB_CMD[@]}" esteira osv-avaliar <"$relatorio"); then
  while IFS= read -r linha; do falha "OSV: $linha"; done <<<"$msg"
fi

echo "== Segredo no pacote do front (SEG-IA-04)"
build=$("${BB_CMD[@]}" config get comandos.build)
if [ -n "$build" ]; then
  bash .bigbang/esteira/nucleo/scripts/comando.sh instalar
  bash -c "$build"
  for saida in dist build out .next public/build; do
    if [ -d "$saida" ]; then
      "$ferramentas/gitleaks" dir --redact --no-banner --exit-code 1 "$saida" || falha "segredo no pacote construído ($saida)"
    fi
  done
else
  echo "comandos.build vazio: sem pacote para conferir."
fi

echo "== RLS (SEG-IA-01)"
"${BB_CMD[@]}" esteira rls || falha "tabela sem RLS com banco_no_navegador = true"

[ "$falhas" -eq 0 ] || { echo "Segurança REPROVADA: $falhas problema(s)."; exit 1; }
echo "Segurança aprovada."
