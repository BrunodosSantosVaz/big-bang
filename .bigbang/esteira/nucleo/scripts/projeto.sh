#!/usr/bin/env bash
# Cards of the three boards (GitHub Projects v2 of the user). Ported from CNABLens, without external jq:
# every filter runs inside gh (--jq) and lists are split as TSV in Bash.
#
# Subcommands (<painel> is the project NUMBER):
#   projeto.sh mover   <painel> <issue> "<Status>" ["<De1|De2>"]
#       Adds the issue to the board (if missing) and sets the Status. With the 4th argument, only moves when the
#       CURRENT Status is in the list ("-" = no status), so a card never goes backwards by accident.
#   projeto.sh cartoes <painel> "<Status>"      numbers of this repository's issues in that column
#   projeto.sh colunas <painel>                 Status options, in board order
#   projeto.sh quadro  <painel>                 open issues: <Status>\t<n>\t<title>\t<Sprint>  (read only)
#   projeto.sh remover <painel> <issue>
#   projeto.sh texto   <painel> <issue> "<Campo>" "<valor>"   sets a text field (Épico, Versão)
#   projeto.sh sprints <painel>                 options of the single-select "Sprint" field
#   projeto.sh sprint-criar <painel> "<Sprint N · AAAA-MM-DD>"  adds the option keeping the existing ones
#   projeto.sh sprint-renomear <painel> "<de>" "<para>"     keeps the option id (cards keep their Sprint)
#   projeto.sh sprint  <painel> <issue> "<titulo>"
#   projeto.sh sprint-de <painel> <issue>       Sprint of the issue (empty if none)
#
# Environment: GH_TOKEN (scope project), PROJETO_OWNER, GITHUB_REPOSITORY. DRY_RUN=1 only prints the writes.
# shellcheck disable=SC2016  # $vars inside single quotes are GraphQL variables, not Bash
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

: "${PROJETO_OWNER:?defina PROJETO_OWNER}"
: "${GITHUB_REPOSITORY:?defina GITHUB_REPOSITORY}"

# Board ids and field options do not change during a run: with BB_CACHE_DIR set (the orchestrating scripts set it
# to a fresh temp dir), they are fetched once. Saves GraphQL points (5000/hour, shared by every workflow).
cache() { # <chave> <comando...>: prints the cached output, running the command once
  local chave="$1"; shift
  if [ -z "${BB_CACHE_DIR:-}" ]; then "$@"; return; fi
  local arquivo="$BB_CACHE_DIR/$chave"
  if [ ! -s "$arquivo" ]; then "$@" >"$arquivo.tmp" && mv "$arquivo.tmp" "$arquivo"; fi
  cat "$arquivo"
}
limpar_cache() { [ -z "${BB_CACHE_DIR:-}" ] || rm -f "$BB_CACHE_DIR"/opcoes-"$1"-* "$BB_CACHE_DIR"/campo-"$1"-*; }

OWNER_QUERY='query($o:String!,$n:Int!){ repositoryOwner(login:$o){ ... on ProjectV2Owner { projectV2(number:$n){'

projeto_id() { cache "id-$1" _projeto_id "$1"; }
_projeto_id() {
  gh api graphql -F n="$1" -f o="$PROJETO_OWNER" -f query="$OWNER_QUERY id } } } }" \
    --jq '.data.repositoryOwner.projectV2.id'
}

# <field id>\t<option id>\t<option name> for every option of a single-select field
opcoes() { cache "opcoes-$1-$(printf '%s' "$2" | cksum | cut -d' ' -f1)" _opcoes "$1" "$2"; }
_opcoes() {
  gh api graphql -F n="$1" -f o="$PROJETO_OWNER" -f c="$2" -f query='
    query($o:String!,$n:Int!,$c:String!){ repositoryOwner(login:$o){ ... on ProjectV2Owner { projectV2(number:$n){
      field(name:$c){ ... on ProjectV2SingleSelectField { id options{ id name } } } } } } }' \
    --jq '.data.repositoryOwner.projectV2.field as $f | $f.options[] | "\($f.id)\t\(.id)\t\(.name)"'
}

campo_id() { cache "campo-$1-$(printf '%s' "$2" | cksum | cut -d' ' -f1)" _campo_id "$1" "$2"; }
_campo_id() {
  gh api graphql -F n="$1" -f o="$PROJETO_OWNER" -f c="$2" -f query='
    query($o:String!,$n:Int!,$c:String!){ repositoryOwner(login:$o){ ... on ProjectV2Owner { projectV2(number:$n){
      field(name:$c){ ... on ProjectV2FieldCommon { id } } } } } }' \
    --jq '.data.repositoryOwner.projectV2.field.id // empty'
}

item_de() {
  local pid="$1" issue="$2" node
  node=$(gh api "repos/$GITHUB_REPOSITORY/issues/$issue" --jq '.node_id')
  gh api graphql -f p="$pid" -f c="$node" -f query='
    mutation($p:ID!,$c:ID!){ addProjectV2ItemById(input:{projectId:$p, contentId:$c}){ item{ id } } }' \
    --jq '.data.addProjectV2ItemById.item.id'
}

