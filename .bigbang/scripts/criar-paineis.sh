#!/usr/bin/env bash
# Creates the three boards of the process (spec 11.1) for a repository, or completes them (idempotent):
#   "<Produto> — Planejamento", "<Produto> — Execução", "<Produto> — Bugs"
# with the Status columns, the fields Sprint (single select), Épico (text), Prioridade and Versão (text), and the
# views Quadro, Tabela and Roadmap. Planejamento and Bugs lose the built-in "Auto-add sub-issues" workflow. Prints the numbers to put in bigbang.toml [paineis] and in the repository
# variables PROJETO_PLANEJAMENTO, PROJETO_EXECUCAO and PROJETO_BUGS.
#
# Requires gh with the "project" scope (gh auth refresh -s project).
# Usage: .bigbang/scripts/criar-paineis.sh OWNER/REPO "Nome do Produto" [--simular]
# shellcheck disable=SC2016  # $vars inside single quotes are GraphQL variables, not Bash
set -euo pipefail

REPO="${1:?Uso: $0 OWNER/REPO \"Nome do Produto\"}"
[[ "$REPO" =~ ^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$ ]] \
  || { echo "::error::informe o repositório como dono/repo (recebi '$REPO')" >&2; exit 2; }
PRODUTO="${2:?Uso: $0 OWNER/REPO \"Nome do Produto\"}"
OWNER="${REPO%%/*}"

# shellcheck source-path=SCRIPTDIR source=colunas.sh
source "$(dirname "$0")/colunas.sh"

numero_do_painel() { # existing board with this exact title, or empty
  gh project list --owner "$OWNER" --limit 200 --format json --jq '.projects[] | "\(.number)\t\(.title)"' \
    | awk -F'\t' -v t="$1" '$2 == t { print $1; exit }'
}

criar_painel() {
  local titulo="$1" numero
  numero=$(numero_do_painel "$titulo")
  if [ -z "$numero" ]; then
    numero=$(gh project create --owner "$OWNER" --title "$titulo" --format json --jq '.number')
    echo "  painel criado: #$numero $titulo" >&2
  else
    echo "  painel existente: #$numero $titulo" >&2
  fi
  gh project link "$numero" --owner "$OWNER" --repo "$REPO" >/dev/null 2>&1 || true
  echo "$numero"
}

campo() { # <numero> <nome> <tipo> [opcoes]
  local numero="$1" nome="$2" tipo="$3" opcoes="${4:-}"
  if gh project field-list "$numero" --owner "$OWNER" --format json --jq '.fields[].name' | grep -xF "$nome" >/dev/null; then
    return 0
  fi
  if [ -n "$opcoes" ]; then
    gh project field-create "$numero" --owner "$OWNER" --name "$nome" --data-type "$tipo" \
      --single-select-options "$opcoes" >/dev/null
  else
    gh project field-create "$numero" --owner "$OWNER" --name "$nome" --data-type "$tipo" >/dev/null
  fi
  echo "  campo '$nome' criado no painel $numero" >&2
}

colunas() { # <numero> "Nome:COR"... : replaces the Status options, keeping the ids of the ones that exist
  local numero="$1"; shift
  local campo_id existentes lista="" item nome cor id
  campo_id=$(gh project field-list "$numero" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .id')
  existentes=$(gh project field-list "$numero" --owner "$OWNER" --format json \
    --jq '.fields[] | select(.name=="Status") | .options[] | "\(.id)\t\(.name)"')
  for item in "$@"; do
    nome="${item%%:*}"; cor="${item##*:}"
    id=$(awk -F'\t' -v n="$nome" '$2 == n { print $1 }' <<<"$existentes")
    lista+="{${id:+id: \"$id\", }name: \"$nome\", color: $cor, description: \"\"}, "
  done
  gh api graphql -f query="mutation { updateProjectV2Field(input: { fieldId: \"$campo_id\",
    singleSelectOptions: [${lista%, }] }) { projectV2Field { ... on ProjectV2SingleSelectField { id } } } }" >/dev/null
}

