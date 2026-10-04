# Migração entre versões do Big Bang

O que muda em cada versão do framework e o que um projeto precisa fazer ao atualizar com `bb atualizar`.
SemVer: versão **maior** = o projeto precisa agir, e a seção diz como. A camada do projeto nunca é tocada.
Cada seção tem "O que muda" e "O que o projeto precisa fazer" ("Nada." quando não há passo manual).

## [0.11.6] - 2026-10-04

### O que muda

- *Mesclar PR* considera só a execução mais recente de cada check obrigatório: um `regras` que rodou de novo depois
  da label de decisão (ou foi cancelado pela concorrência) não segura mais o merge.

### O que o projeto precisa fazer

Nada.

## [0.11.5] - 2026-10-04

### O que muda

- `kanban.sh`: editar um épico sem mudar as respostas do formulário não falha mais.
- Fundação: o *Publicar sem release* vem logo depois do PR que instala a esteira (F5), antes do épico Esqueleto
  andante; sem a esteira na `main`, os workflows de issue e os botões não rodam.

### O que o projeto precisa fazer

Nada.

## [0.11.4] - 2026-10-04

### O que muda

- `seguranca.sh`: o build da varredura de segredo no pacote passa pelo `comando.sh` (pula sem código do artefato, como
  a CI) e também confere `*/build/outputs` (pacotes de módulos Gradle, como o APK).

### O que o projeto precisa fazer

Nada.

## [0.11.3] - 2026-10-04

### O que muda

- `comando.sh` (CI): enquanto nenhum caminho de `entrega.caminhos_artefato` existe no repositório, os comandos da
  stack são pulados com aviso. O PR da F5 instala a esteira sem código do artefato, que chega pelo épico Esqueleto
  andante (invariante 11.5).

### O que o projeto precisa fazer

Nada.

## [0.11.2] - 2026-10-04

### O que muda

- Perfil compilado: o passo de build da candidata recebe os segredos de assinatura `BB_ASSINATURA_ARQUIVO`,
  `BB_ASSINATURA_SENHA`, `BB_ASSINATURA_ALIAS` e `BB_ASSINATURA_SENHA_CHAVE` (opcionais).
- `configurar-repositorio.sh` lista só os segredos do dono que ainda faltam (pelo nome), incluindo os de assinatura no
  perfil compilado.

### O que o projeto precisa fazer

Nada.

### Para assinar no perfil compilado

Crie os segredos `BB_ASSINATURA_*` e use-os no comando `compilado.build_<sistema>` (processo 14).

## [0.11.1] - 2026-10-04

### O que muda

- `configurar-repositorio.sh`: antes da esteira (F5), os rulesets saíam com a regra `non_fast_forward` repetida e o
  GitHub recusava os três (HTTP 422). Agora vão sem a regra de checks; a simulação não mostra mais `BrokenPipeError`.
- `criar-paineis.sh`, `criar-labels.sh` e `configurar-repositorio.sh` recusam repositório fora de `dono/repo`.
- `bb atualizar` cria a label `revisao-humana` se ainda não existir (antes da F4), antes de enviar a branch.

### O que o projeto precisa fazer

Nada.

### Se os rulesets falharam na F4

Rode de novo `.bigbang/scripts/configurar-repositorio.sh dono/repo` depois de atualizar.

## [0.11.0] - 2026-10-04

### O que muda

- Perfil compilado aceita o sistema `android` (runner Linux; candidata `.apk`/`.aab`).
- Guarda da stack lê o Gradle moderno (catálogo `gradle/libs.versions.toml`, bundles, `platform(...)`) e reprova a
  linha de dependência que não consegue ler, em vez de ignorá-la.
- `bb init` mantém os comentários do `bigbang.toml` na mesma coluna.

### O que o projeto precisa fazer

Nada.

### Projetos Gradle

Se a guarda passar a apontar dependências que antes não via, inclua-as na tabela do `STACK.md` pelo
`bb-nova-tecnologia`.

## [0.10.2] - 2026-10-04

