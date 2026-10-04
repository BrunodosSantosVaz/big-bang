---
name: bb-escolher-stack
description: Use em F2 da Fundação para pesquisar e propor stack, arquitetura e hospedagem. O dono escolhe; a skill registra STACK.md, configuração, ADR e C4.
---

# Escolher stack

## Quando usar

Em F2, depois do produto aprovado. Para dependência nova em projeto fundado, use `bb-nova-tecnologia`.

## Antes de começar

Leia `PRODUTO.md`, `AGENTS.md`, `.bigbang/processo/02-fundacao.md` e os padrões em `.bigbang/padroes/`.
Confira `.bigbang/modelos/STACK.md`, `bigbang.toml` e decisões já aprovadas.

## Passos

1. Acione `bb-pesquisador` com contexto separado, requisitos e orçamento; sem subagentes, use sessão separada.
   Exija fontes oficiais atuais, datas e incertezas, gravadas em `docs/pesquisa/`.
2. Apresente duas ou três opções completas: linguagem, framework, banco, entrega/alvo, testes, lint, tipos e arquitetura;
   compare custo mensal, curva, licença, manutenção ativa, segurança e risco. Recomende e espere a escolha.
3. Após a escolha, escreva `STACK.md` com dependências de execução permitidas e versões; complete `bigbang.toml`,
   inclusive perfil/alvo, caminhos do artefato, versão, comandos, ecossistemas e zonas sensíveis.
4. Escreva `docs/decisoes/ADR-0001-stack.md` com alternativas e C4 inicial em `docs/arquitetura/`.
   Preserve os marcadores gerados do STACK.md; use `bb gerar --simular`, `bb gerar` e `bb verificar` para o bloco.
5. Peça aprovação dos arquivos no PR de F2 e registre a frase antes do merge. Só então libere código do sistema.

## Pare e pergunte quando

O dono ainda não escolheu, faltar orçamento ou uma tecnologia contrariar requisitos ou garantias SEG-IA.

## Nunca

Escolha pelo dono, instale antes da escolha ou proponha tecnologia sem manutenção ativa.

## Pronto quando

STACK, configuração, ADR e C4 aprovados e coerentes com o produto.
