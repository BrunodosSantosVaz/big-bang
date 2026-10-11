---
name: bb-montar-github
description: Use em F4 da Fundação para guiar permissões e montar labels v3, o Project único, rulesets com o check gate e o ambiente production, conferindo cada item antes do próximo. Nunca pede o valor de tokens.
---

# Montar o GitHub (v3)

## Quando usar

Em F4, com produto, stack e design aprovados, ou com o design registrado como não aplicável.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb docs read <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada em todos os modos. README público é uma apresentação breve com Wiki, Discussions e o quadro; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `.bigbang/processo/02-fundacao.md` (F4), `.bigbang/pipeline/process/board.md`,
`.bigbang/processo/11-seguranca-operacional.md` e `bigbang.toml`. Consulte a documentação e o plano atuais do GitHub.

## Passos

Habilite Discussions no escopo autorizado e publique o primeiro post factual com `bb community welcome-post`. Em
públicos, confira a Wiki e o quadro; audite o conteúdo antes de deixar o quadro com leitura pública. Registre a Wiki,
Discussions e o quadro no README e na Wiki, e confira o Social preview preparado em F3.

1. Um item por vez: mostre o comando exato, o propósito, o efeito e as limitações do plano. Espere o dono agir ou
   autorizar e confira o resultado com uma leitura pelo `gh` antes de seguir.
2. Confira o escopo `project` no `gh`. Oriente o dono a criar um `PROJECT_TOKEN` por projeto, com validade e escopos
   mínimos, e a guardá-lo com `gh secret set PROJECT_TOKEN`. Confira só o nome e os metadados do segredo.
3. Rode `bb board labels` (catálogo v3, idempotente) e `bb board create --title "<produto>"`. Registre no
   `bigbang.toml` (`[board]`, `model = "single"`, `number = N`) e nas variáveis `PROJECT_OWNER` e
   `PROJECT_NUMBER` os valores impressos.
4. Proteções:
   - secret scanning e push protection;
   - ambiente `production` só a partir da `main` e com a aprovação do dono (no autonomous, conforme o contrato);
   - `staging` no perfil deploy;
   - rulesets de `main` e `develop` com PR, o check obrigatório `gate` e bloqueio de força e exclusão;
   - merge commit permitido e exclusão automática de branch desligada.
   No deploy, credenciais do alvo, preferindo OIDC.
5. No modo autonomous, rode `bb autonomy check`; ele recusa o repositório sem esses controles (ou privado numa conta
   pessoal Free). Se o plano não suportar uma proteção, explique e peça a decisão do dono.
6. Rode `bb board show` e acrescente as issues da Fundação ao quadro. Registre as evidências no PR de F4 e peça a
   aprovação.

## Pare e pergunte quando

Algum item exigir ação ou permissão do dono, o plano limitar uma proteção ou a conferência não confirmar o resultado.

## Nunca

Peça, leia ou exponha o valor de um token; amplie escopos em silêncio; aprove o ambiente production.

## Pronto quando

F4 está aprovado, a configuração efetiva está registrada e `bb board show` lê o quadro único, com as limitações
aceitas explicitamente.
