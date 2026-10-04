# ADR-0009: Perfil compilado: candidata, promoção e correção

- **Situação:** aceita
- **Data:** 2026-10-04
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

A especificação (seção 14.3) pede uma candidata `vX.Y.Z-rc.N` com os binários de cada sistema, SHA256SUMS, SBOM e
atestado, e uma publicação que promove **os mesmos binários** sem recompilar. O CNABLens faz isso com nomes, sistemas
e comandos de build fixos, e leva a release para a `develop` antes da produção — o que o Big Bang proíbe (invariante
da seção 11.5).

## Opções consideradas

1. Copiar o workflow do CNABLens com parâmetros.
2. **Um contrato de build mínimo por sistema, nomes e matriz calculados pelo `bb`, e a promoção como cópia dos bytes
   baixados da candidata.**

## Decisão e justificativa

Escolhida: **opção 2**.

- **Contrato de build:** `compilado.build_<sistema>` deixa **exatamente um arquivo** em `$BB_SAIDA` (`dist/<sistema>`)
  e pode ler `BB_VERSAO`, `BB_RC` e `BB_SISTEMA`. Mais de um arquivo (ou nenhum) reprova a candidata.
- **Nomes:** `<slug>-vX.Y.Z-rc.N-<sistema><ext>`; na produção o nome só perde o `-rc.N`. O SHA-256 é o mesmo, e o
  `SHA256SUMS-<sistema>.txt` é reescrito com o nome novo e conferido antes de publicar.
- **Matriz:** um runner de versão fixa por sistema (`windows-2025`, `ubuntu-24.04`, `macos-15`…), calculada pelo
  gerador (`gerado.matriz_compilado`), sem lógica no template. No Windows os scripts rodam no Git Bash.
- **Candidata só com todos os sistemas compilados**; SBOM CycloneDX (`anchore/sbom-action`, Syft) do repositório;
  atestado de procedência (`actions/attest-build-provenance`) **só em repositório público**, porque em repositório
  privado ele exige GitHub Enterprise Cloud.
- **Homologação sem tocar a `develop`:** a candidata move o épico (ou bug) para *Homologação*, tira um `reprovado`
  anterior, comenta os critérios e abre o PR `release/x.y.z → main`. A `develop` só recebe o código depois da
  produção, pela devolução da `main`.
- **Reprovação:** o botão *Tarefa de correção* cria uma tarefa nova no mesmo épico (decisão 16), com o motivo do dono,
  no milestone e na Sprint do épico. Mesclada, o épico fica completo de novo e o *Integrar release* mescla o épico na
  mesma `release/x.y.z`: a próxima candidata é a `rc.N+1`.
- **Portão de produção** (núcleo, comum aos perfis): unidade `homologado`, documentação na release, nada
  `bloqueia-producao`, `bb checklist producao` (a partir do E6), PR verde no SHA exato e sem conflito, candidata igual à
  ponta da release, changelog com a seção. A promoção é do perfil: `.bigbang/esteira/perfis/<perfil>/scripts/promover.sh`.

## Consequências

### Positivas

- O que o dono testou é, byte a byte, o que vai para produção — conferido por hash nos dois lados.
- O mesmo portão serve ao perfil deploy (E9), que só troca o `promover.sh`.

### Negativas

- O build precisa respeitar o contrato de um arquivo (um instalador ou um executável por sistema).
- Projetos privados no plano gratuito ficam sem atestado de procedência (o SHA-256 e o SBOM continuam).

## Referências

- Especificação, seções 11.6, 14.3 e 18. CNABLens: `build-release.yml`, `promover-release.sh`, `publicar-producao.sh`.
- Artifact attestations: https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations

## Validação no sandbox (2026-10-04)

No `big-bang-sandbox` no perfil compilado (Linux e Windows, build fictício): a candidata `v0.1.0-rc.1` rodou nas
Actions (testes, build nos dois sistemas, SBOM, atestado verificado com `gh attestation verify`, pre-release); o
épico foi reprovado e a tarefa de correção, mesclada, gerou a `v0.1.0-rc.2`; depois de homologado, o *Publicar em
produção* mesclou o PR da release e publicou a `v0.1.0` com **o mesmo SHA-256** da `rc.2` nos dois sistemas,
fechando issues, milestone, cartões e branches, e devolvendo a `main` à `develop`. A retomada é idempotente.

Os passos que dependem do `PROJETO_TOKEN` (homologar, tarefa de correção, integrar, publicar) rodaram com a conta do
dono fora das Actions; a aprovação real do ambiente `producao` será conferida quando o sandbox tiver o token. O
sandbox revelou e corrigiu: `grep -q` no fim de pipeline com `pipefail` (o portão não via a documentação mesclada) e a
devolução da `main` tentando branches já apagadas (faltava `--prune`).
