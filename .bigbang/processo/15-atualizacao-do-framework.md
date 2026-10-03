# 15 · Atualização do framework

O Big Bang é atualizável: tudo que é do framework fica isolado e pode ser trocado por uma versão nova **sem tocar no
que é do projeto**.

## As três camadas

| Camada | Onde | Quem edita | Numa atualização |
| --- | --- | --- | --- |
| **Framework** | `.bigbang/` | Ninguém no projeto | Substituída inteira pela versão nova (conferida por hash) |
| **Gerada** | `.github/` (arquivos com prefixo `bb-`), `.agents/skills/bb-*`, `.claude/skills/bb-*`, `.claude/settings.json`, `.claude/agents/bb-*`, bloco marcado do `AGENTS.md`, bloco marcado do `STACK.md` | O gerador (`bb gerar`), a partir de `.bigbang/` + `bigbang.toml` | Gerada de novo; o dono revisa o diff num PR |
| **Projeto** | Todo o resto: `bigbang.toml`, `PRODUTO.md`, `STACK.md` (fora do bloco), `DESIGN.md`, `docs/`, `src/`, `tests/`, skills e workflows sem prefixo `bb-` | O dono e as IAs | Nunca é tocada |

Todo arquivo gerado começa com o aviso:

```
Gerado pelo Big Bang vX.Y.Z a partir de <caminho do template>. Não edite: personalize em bigbang.toml.
```

O `bb verificar` reprova na CI qualquer arquivo gerado editado à mão e qualquer alteração em `.bigbang/` que não
bata com `.bigbang/CHECKSUMS`.

## Personalizar sem editar o framework

- Configuração: `bigbang.toml`, depois `bb gerar`.
- Skills próprias: `.agents/skills/<nome>` **sem** o prefixo `bb-`.
- Workflows próprios: `.github/workflows/<nome>.yml` **sem** o prefixo `bb-`.
- Instruções próprias: a seção `## Projeto` do `AGENTS.md`.
- Se o framework não permite o que o projeto precisa: abrir issue no repositório do Big Bang.

## `bb atualizar [versão]`

Skill `bb-atualizar` (o dono diz "atualizar o Big Bang"):

1. Lê a versão atual e a origem em `bigbang.toml` (`bigbang.versao`, `bigbang.origem`).
2. Baixa `bigbang-vX.Y.Z.tar.gz` e o `.sha256` da Release pública da origem; confere o hash; recusa se não bater.
3. Mostra o `MIGRACAO.md` entre as duas versões; se houver passo manual, pergunta ao dono.
4. Cria a branch `framework/vX.Y.Z` a partir da `develop`, troca `.bigbang/` inteira, atualiza `bigbang.versao`, roda
   `bb gerar` e `bb verificar`.
5. Abre o PR `framework/vX.Y.Z` → `develop` com `revisao-humana` (toca `.github/`), listando o diff da camada gerada.

## Versões do Big Bang

O Big Bang segue [SemVer](https://semver.org/lang/pt-BR/): versão **maior** = o projeto precisa agir, e o
`MIGRACAO.md` diz como. Cada versão é uma tag `vX.Y.Z` no repositório do Big Bang, com uma GitHub Release que contém
`bigbang-vX.Y.Z.tar.gz` (a pasta `.bigbang/`), `bigbang-vX.Y.Z.tar.gz.sha256` e as notas extraídas do `MIGRACAO.md`.

## O que a automação faz sozinha

No repositório do Big Bang, o workflow de release empacota `.bigbang/` a cada tag. No projeto, a CI roda o
`bb verificar` em todo PR.
