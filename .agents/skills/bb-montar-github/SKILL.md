---
name: bb-montar-github
description: Use em F4 da Fundação para guiar permissões e montar labels, painéis, rulesets e ambientes no GitHub, conferindo cada item antes do próximo. Nunca pede o valor de tokens.
---
<!-- Gerado pelo Big Bang v0.10.2 a partir de .bigbang/skills/bb-montar-github/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Montar o GitHub

## Quando usar

Em F4, com produto, stack e design aprovados ou design não aplicável registrado.

## Antes de começar

Leia `AGENTS.md`, `.bigbang/processo/02-fundacao.md` (F4), `.bigbang/processo/04-paineis.md`,
`.bigbang/processo/11-seguranca-operacional.md` e `bigbang.toml`. Consulte a documentação/plano atuais do GitHub.

## Passos

1. Um item por vez: mostre comando exato, propósito, efeito e qualquer limitação do plano. Espere o dono agir ou autorizar;
   confira o resultado com leitura por gh antes de seguir. Nunca trate configuração desejada como aplicada.
2. Confira escopo project no gh; oriente o dono a criar um `PROJETO_TOKEN` por projeto com validade e escopos mínimos
   e guardá-lo via `gh secret set PROJETO_TOKEN`. Confira só nome/metadados do secret, jamais seu valor.
3. Confira secret scanning/push protection; ambiente producao com aprovação do dono e só main; staging no perfil deploy;
   rulesets de main/develop/epico com PR, checks check/regras/seguranca e bloqueio de força/exclusão.
4. Deploy: credenciais do alvo, preferindo OIDC. Confira variáveis PROJETO_OWNER/números dos painéis, merge commit
   permitido e exclusão automática de branch desligada. Se o plano não suportar uma proteção, explique e peça decisão.
5. Com autorização, use `.bigbang/scripts/criar-labels.sh`, `.bigbang/scripts/criar-paineis.sh` e
   `.bigbang/scripts/configurar-repositorio.sh` (itens 3, 4, 5 e 7), sempre primeiro com `--simular`;
   não recrie sua lógica. Registre os números reais dos painéis no `bigbang.toml`, acrescente as issues da Fundação.
6. Execute `bb status` e confira os três painéis. Registre evidências no PR de F4 e peça aprovação.

## Pare e pergunte quando

Cada item exigir ação/permissão do dono, o plano limitar proteção ou a conferência não confirmar o resultado.

## Nunca

Peça, leia ou exponha o valor de token; amplie escopos silenciosamente; aprove o ambiente producao.

## Pronto quando

F4 aprovado, configuração efetiva registrada e `bb status` lendo os três painéis, com limitações aceitas explicitamente.
