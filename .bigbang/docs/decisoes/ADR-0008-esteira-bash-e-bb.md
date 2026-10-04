# ADR-0008: Esteira: Bash orquestra, o `bb` decide

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

A especificação (seção 14.5) manda portar os scripts Bash da esteira do CNABLens, parametrizando o que era fixo, e
escolher a versão mais robusta onde CNABLens e PrintRoute divergem. Também pede para não depender de `jq` externo.
Os scripts antigos misturavam orquestração (`gh`, `git`) com regras (formulário, versão, changelog, caminhos), e
algumas regras exigiam `jq` ou Python embutido.

## Comparação CNABLens × PrintRoute (2026-10-03)

Dos scripts em comum, 7 diferem. As diferenças são de parametrização, não de lógica:

- `toca-executavel.sh`, `publicar-sem-executavel.sh`, `conferir-release.sh`: listas fixas de caminhos do executável. O
  PrintRoute corrigiu um bug real (o compilador ficava fora da lista e um PR que só mudava o build pulava a
  homologação). **No Big Bang:** a lista vira `entrega.caminhos_artefato`, a mesma em todos os portões.
- `projeto.sh`: o do CNABLens é mais completo (`colunas` e `quadro`, usados pelo *Ver painéis*). **Escolhido** e
  reescrito sem `jq`.
- `versao.sh`: caminho fixo do arquivo de versão. **No Big Bang:** `entrega.arquivo_versao`.
- `anunciar-release.sh`, `atualizar_release.py`: textos com o nome do produto; o changelog passa para o `bb`.

## Opções consideradas

1. Portar os scripts quase iguais, com `jq` e Python embutido.
2. Reescrever toda a esteira em Python.
3. **Bash para orquestrar `gh` e `git`; toda regra com decisão em funções Python do `bb` (`bb esteira …`).**

## Decisão e justificativa

Escolhida: **opção 3**. Os scripts (`.bigbang/esteira/nucleo/scripts/`) continuam Bash, portados do CNABLens, e só
orquestram. Formulário do épico → labels, Definition of Ready, tarefas e dependências, modelo de branches, título
Conventional Commits, versão SemVer, changelog Keep a Changelog, zonas sensíveis e caminhos do artefato ficam em
`.bigbang/bb/pipeline.py`, com testes unitários. Os filtros usam `gh --jq` e as listas são TSV tratado em Bash: a
esteira não depende de `jq` (os testes usam `jq` só para simular o `gh`).

Decisões que acompanham:

- **Duas chaves novas no `bigbang.toml`**, lacunas do modelo da especificação: `entrega.arquivo_versao` (o "único
  arquivo por stack" da seção 11.10, gravado pelo *Integrar release*) e `entrega.ecossistemas` (os pacotes da stack
  para o `dependabot.yml`, que não dá para inferir). Ambas são definidas em F2.
- **Campo Sprint de seleção única:** uma opção nova é criada reenviando as existentes **com o id** (o
  `ProjectV2SingleSelectFieldOptionInput` aceita `id`; sem ele o GitHub recria as opções e apaga a Sprint dos
  cartões). O encerramento renomeia a opção para `Sprint N · início → fim`, mantendo o id.
- **Relações nativas:** sub-issues (`addSubIssue`) e bloqueio (`POST /issues/{n}/dependencies/blocked_by`),
  conferidos na documentação e no schema da API em 2026-10-03.
- **Checks obrigatórios do merge:** `check` e `regras`; o `seguranca` entra no E6 (`CHECKS_OBRIGATORIOS`).
- **Ferramentas da stack na CI:** o `check` usa as versões do runner `ubuntu-24.04`; quem precisar de outra versão a
  instala em `comandos.instalar` (por exemplo com um gerenciador de versões).
- **Invariante da `develop` (seção 11.5):** testada pelo `regras` em todo PR para a `develop` (o artefato do PR tem
  de ser igual ao da `main`) e pelo portão do *Publicar sem release*.
- **Disparo entre workflows:** merges e pushes da esteira usam o `PROJETO_TOKEN`, porque eventos do `GITHUB_TOKEN`
  não disparam outros workflows.

## Consequências

### Positivas

- Regras testadas como funções puras; scripts finos, testados com um `gh` falso com estado.
- Um projeto muda os caminhos do artefato num lugar só, e todos os portões obedecem.

### Negativas

- Dois idiomas de código na esteira (Bash e Python). Mitigação: a fronteira é clara (`bb esteira`).
- Duas chaves além do modelo da especificação (documentadas aqui e no modelo).

## Referências

- Especificação, seções 11, 14.1, 14.2 e 14.5.
- GitHub: *Issue dependencies* (REST) e *Projects* (GraphQL), consultados em 2026-10-03.