visoes() { # <numero>: Quadro (board), Tabela and Roadmap
  local numero="$1" pid nomes primeira
  pid=$(gh project view "$numero" --owner "$OWNER" --format json --jq '.id')
  nomes=$(gh api graphql -f id="$pid" -f query='query($id:ID!){ node(id:$id){ ... on ProjectV2 {
    views(first:20){ nodes{ id name } } } } }' --jq '.data.node.views.nodes[] | "\(.id)\t\(.name)"')
  if ! grep -q $'\tQuadro$' <<<"$nomes"; then
    primeira=$(head -n 1 <<<"$nomes" | cut -f1)
    gh api graphql -f v="$primeira" -f query='mutation($v:ID!){ updateProjectV2View(input:{viewId:$v,
      name:"Quadro", layout:BOARD_LAYOUT}){ projectV2View{ id } } }' >/dev/null
  fi
  for visao in "Tabela:TABLE_LAYOUT" "Roadmap:ROADMAP_LAYOUT"; do
    grep -q $'\t'"${visao%%:*}"'$' <<<"$nomes" && continue
    gh api graphql -f p="$pid" -f n="${visao%%:*}" -f query="mutation(\$p:ID!,\$n:String!){ createProjectV2View(
      input:{projectId:\$p, name:\$n, layout:${visao##*:}}){ projectV2View{ id } } }" >/dev/null
  done
}

sem_auto_add_de_sub_issues() { # <numero>: Planejamento and Bugs only hold epics and bugs
  local numero="$1" pid id
  pid=$(gh project view "$numero" --owner "$OWNER" --format json --jq '.id')
  # The built-in "Auto-add sub-issues to project" workflow (on by default) would pull every task into this board.
  # The API cannot switch it off, only delete it.
  id=$(gh api graphql -f id="$pid" -f query='query($id:ID!){ node(id:$id){ ... on ProjectV2 {
    workflows(first:20){ nodes{ id name enabled } } } } }' \
    --jq '.data.node.workflows.nodes[] | select(.enabled and .name == "Auto-add sub-issues to project") | .id')
  [ -n "$id" ] || return 0
  gh api graphql -f id="$id" -f query='mutation($id:ID!){ deleteProjectV2Workflow(input:{workflowId:$id}){
    deletedWorkflowId } }' >/dev/null
  echo "  workflow 'Auto-add sub-issues to project' removido do painel $numero" >&2
}

montar() { # <titulo> <array de colunas> -> numero
  local titulo="$1"; shift
  local numero
  numero=$(criar_painel "$titulo")
  colunas "$numero" "$@"
  campo "$numero" Sprint SINGLE_SELECT "Sem sprint"
  campo "$numero" "Épico" TEXT
  campo "$numero" Prioridade SINGLE_SELECT "Alta,Média,Baixa"
  campo "$numero" "Versão" TEXT
  visoes "$numero"
  echo "$numero"
}

if [ "${3:-}" = --simular ]; then
  for titulo in "$PRODUTO — Planejamento" "$PRODUTO — Execução" "$PRODUTO — Bugs"; do
    numero=$(numero_do_painel "$titulo")
    if [ -n "$numero" ]; then echo "[simulado] completar o painel existente #$numero $titulo"
    else echo "[simulado] criar o painel \"$titulo\" e ligar a $REPO"; fi
  done
  echo "[simulado] colunas da seção 11.1, campos Sprint/Épico/Prioridade/Versão, visões Quadro/Tabela/Roadmap;"
  echo "[simulado] sem o workflow 'Auto-add sub-issues' no Planejamento e em Bugs"
  exit 0
fi

echo "== Planejamento ==" >&2
P=$(montar "$PRODUTO — Planejamento" "${COLUNAS_PLANEJAMENTO[@]}")
sem_auto_add_de_sub_issues "$P"
echo "== Execução ==" >&2
E=$(montar "$PRODUTO — Execução" "${COLUNAS_EXECUCAO[@]}")
echo "== Bugs ==" >&2
B=$(montar "$PRODUTO — Bugs" "${COLUNAS_BUGS[@]}")
sem_auto_add_de_sub_issues "$B"

cat <<FIM

Painéis prontos para $REPO: Planejamento #$P, Execução #$E, Bugs #$B.
No bigbang.toml, seção [paineis]: owner = "$OWNER", planejamento = $P, execucao = $E, bugs = $B
Variáveis do repositório:
  gh variable set PROJETO_OWNER --repo $REPO --body $OWNER
  gh variable set PROJETO_PLANEJAMENTO --repo $REPO --body $P
  gh variable set PROJETO_EXECUCAO --repo $REPO --body $E
  gh variable set PROJETO_BUGS --repo $REPO --body $B
Só pela interface do GitHub: agrupar a Tabela por Épico (opcional).
FIM