valor_atual() {
  gh api graphql -f i="$1" -f c="$2" -f query='
    query($i:ID!,$c:String!){ node(id:$i){ ... on ProjectV2Item {
      fieldValueByName(name:$c){ ... on ProjectV2ItemFieldSingleSelectValue { name } } } } }' \
    --jq '.data.node.fieldValueByName.name // "-"'
}

definir_opcao() { # <pid> <item> <campo id> <opcao id>
  gh api graphql -f p="$1" -f i="$2" -f f="$3" -f o="$4" -f query='
    mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){ updateProjectV2ItemFieldValue(input:{
      projectId:$p, itemId:$i, fieldId:$f, value:{singleSelectOptionId:$o}}){ projectV2Item{ id } } }' >/dev/null
}

mover() {
  local painel="$1" issue="$2" destino="$3" de="${4:-}" pid item atual linha campo opcao
  if [ "${DRY_RUN:-}" = 1 ]; then
    echo "[simulado] painel $painel: #$issue -> '$destino' (somente de: ${de:-qualquer})"; return 0
  fi
  pid=$(projeto_id "$painel")
  item=$(item_de "$pid" "$issue")
  atual=$(valor_atual "$item" Status)
  if [ -n "$de" ] && ! printf '%s' "|$de|" | grep -F "|$atual|" >/dev/null; then
    echo "#$issue no painel $painel: '$atual' fora de [$de]; mantido."; return 0
  fi
  if [ "$atual" = "$destino" ]; then echo "#$issue no painel $painel: já está em '$destino'."; return 0; fi
  linha=$(opcoes "$painel" Status | awk -F'\t' -v d="$destino" '$3 == d' | head -n 1)
  [ -n "$linha" ] || { echo "Coluna '$destino' não existe no painel $painel." >&2; return 1; }
  IFS=$'\t' read -r campo opcao _ <<<"$linha"
  definir_opcao "$pid" "$item" "$campo" "$opcao"
  echo "#$issue no painel $painel: '$atual' -> '$destino'."
}

cartoes() {
  local pid; pid=$(projeto_id "$1")
  gh api graphql --paginate -f id="$pid" -f query='
    query($id:ID!,$endCursor:String){ node(id:$id){ ... on ProjectV2 {
      items(first:100, after:$endCursor){ pageInfo{ hasNextPage endCursor } nodes{
        fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue { name } }
        content{ ... on Issue { number repository{ nameWithOwner } } } } } } } }' \
    --jq '.data.node.items.nodes[]
      | select(.content.repository.nameWithOwner != null)
      | "\(.fieldValueByName.name // "-")\t\(.content.repository.nameWithOwner)\t\(.content.number)"' \
    | awk -F'\t' -v s="$2" -v r="$GITHUB_REPOSITORY" '$1 == s && $2 == r { print $3 }'
}

colunas() { opcoes "$1" Status | cut -f3; }

quadro() {
  local pid; pid=$(projeto_id "$1")
  gh api graphql --paginate -f id="$pid" -f query='
    query($id:ID!,$endCursor:String){ node(id:$id){ ... on ProjectV2 {
      items(first:100, after:$endCursor){ pageInfo{ hasNextPage endCursor } nodes{
        status: fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue { name } }
        sprint: fieldValueByName(name:"Sprint"){ ... on ProjectV2ItemFieldSingleSelectValue { name } }
        content{ ... on Issue { number title state repository{ nameWithOwner } } } } } } } }' \
    --jq '.data.node.items.nodes[] | select(.content.state == "OPEN")
      | "\(.content.repository.nameWithOwner)\t\(.status.name // "-")\t\(.content.number)\t\(.content.title)\t\(.sprint.name // "-")"' \
    | awk -F'\t' -v r="$GITHUB_REPOSITORY" 'BEGIN { OFS = "\t" } $1 == r { print $2, $3, $4, $5 }'
}

remover() {
  local painel="$1" issue="$2" pid item
  if [ "${DRY_RUN:-}" = 1 ]; then echo "[simulado] remover #$issue do painel $painel"; return 0; fi
  pid=$(projeto_id "$painel"); item=$(item_de "$pid" "$issue")
  gh api graphql -f p="$pid" -f i="$item" -f query='
    mutation($p:ID!,$i:ID!){ deleteProjectV2Item(input:{projectId:$p, itemId:$i}){ deletedItemId } }' >/dev/null
  echo "#$issue removida do painel $painel."
}

