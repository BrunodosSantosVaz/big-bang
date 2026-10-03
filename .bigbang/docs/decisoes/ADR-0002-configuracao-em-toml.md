# ADR-0002: Configuração do projeto em `bigbang.toml`

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

Tudo que as ferramentas precisam saber sobre um projeto (perfil de entrega, caminhos do artefato, zonas sensíveis,
comandos da stack, painéis, IAs) precisa estar numa fonte única, lida pelo `bb`, pelos scripts e pelos workflows. O
planejamento original previa `bigbang.yml`.

## Fatores de decisão

- Leitura sem dependência (ADR-0001).
- Legível e editável à mão pelo dono.
- Validação de esquema com recusa de chaves desconhecidas.

## Opções consideradas

1. `bigbang.toml`, lido com `tomllib`.
2. `bigbang.yml`, lido com PyYAML.
3. `bigbang.json`.

## Decisão e justificativa

Escolhida: **opção 1**. O Python lê TOML sem dependência desde o 3.11; YAML exigiria uma biblioteca externa. JSON
não aceita comentários, que são essenciais para o dono entender cada chave. Os scripts Bash leem a configuração por
`bb config get <chave>`, nunca analisando o arquivo por conta própria.

## Consequências

### Positivas

- Fonte única, comentada e validada.
- Nenhuma dependência para ler.

### Negativas

- Os workflows do GitHub continuam em YAML (formato do GitHub); eles são **gerados**, nunca configurados à mão.
- Chaves com hífen, como `build_windows-x64`, são válidas em TOML mas exigem cuidado no acesso; o esquema do gerador
  as trata de forma explícita.

## Referências

- Especificação, seções 3.3 e 5.4, e Apêndice A, item 2.
- TOML 1.0 — https://toml.io/pt/v1.0.0