### O que muda

- O job `regras` lê os arquivos do PR pela API paginada: o `gh pr diff` recusa PR com mais de 300 arquivos, como o
  de uma atualização do framework. Arquivo de `tests/aceite/` sem trecho de diff (grande demais) reprova a trava.

### O que o projeto precisa fazer

Nada.

### Vindo de uma versão anterior à 0.10.2

O job `regras` roda com os scripts da `develop`, ainda antigos, e pode reprovar o PR da atualização com
"diff exceeded the maximum number of files (300)". Revise o PR e mescle com o bypass de administrador; os PRs
seguintes já usam o script novo.

## [0.10.1] - 2026-10-04

### O que muda

- O passo de quem vem de uma versão anterior à 0.10.0 saiu de "O que o projeto precisa fazer": o `bb atualizar`
  o lia como passo manual e parava pedindo confirmação.

### O que o projeto precisa fazer

Nada.

## [0.10.0] - 2026-10-04

### O que muda

- Releases do framework com `bigbang-vX.Y.Z.tar.gz` (a pasta `.bigbang/`) e `.sha256`.
- `bb atualizar [versão]`: troca `.bigbang/` numa branch `framework/vX.Y.Z`, gera, verifica e abre o PR.

### O que o projeto precisa fazer

Nada.

### Vindo de uma versão anterior à 0.10.0

Essas versões ainda não têm `bb atualizar`. Rode uma vez o `bb` do pacote novo, na raiz do sistema, com a árvore
limpa (troque `0.10.0` pela versão desejada; daí em diante, use só `bb atualizar`):

```bash
gh release download v0.10.0 --repo BrunodosSantosVaz/big-bang --pattern 'bigbang-v0.10.0.tar.gz*' --dir /tmp/bb
cd /tmp/bb && sha256sum -c bigbang-v0.10.0.tar.gz.sha256 && cd -
gh attestation verify /tmp/bb/bigbang-v0.10.0.tar.gz --repo BrunodosSantosVaz/big-bang
tar -xzf /tmp/bb/bigbang-v0.10.0.tar.gz -C /tmp/bb
python3 /tmp/bb/.bigbang/bin/bb.py --raiz . atualizar 0.10.0
```

## [0.9.0] - 2026-10-04

### O que muda

- Perfil deploy com o alvo vps-docker, candidata no staging, produção pelo digest e Voltar versão.

### O que o projeto precisa fazer

Nada.

## [0.8.0] - 2026-10-04

### O que muda

- As 20 skills, os hooks do Claude Code e `configurar-repositorio.sh`.

### O que o projeto precisa fazer

Nada.

## [0.7.0] - 2026-10-04

### O que muda

- Posse de tarefas por várias IAs (`bb assumir`, `bb liberar`).

### O que o projeto precisa fazer

Nada.

## [0.6.0] - 2026-10-04

### O que muda

- Trava de aceite, rastreabilidade, guarda da stack, segurança, CodeQL, `bb decisao`, `bb revisao aprovar`,
  `bb checklist producao`.

### O que o projeto precisa fazer

Nada.

## [0.5.0] - 2026-10-04

### O que muda

- Perfil compilado: candidata, promoção sem recompilar e tarefa de correção.

### O que o projeto precisa fazer

Nada.

## [0.4.0] - 2026-10-04

### O que muda

- Núcleo da esteira e as chaves `entrega.arquivo_versao` e `entrega.ecossistemas`.

### O que o projeto precisa fazer

Nada.

## [0.3.0] - 2026-10-03

### O que muda

- CLI `bb` (`init`, `config get`, `gerar`, `verificar`).

### O que o projeto precisa fazer

Nada.

## [0.2.0] - 2026-10-03

### O que muda

- Padrões obrigatórios e `AGENTS.base.md`.

### O que o projeto precisa fazer

Nada.

## [0.1.0] - 2026-10-03

### O que muda

- Primeira versão: estrutura, processo, modelos e ADRs.

### O que o projeto precisa fazer

Nada.