texto() {
  local painel="$1" issue="$2" nome="$3" valor="$4" pid item campo
  if [ "${DRY_RUN:-}" = 1 ]; then echo "[simulado] painel $painel: #$issue $nome='$valor'"; return 0; fi
  campo=$(campo_id "$painel" "$nome")
  [ -n "$campo" ] || { echo "Campo '$nome' não existe no painel $painel." >&2; return 1; }
  pid=$(projeto_id "$painel"); item=$(item_de "$pid" "$issue")
  gh api graphql -f p="$pid" -f i="$item" -f f="$campo" -f t="$valor" -f query='
    mutation($p:ID!,$i:ID!,$f:ID!,$t:String!){ updateProjectV2ItemFieldValue(input:{
      projectId:$p, itemId:$i, fieldId:$f, value:{text:$t}}){ projectV2Item{ id } } }' >/dev/null
  echo "#$issue no painel $painel: $nome='$valor'."
}

sprints() { opcoes "$1" Sprint | cut -f3; }

# Adds a Sprint option. ProjectV2SingleSelectFieldOptionInput accepts the option id, so the existing options are
# sent back with their ids and keep the values already set on the cards (a new id would wipe them).
sprint_criar() {
  local painel="$1" titulo="$2" campo lista="" oid nome
  if sprints "$painel" | grep -xF -- "$titulo" >/dev/null; then echo "Sprint '$titulo' já existe no painel $painel."; return 0; fi
  if [ "${DRY_RUN:-}" = 1 ]; then echo "[simulado] painel $painel: criar a opção de Sprint '$titulo'"; return 0; fi
  campo=$(campo_id "$painel" Sprint)
  [ -n "$campo" ] || { echo "Campo 'Sprint' não existe no painel $painel (rode criar-paineis.sh)." >&2; return 1; }
  while IFS=$'\t' read -r _ oid nome; do
    [ -n "$oid" ] || continue
    lista+="{id: $(json_texto "$oid"), name: $(json_texto "$nome"), color: GRAY, description: \"\"}, "
  done < <(opcoes "$painel" Sprint)
  lista+="{name: $(json_texto "$titulo"), color: BLUE, description: \"\"}"
  gh api graphql -f query="mutation { updateProjectV2Field(input: { fieldId: $(json_texto "$campo"),
    singleSelectOptions: [$lista] }) { projectV2Field { ... on ProjectV2SingleSelectField { id } } } }" >/dev/null
  limpar_cache "$painel"
  echo "Sprint '$titulo' criada no painel $painel."
}

# Renames a Sprint option keeping every id (the cards keep their Sprint).
sprint_renomear() {
  local painel="$1" de="$2" para="$3" campo lista="" oid nome
  if [ "${DRY_RUN:-}" = 1 ]; then echo "[simulado] painel $painel: Sprint '$de' -> '$para'"; return 0; fi
  campo=$(campo_id "$painel" Sprint)
  while IFS=$'\t' read -r _ oid nome; do
    [ -n "$oid" ] || continue
    [ "$nome" != "$de" ] || nome="$para"
    lista+="{id: $(json_texto "$oid"), name: $(json_texto "$nome"), color: GRAY, description: \"\"}, "
  done < <(opcoes "$painel" Sprint)
  gh api graphql -f query="mutation { updateProjectV2Field(input: { fieldId: $(json_texto "$campo"),
    singleSelectOptions: [${lista%, }] }) { projectV2Field { ... on ProjectV2SingleSelectField { id } } } }" >/dev/null
  limpar_cache "$painel"
  echo "Sprint '$de' renomeada para '$para' no painel $painel."
}

json_texto() { # GraphQL string literal
  local s="${1//\\/\\\\}"; s="${s//\"/\\\"}"; printf '"%s"' "$s"
}

sprint() {
  local painel="$1" issue="$2" titulo="$3" linha campo opcao pid item
  if [ "${DRY_RUN:-}" = 1 ]; then echo "[simulado] painel $painel: #$issue -> Sprint '$titulo'"; return 0; fi
  linha=$(opcoes "$painel" Sprint | awk -F'\t' -v t="$titulo" '$3 == t' | head -n 1)
  [ -n "$linha" ] || { echo "Sprint '$titulo' não existe no painel $painel." >&2; return 1; }
  IFS=$'\t' read -r campo opcao _ <<<"$linha"
  pid=$(projeto_id "$painel"); item=$(item_de "$pid" "$issue")
  definir_opcao "$pid" "$item" "$campo" "$opcao"
  echo "#$issue no painel $painel: Sprint '$titulo'."
}

sprint_de() {
  local pid item; pid=$(projeto_id "$1"); item=$(item_de "$pid" "$2")
  local valor; valor=$(valor_atual "$item" Sprint)
  [ "$valor" = "-" ] || printf '%s\n' "$valor"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  mover) mover "$@" ;;
  cartoes) cartoes "$@" ;;
  colunas) colunas "$@" ;;
  quadro) quadro "$@" ;;
  remover) remover "$@" ;;
  texto) texto "$@" ;;
  sprints) sprints "$@" ;;
  sprint-criar) sprint_criar "$@" ;;
  sprint-renomear) sprint_renomear "$@" ;;
  sprint) sprint "$@" ;;
  sprint-de) sprint_de "$@" ;;
  *) sed -n '2,23p' "$0"; exit 2 ;;
esac
