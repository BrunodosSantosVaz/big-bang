---
name: bb-auditar-seguranca
description: Use para audita a segurança, antes da primeira produção e ao fim de épico em zona sensível. Reporta só achados verificados no código e abre issues com evidências; não corrige na mesma sessão sem issue.
---
<!-- Gerado pelo Big Bang v2.0.1 a partir de .bigbang/skills/bb-auditar-seguranca/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Auditar segurança

## Quando usar

Na auditoria solicitada ou nos portões de primeira produção/zona sensível; não amplie todo trabalho comum para auditoria.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `STACK.md`, ASVS em `bigbang.toml`, `.bigbang/padroes/seguranca.md`,
`.bigbang/processo/11-seguranca-operacional.md` e escopo/alvo autorizado.

## Passos

1. Detecte stack e aplique ferramentas existentes: Gitleaks, Opengrep/Bandit, OSV-Scanner, Trivy e ZAP no staging quando houver.
   Use workflow/script de Segurança previsto, sem reimplementar ou baixar scanner sem versão/hash. Não varra alvo externo
   sem autorização; falha/indisponibilidade de ferramenta é pendência, nunca resultado limpo.
2. Revise SEG-IA-01 a SEG-IA-05 e checklist ASVS do nível escolhido. Valide cada alerta no código/teste; descarte falso positivo
   com motivo, sem desativar scanner. Segredo encontrado é vazado: avise o dono para revogar/trocar, sem reproduzir o valor.
3. Grave `docs/seguranca/auditorias/AAAA-MM-DD.md`: arquivo:linha, trecho seguro, exploração demonstrável e severidade.
   Distinga achado comprovado de verificação ainda pendente; não publique alegação especulativa.
4. Uma issue por achado: bug, seguranca, severidade:*; título [Segurança] descrição curta, evidência, correção sugerida e CA.
   Crítico/alto recebem bloqueia-producao. Preserve dados sensíveis; reporte à parte quando divulgação pública trouxer risco.
5. Encerre com relatório/issues e próximos passos. Correção exige issue e pedido de implementação, pelo fluxo de bug.

## Pare e pergunte quando

Faltar permissão para varredura, houver vazamento, risco de divulgação ou garantia SEG-IA em conflito com o pedido.

## Nunca

Especule vulnerabilidade sem evidência, exponha segredo, desligue varredura ou corrija sem issue/autorização.

## Pronto quando

Relatório e issues criados para achados confirmados, cobertura e pendências declaradas.
