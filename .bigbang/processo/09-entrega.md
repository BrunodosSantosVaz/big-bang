# 09 · Entrega

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Integração, candidata, homologação e publicação acontecem **por épico** (ou por bug). O Git guarda o código; a
Release guarda o artefato; **o artefato aprovado é o publicado**.

## 1. Integrar release

Disparo: automático quando teste, tarefas e documentação do épico estão mesclados; ou botão (`epico=`, `bug=` ou
`dependencias=true`). `epico=` aceita um número, uma lista (`36,37`) ou `sprint`.

**Por épico ou por sprint** (ADR-0015): no início de cada sprint a IA pergunta ao dono como entregar.

- **Por sprint:** quando os épicos da sprint estão prontos, `epico=sprint` leva todos os épicos em *Em
  desenvolvimento* ou *Homologação* (menos os `sem-release`) numa só release: uma candidata, uma homologação (cada
  épico recebe `homologado`) e uma publicação. Um épico que depende de outro da mesma release não espera.
- **Por épico:** `epico=<n>`, um de cada vez, como antes.

- **Épico com release:** cria `release/x.y.z` a partir da `main`, mescla o `epico/…` (`--no-ff`; vários épicos, um
  merge cada), calcula a versão, escreve o changelog, cria o milestone `vX.Y.Z` com as issues dos épicos e envia →
  candidata.
- **Épico `sem-release`:** mescla o `epico/…` na `develop` e segue para *Publicar sem release*.
- Recusa épico com `tem-dependencia` cujo épico de origem não está em produção nem na mesma release.
- Conflito: nada é enviado e o épico ganha a label `conflito`.

## 2. Candidata

| Perfil | O que acontece |
| --- | --- |
| `compilado` | Pre-release `vX.Y.Z-rc.N` com os binários de cada sistema, `SHA256SUMS`, SBOM e atestado de procedência |
| `deploy` | Imagem construída uma vez, publicada no registro com digest, implantada no staging; migração, smoke test e varredura ZAP básica |

A esteira abre o PR `release/x.y.z` → `main` e o épico vai para *Homologação*.

## 3. Homologação

O dono testa **o épico inteiro, uma vez**, e põe `homologado` ou `reprovado` com o motivo (no GitHub ou dizendo na
conversa, quando a IA usa `bb decisao`).

**Reprovado:** a IA cria **uma tarefa nova de correção** no mesmo épico, com o motivo. Ela percorre o fluxo normal e
a nova integração gera a `rc.N+1` (ou um novo deploy no staging) na mesma `release/x.y.z`.

## 4. Publicar em produção

Botão `Publicar em produção` (`versao`, `simular`). Portão:

- épico `homologado`;
- documentação concluída;
- nenhuma issue `bloqueia-producao` aberta;
- `bb checklist producao` aprovado;
- PR da release sem conflito e com checks verdes no SHA exato;
- candidata existe e nada mudou desde ela;
- changelog com a seção da versão.

Com `simular=false` e **a aprovação do dono no ambiente `producao`**: mescla o PR na `main`; publica **o mesmo
artefato** da candidata (binário promovido sem recompilar, com hashes conferidos; ou a imagem pelo mesmo digest, com
migração antes da troca e health check depois); cria tag e Release `vX.Y.Z` (*Latest*); fecha as issues e o épico;
move os cartões; fecha o milestone; apaga as branches do épico e a `release/x.y.z` (com as travas); devolve a `main`
para a `develop` e para os `epico/*` abertos. É idempotente: rodar de novo só refaz o que faltou.

Quem dispara com `simular=false` entrega ao humano que aprova o **link direto do run e os passos** (*Review
deployments* → marcar `producao` → *Approve and deploy*): a IA roda `link-aprovacao.sh <workflow.yml>` e cola o
bloco; o próprio run também mostra esse bloco no resumo do job `conferir`. Vale para *Publicar em produção*,
*Publicar sem release* e *Voltar versão*.

## Versão e changelog

[SemVer](https://semver.org/lang/pt-BR/) por unidade de release. A versão sai dos títulos dos PRs do épico:

| Nos títulos | Versão sobe |
| --- | --- |
| algum `!` ou `BREAKING CHANGE` | a maior (antes da 1.0, a do meio) |
| algum `feat` | a do meio |
| só outros tipos | a última |

O changelog é gerado em português, nas seções do [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
(Adicionado, Alterado, Corrigido, Removido, Segurança), e completado pelo rascunho da tarefa de documentação. Versão
informada à mão que conflita com a classificação exige `confirmar_versao=true`. A versão do artefato fica num único
arquivo por stack (definido em F2), nunca editado à mão.

## `sem-release`

Mudança que não toca os caminhos do artefato (documentação, testes, esteira) não gera versão nem homologação. O botão
*Publicar sem release* avança a `main` até a `develop` (fast-forward), com o portão: caminhos do artefato iguais entre
`main` e `develop`, `main` contida na `develop`, CI verde na ponta da `develop`. Fecha as issues `sem-release`
concluídas.

## Feature flags

Usadas quando um épico depende de outro ainda não publicado: o épico do qual se depende pode ir para produção com a
parte incompleta desligada. Toda flag é registrada em `flags.toml` (dono, motivo, épico, criação, validade, estado por
ambiente). O *Ver painéis* lista flags ligadas em produção há mais que `flags.validade_maxima_dias` e a IA abre uma
tarefa de limpeza. O mecanismo técnico é decidido em F2.

## Voltar versão

- **Deploy:** botão *Voltar versão* (`versao`, `simular`) com aprovação no ambiente `producao`: reimplanta a imagem da
  tag anterior. **Nunca desfaz migração** — por isso migrações seguem expandir-e-contrair (`DAD-02`).
- **Compilado:** baixar a Release anterior; o runbook explica.

O *Voltar versão* é testado de verdade no esqueleto andante da Fundação.

## O que a automação faz sozinha

Integra quando o épico está completo, calcula a versão, gera o changelog, constrói a candidata uma única vez, abre o
PR da release, move os cartões e, depois do "ok" do dono, publica e limpa. O "ok" de produção é o único que o dono não
delega.
