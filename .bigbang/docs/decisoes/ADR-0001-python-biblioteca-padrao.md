# ADR-0001: Ferramentas do framework em Python só com a biblioteca padrão

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

O CLI `bb`, o gerador, o verificador e os hooks precisam rodar em Linux, macOS e Windows, na máquina do dono e nas
GitHub Actions, em qualquer sistema criado a partir do Big Bang, seja qual for a stack escolhida. Qualquer dependência
de instalação do framework vira atrito na primeira sessão e risco de cadeia de suprimentos em todos os projetos.

## Fatores de decisão

- Rodar igual nos três sistemas operacionais, sem passo de instalação.
- Não impor dependência de execução à stack do projeto (o framework não pode furar a *Guarda da stack*).
- Superfície de ataque mínima (SEG-17, SEG-18).
- Testável na CI com o mínimo de ferramentas.

## Opções consideradas

1. Python 3.11+ só com a biblioteca padrão (`tomllib`, `unittest`, `subprocess`, `json`, `hashlib`).
2. Python com dependências (Click, PyYAML, Jinja2) instaladas por `pip`.
3. Node.js (com `npx`).
4. Binário em Go distribuído na Release.

## Decisão e justificativa

Escolhida: **opção 1**. Python já está presente nos runners e é fácil de instalar em qualquer máquina; desde o 3.11 a
biblioteca padrão lê TOML (`tomllib`), o que cobre a configuração sem dependência. `unittest` cobre os testes, como já
acontece no CNABLens. Os templates usam substituição simples de `{{secao.chave}}` e composição por pastas, sem lógica
condicional, o que dispensa um motor de templates.

Os scripts de automação da esteira continuam em **Bash** (portados do CNABLens), usando `gh` (incluindo `gh api` e
`--jq`) e `git`, sem `jq` externo.

## Consequências

### Positivas

- Nenhum `pip install` para usar o framework; nada para atualizar por segurança fora do próprio Big Bang.
- Mesmo código no Windows, Linux e macOS.

### Negativas

- Sem bibliotecas prontas para CLI e templates: o código de argumentos e de substituição é próprio e precisa de
  testes.
- Escrita de TOML não existe na biblioteca padrão: o `bb` só escreve TOML em formatos simples e controlados (por
  exemplo, a partir do modelo com substituições), com testes de ida e volta usando `tomllib`.

## Referências

- Especificação, seção 3.3.
- `tomllib` — https://docs.python.org/3/library/tomllib.html
