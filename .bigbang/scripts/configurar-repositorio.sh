#!/usr/bin/env bash
# Foundation F4, items 3 to 7 (spec 10/F4): applies the repository protections the pipeline relies on, idempotently.
#   3. secret scanning and push protection;
#   4. environment `producao` (owner approval, only `main`); `staging` in the deploy profile;
#   5. rulesets on main, develop and epico/*: PR required, checks check/regras/seguranca, no force push, no deletion
#      (repository admins bypass them: the pipeline pushes with the owner's PROJETO_TOKEN);
#   7. repository variables PROJETO_OWNER/PLANEJAMENTO/EXECUCAO/BUGS (from bigbang.toml [paineis]) and merge options
#      (merge commit allowed, automatic branch deletion off: the pipeline deletes branches, with locks).
# Item 2 (PROJETO_TOKEN) and item 6 (deploy credentials) are secrets: only the owner creates them.
# A protection the plan does not offer (e.g. on a private repository of the free plan) is reported, never faked.
# The required checks are added only once the pipeline is installed (F5); run the script again after F5.
# Usage (from the project root): .bigbang/scripts/configurar-repositorio.sh OWNER/REPO [--simular]
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

REPO="${1:?Uso: $0 OWNER/REPO [--simular]}"
[[ "$REPO" =~ ^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$ ]] \
  || { echo "::error::informe o repositório como dono/repo (recebi '$REPO')" >&2; exit 2; }
SIMULAR="${2:-}"
read -r -a BB_CMD <<<"${BB:-python3 .bigbang/bin/bb.py}"
config() { "${BB_CMD[@]}" config get "$1"; }
avisos=0
aviso() { echo "  ! $*"; avisos=$((avisos + 1)); }
fazer() { # <descrição> <comando...>
  local descricao="$1"; shift
  if [ "$SIMULAR" = --simular ]; then echo "  [simulado] $descricao"; return 0; fi
  if "$@" >/dev/null 2>"${TMPDIR:-/tmp}/bb-configurar.err"; then echo "  ok: $descricao"
  else aviso "$descricao: $(head -c 300 "${TMPDIR:-/tmp}/bb-configurar.err" | tr '\n' ' ')"; fi
}
json() { python3 -c 'import json,sys; print(json.dumps(json.loads(sys.stdin.read())))'; }

dono=$(config projeto.dono)
perfil=$(config entrega.perfil)
dono_id=$(gh api "users/$dono" --jq .id)
echo "Configurando $REPO (dono $dono, perfil $perfil)$([ "$SIMULAR" = --simular ] && echo " [SIMULAÇÃO]")"

echo "3. Secret scanning e bloqueio de push"
fazer "secret scanning e push protection ligados" gh api -X PATCH "repos/$REPO" \
  -f "security_and_analysis[secret_scanning][status]=enabled" \
  -f "security_and_analysis[secret_scanning_push_protection][status]=enabled"

echo "4. Ambientes"
ambiente() { # <nome> <exigir aprovação: true|false>
  local corpo
  if [ "$2" = true ]; then
    corpo=$(printf '{"reviewers":[{"type":"User","id":%s}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}' "$dono_id")
  else
    corpo='{"deployment_branch_policy":null}'
  fi
  corpo=$(json <<<"$corpo")  # before the call: in a simulation nobody reads the <(…) and python would hit SIGPIPE
  fazer "ambiente $1$([ "$2" = true ] && echo " com aprovação do dono")" \
    gh api -X PUT "repos/$REPO/environments/$1" --input <(printf '%s' "$corpo")
}
ambiente producao true
if [ "$SIMULAR" != --simular ]; then
  if ! gh api "repos/$REPO/environments/producao/deployment-branch-policies" --jq '.branch_policies[].name' 2>/dev/null \
      | grep -x main >/dev/null; then
    fazer "producao aceita só a main" gh api -X POST "repos/$REPO/environments/producao/deployment-branch-policies" \
      -f name=main -f type=branch
  fi
  revisores=$(gh api "repos/$REPO/environments/producao" --jq '[.protection_rules[]? | select(.type == "required_reviewers")] | length')
  [ "$revisores" != 0 ] || aviso "o plano não aplicou a aprovação obrigatória em producao (repositório privado no plano gratuito?): a publicação fica sem o 'ok' do GitHub; decida com o dono"
fi
[ "$perfil" != deploy ] || ambiente staging false

echo "5. Rulesets"
# The required checks only exist once the pipeline is installed (F5): before that, requiring them would block every
# Foundation PR. Run this script again after `bb gerar --esteira`.
# Each rule type may appear only once in a ruleset (GitHub answers 422 otherwise), so before F5 the checks rule is
# simply left out.
checks=', {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": false,
         "required_status_checks": [{"context": "check"}, {"context": "regras"}, {"context": "seguranca"}]}}'
if [ ! -f .github/workflows/bb-ci.yml ]; then
  checks=""
  aviso "a esteira ainda não está instalada: os rulesets exigem PR, mas ainda não os checks; rode este script de novo depois da F5"
fi
ruleset() { # <nome> <padrão do ref>
  local id corpo
  corpo=$(json <<EOF
{"name": "$1", "target": "branch", "enforcement": "active",
 "conditions": {"ref_name": {"include": ["$2"], "exclude": []}},
 "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
 "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
           {"type": "pull_request", "parameters": {"required_approving_review_count": 0,
             "dismiss_stale_reviews_on_push": false, "require_code_owner_review": false,
             "require_last_push_approval": false, "required_review_thread_resolution": false}}$checks]}
EOF
)
  id=""
  [ "$SIMULAR" = --simular ] || id=$(gh api "repos/$REPO/rulesets" --jq ".[] | select(.name == \"$1\") | .id" 2>/dev/null || true)
  if [ -n "$id" ]; then
    fazer "ruleset $1 atualizado ($2)" gh api -X PUT "repos/$REPO/rulesets/$id" --input <(printf '%s' "$corpo")
  else
    fazer "ruleset $1 criado ($2)" gh api -X POST "repos/$REPO/rulesets" --input <(printf '%s' "$corpo")
  fi
}
ruleset bb-main refs/heads/main
ruleset bb-develop refs/heads/develop
ruleset bb-epicos "refs/heads/epico/*"

echo "7. Variáveis e opções de merge"
for par in "PROJETO_OWNER:paineis.owner" "PROJETO_PLANEJAMENTO:paineis.planejamento" \
           "PROJETO_EXECUCAO:paineis.execucao" "PROJETO_BUGS:paineis.bugs"; do
  valor=$(config "${par#*:}")
  if [ "$valor" = 0 ]; then aviso "${par#*:} = 0: rode criar-paineis.sh e registre os números no bigbang.toml"; continue; fi
  fazer "variável ${par%%:*}=$valor" gh variable set "${par%%:*}" --repo "$REPO" --body "$valor"
done
fazer "merge commit permitido; apagar branch no merge desligado" gh repo edit "$REPO" --enable-merge-commit \
  --delete-branch-on-merge=false

echo "Pendente do dono (segredos): PROJETO_TOKEN (gh secret set PROJETO_TOKEN --repo $REPO)$([ "$perfil" = deploy ] && echo "; credenciais do alvo de deploy")."
[ "$avisos" -eq 0 ] || echo "$avisos aviso(s): mostre cada um ao dono antes de seguir."
