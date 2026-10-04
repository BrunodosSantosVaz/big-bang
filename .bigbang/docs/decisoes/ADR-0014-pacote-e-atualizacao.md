# ADR-0014: Pacote do framework e `bb atualizar`

- **Situação:** aceita
- **Data:** 2026-10-04
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

A seção 5.7 pede que um sistema troque só o framework, conferido por hash, sem tocar na camada do projeto. Para isso
cada versão do Big Bang precisa publicar um pacote confiável, e o sistema precisa de um comando que o baixe, confira,
mostre o que muda e entregue a troca num PR para revisão humana.

## Decisão e justificativa

- **Pacote reprodutível** (`bb pacote`, `.bigbang/bb/package.py`): `bigbang-vX.Y.Z.tar.gz` com os arquivos do
  `CHECKSUMS` mais o próprio `CHECKSUMS`, em ordem, com data, dono e permissões fixos e gzip sem data. O mesmo conteúdo
  gera o mesmo SHA-256 em qualquer máquina, então qualquer um pode reconstruir e comparar. Recusa empacotar se o
  framework não bater com o `CHECKSUMS`.
- **Release do framework** (`.github/workflows/bb-framework-release.yml`): na tag `vX.Y.Z` que está na `main` e bate
  com `.bigbang/VERSION`, roda `bb verificar`, empacota, gera a **atestação de origem** do pacote e cria a Release com
  o pacote, o `.sha256` e as notas da seção da versão no `MIGRACAO.md`. Só roda no repositório do Big Bang; a
  Fundação o remove dos sistemas (prefixo `bb-framework-`).
- **`MIGRACAO.md`** em `.bigbang/`: uma seção `## [X.Y.Z]` por versão, com "O que muda" e "O que o projeto precisa
  fazer" ("Nada." quando não há passo manual). Os testes exigem a seção da versão atual.
- **`bb atualizar [versão]`** (`.bigbang/bb/update.py`): exige árvore limpa; baixa o pacote da Release de
  `bigbang.origem` (sem versão, a última); confere SHA-256, **atestação** (`gh attestation verify --repo <origem>`),
  entradas só dentro de `.bigbang/`, o `CHECKSUMS` e o `VERSION` do pacote; mostra o `MIGRACAO.md` entre as versões e
  **para** se houver passo manual, até o dono confirmar (`--confirmo-migracao`); cria `framework/vX.Y.Z` da `develop`,
  troca `.bigbang/` inteira (mantendo o README e a LICENSE que o `bb init` moveu para lá), atualiza só a chave
  `bigbang.versao` e roda o `bb gerar` e o `bb verificar` **da versão nova** em outro processo (o processo atual tem o
  código antigo carregado); se tudo passar, faz commit, envia e abre o PR para a `develop` com `revisao-humana`.
  `--simular` baixa, confere e mostra a migração sem gravar nada.
- **Atestação além do hash:** o `.sha256` vem da mesma Release e só prova integridade; a atestação prova que o pacote
  foi construído pelo workflow do repositório de origem. `--sem-atestacao` existe só para origem sem atestação (fork
  privado) e a skill proíbe usá-lo sem o dono pedir.
- **Versões anteriores à 0.10.0** não têm `bb atualizar`: a primeira atualização usa o `bb` do pacote novo, uma vez
  (passo descrito no `MIGRACAO.md`). Daí em diante, o próprio sistema atualiza.

## Consequências

### Positivas

- A troca do framework é um PR comum, revisado pelo dono, com a migração e o diff da camada gerada; a camada do
  projeto não muda (teste de ponta a ponta com git real e validação num sistema de teste).
- Pacote adulterado, Release trocada ou pacote de outro repositório são recusados antes de tocar no sistema.

### Negativas

- Precisa do `gh` autenticado com suporte a `gh attestation` (2.49+).
- Uma versão maior com passo manual exige o dono na conversa; a IA não segue sozinha.

## Referências

- Especificação, seções 5.2, 5.7 e 17 (E10); `.bigbang/processo/15-atualizacao-do-framework.md`.
- Atestações de artefato do GitHub: https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
