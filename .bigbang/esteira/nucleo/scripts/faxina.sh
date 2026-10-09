#!/usr/bin/env bash
# "Faxina" (housekeeping): nothing is left behind after a publication or a sprint. Runs at the end of "Encerrar"
# (version and sprint) and of "Publicar sem release"; can also be run alone. API failures are always explicit.
#   DELETES remote branches already merged (contained in main or develop) whose work is over:
#     epico/<n>-*                      when the epic #n is closed and no PR from it is open;
#     teste|feature|docs|bugfix|hotfix/<n>-*  when the issue #n is closed and no PR from it is open;
#     framework/*, fundacao/*, sync/*  when no PR from it is open;
#     release/x.y.z                    when incorporated in its stable published tag and main/develop.
#   REPORTS: branches outside the naming rules, unmerged branches without an open PR, open issues in a closed
#   (published) milestone, PRs open for more than FAXINA_DIAS days (14), and open ownership claims (ia:<nome>).
# Main, develop and dependabot/* are never touched; tags are never deleted.
# FAXINA_EXIGIR_LIMPA=true makes unresolved leftovers fail closure instead of silently succeeding.
# Environment: SIMULAR, FAXINA_DIAS, FAXINA_EXIGIR_LIMPA, GITHUB_REPOSITORY, GH_TOKEN.
set -euo pipefail
trap 'echo "::error::$(basename "$0") falhou na linha $LINENO (código $?)" >&2' ERR

R="${GITHUB_REPOSITORY:?}"; SIMULAR="${SIMULAR:-false}"; DIAS="${FAXINA_DIAS:-14}"
avisos=0
aviso() { echo "  ! $*"; avisos=$((avisos + 1)); }
apagar() { # <branch> <motivo>
  if [ "$SIMULAR" = true ]; then echo "  [simulado] apagar $1 ($2)"; return; fi
  gh api -X DELETE "repos/$R/git/refs/heads/$1" >/dev/null && echo "  apagada: $1 ($2)"
}
estado() { gh api "repos/$R/issues/$1" --jq .state; }

echo "Faxina de $R$([ "$SIMULAR" = true ] && echo " [SIMULAÇÃO]")"
git fetch -q --prune origin "+refs/heads/*:refs/remotes/origin/*" --tags
abertos=" $(gh pr list --repo "$R" --state open --limit 200 --json headRefName --jq '[.[].headRefName] | join(" ")') "
# Capture reads before mutations; process substitution would hide a failed GitHub request.
issues_publicadas=$(gh api --paginate "repos/$R/issues?state=open&per_page=100" \
  --jq '.[] | select((has("pull_request") | not) and .milestone.state == "closed") | "\(.number)\t\(.milestone.title)"')
prs=$(gh pr list --repo "$R" --state open --limit 200 --json number,createdAt,headRefName \
  --jq '.[] | "\(.number)\t\(.createdAt)\t\(.headRefName)"')
posses=$(gh api --paginate "repos/$R/issues?state=open&per_page=100" \
  --jq '[.[] | select([.labels[].name] | any(startswith("ia:"))) | "#\(.number)"] | join(" ")')
mesclada() { # contained in main or develop
  git merge-base --is-ancestor "origin/$1" origin/main 2>/dev/null \
    || { git rev-parse -q --verify origin/develop >/dev/null && git merge-base --is-ancestor "origin/$1" origin/develop; }
}

echo "== Branches"
while IFS= read -r b; do
  case "$b" in main|develop|HEAD|dependabot/*) continue ;; esac
  pr_aberto=false; [[ "$abertos" == *" $b "* ]] && pr_aberto=true
  if $pr_aberto; then
    [ "${FAXINA_EXIGIR_LIMPA:-false}" != true ] || aviso "$b: PR aberto; branch preservada"
    continue
  fi
  if [[ "$b" =~ ^release/([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    tag="v${BASH_REMATCH[1]}"
    if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
      release=$(gh api "repos/$R/releases/tags/$tag")
      if jq -e --arg tag "$tag" '.tag_name == $tag and .draft == false and .prerelease == false' <<< "$release" >/dev/null \
        && mesclada "$b" && git merge-base --is-ancestor "origin/$b" "refs/tags/$tag"; then
        apagar "$b" "$tag publicada e incorporada"
      else
        aviso "$b: release não estável ou commits fora da tag/main/develop; preservada"
      fi
    fi
    continue
  fi
  if [[ "$b" =~ ^epico/([0-9]+)- ]]; then
    n="${BASH_REMATCH[1]}"
    estado_atual=$(estado "$n")
    if [ "$estado_atual" = closed ]; then
      if mesclada "$b"; then apagar "$b" "épico #$n fechado"; else aviso "$b: épico fechado, mas a branch tem commits fora da main/develop"; fi
    fi
    continue
  fi
  if [[ "$b" =~ ^(teste|feature|docs|bugfix|hotfix)/([0-9]+)- ]]; then
    n="${BASH_REMATCH[2]}"
    estado_atual=$(estado "$n")
    if [ "$estado_atual" = closed ]; then
      if mesclada "$b"; then apagar "$b" "#$n fechada"; else aviso "$b: #$n fechada, mas a branch tem commits fora da main/develop"; fi
    elif ! mesclada "$b" && [ "$(git log -1 --format=%ct "origin/$b")" -lt "$(( $(date +%s) - DIAS * 86400 ))" ]; then
      aviso "$b: #$n aberta, sem PR e sem commit há mais de $DIAS dias"
    fi
    continue
  fi
  if [[ "$b" =~ ^(framework|fundacao|sync)/ ]]; then
    if mesclada "$b"; then apagar "$b" "mesclada"; else aviso "$b: sem PR aberto e com commits fora da main/develop"; fi
    continue
  fi
  aviso "$b: branch fora do padrão do Big Bang (07-branches-e-commits.md)"
done < <(git for-each-ref --format='%(refname:strip=3)' refs/remotes/origin)

echo "== Issues e PRs"
while IFS=$'\t' read -r n marco; do
  [ -n "$n" ] || continue
  aviso "#$n aberta no milestone $marco, já publicado (feche ou leve para a próxima versão)"
done <<< "$issues_publicadas"
limite=$(date -u -d "-$DIAS days" +%FT%TZ 2>/dev/null || date -u -v-"$DIAS"d +%FT%TZ)
while IFS=$'\t' read -r n criado head; do
  [ -n "$n" ] || continue
  [[ "$criado" > "$limite" ]] || aviso "PR #$n ($head) aberto desde ${criado%%T*}"
done <<< "$prs"
[ -z "$posses" ] || aviso "posses abertas: $posses (libere com bb liberar na pasta da tarefa, ou explique ao dono)"

if [ "$avisos" -gt 0 ]; then
  echo "Faxina: $avisos ponto(s) para revisar (acima). Resolva ou explique ao dono."
  [ "${FAXINA_EXIGIR_LIMPA:-false}" != true ] || exit 1
else
  echo "Faxina: nada sobrando."
fi
