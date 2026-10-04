#!/usr/bin/env bash
# Creates (or updates) every label of the process (spec 11.2) in a repository. Idempotent (--force).
# Usage: .bigbang/scripts/criar-labels.sh OWNER/REPO [--simular]
# The ia:<nome> ownership labels are created on demand by `bb assumir`.
set -euo pipefail

REPO="${1:?Uso: $0 OWNER/REPO [--simular]}"
SIMULAR="${2:-}"

# name|color|description
LABELS=(
  "epic|5319E7|Épico: mudança com valor, unidade de planejamento, homologação e release"
  "task|1D76DB|Tarefa de um épico (um PR)"
  "teste-aceite|0E8A16|Testes de aceite do épico, escritos antes das tarefas"
  "documentacao|0075CA|Documentação do épico (última issue do épico)"
  "bug|D73A4A|Defeito: unidade de release"
  "fundacao|1D76DB|Etapa da Fundação (F0 a F5)"
  "seguranca|B60205|Achado ou trabalho de segurança"
  "sem-release|BFD4F2|Não muda o artefato: sem versão nem homologação"
  "com-prototipo|F9D0C4|O épico precisa de protótipo aprovado"
  "sem-prototipo|EDEDED|O épico não precisa de protótipo"
  "testes-revisao-ia|C5DEF5|Testes de aceite revisados pela IA"
  "testes-revisao-humana|FBCA04|Testes de aceite revisados pelo dono antes de codar"
  "revisao-ia|C5DEF5|PRs revisados pela IA (bb-revisor-pr)"
  "revisao-humana|FBCA04|PRs revisados pelo dono"
  "refinamento-aprovado|0E8A16|Decisão do dono: refinamento aprovado"
  "prototipo-aprovado|0E8A16|Decisão do dono: protótipo aprovado"
  "testes-aprovados|0E8A16|Decisão do dono: testes de aceite aprovados"
  "teste-alterado-aprovado|D93F0B|Decisão do dono: mudança em tests/aceite/ aprovada"
  "homologado|0E8A16|Decisão do dono: homologado"
  "reprovado|B60205|Decisão do dono: reprovado na homologação"
  "dono:revisao-ia|5319E7|Decisão do dono: a revisão volta para a IA e não é trocada de novo"
  "pr-aprovado|0E8A16|PR aprovado (IA com revisao-ia; dono com revisao-humana)"
  "tem-dependencia|D4C5F9|Depende de outro épico ainda não publicado"
  "conflito|B60205|Conflito ao devolver a main ou ao integrar"
  "bloqueia-producao|B60205|Nenhuma publicação passa enquanto estiver aberta"
  "parada|FEF2C0|Posse de IA sem push há mais que o limite"
  "prioridade:alta|B60205|Prioridade alta"
  "prioridade:media|FBCA04|Prioridade média"
  "prioridade:baixa|C2E0C6|Prioridade baixa"
  "severidade:critica|B60205|Sistema fora, perda de dados ou segurança"
  "severidade:alta|D93F0B|Função principal quebrada sem alternativa"
  "severidade:media|FBCA04|Falha com contorno"
  "severidade:baixa|C2E0C6|Cosmético ou raro"
  "hotfix|B60205|Correção urgente em produção"
  "dependencies|0366D6|Atualização de dependências"
  "good first issue|7057FF|Bom para quem está começando"
  "help wanted|008672|Ajuda bem-vinda"
)

for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color description <<<"$entry"
  if [ "$SIMULAR" = --simular ]; then echo "[simulado] label $name"; continue; fi
  gh label create "$name" --repo "$REPO" --color "$color" --description "$description" --force >/dev/null
  echo "label ok: $name"
done
