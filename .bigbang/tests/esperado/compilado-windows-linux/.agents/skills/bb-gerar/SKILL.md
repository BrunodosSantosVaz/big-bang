---
name: bb-gerar
description: Use em F5 ou quando bigbang.toml mudar ou o framework for atualizado, para simular, gerar e verificar a camada gerada e abrir PR com revisão humana.
---
<!-- Gerado pelo Big Bang v2.0.1 a partir de .bigbang/skills/bb-gerar/SKILL.md. Não edite: personalize em bigbang.toml. -->

# Gerar a camada do Big Bang

## Quando usar

Para regenerar após mudança aprovada; na primeira instalação da esteira, em F5.

## Antes de começar

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Leia `AGENTS.md`, `bigbang.toml`, `.bigbang/processo/15-atualizacao-do-framework.md` e a etapa de Fundação se aplicável.
Confira branch e alterações existentes; preserve arquivos e alterações do projeto.

## Passos

1. Em F5, use `bb gerar --esteira --simular`; nas outras regenerações, `bb gerar --simular`.
   Sem configuração fundada, não instale esteira. Mostre inclusões, alterações e remoções previstas.
2. Resolva configuração inválida pela decisão do dono, nunca alterando framework/arquivo gerado para esconder o erro.
3. Rode `bb gerar --esteira` só na primeira instalação de F5; depois, `bb gerar`. Rode `bb verificar` e comandos da stack.
   Depois do merge da F5, rode de novo `.bigbang/scripts/configurar-repositorio.sh` para os rulesets exigirem os checks.
4. Revise que só a camada gerada mudou e que skills sem prefixo bb-, documentos e código do projeto foram preservados.
5. Abra PR para develop com `revisao-humana`, diff e evidências; peça revisão. Em F5, continue Esqueleto andante pela
   `bb-rodar-sprint`; gerar arquivos não encerra a Fundação.

## Pare e pergunte quando

O diff remover algo inesperado, existir conflito com alteração do dono ou for necessária mudança de decisão/configuração.

## Nunca

Edite gerado à mão, regenere CHECKSUMS de framework adulterado ou desligue uma verificação.

## Pronto quando

`bb verificar` verde e PR revisado; a Fundação ainda exige seu ciclo até produção.
