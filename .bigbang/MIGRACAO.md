# Migração entre versões do Big Bang

O que muda em cada versão do framework e o que um projeto precisa fazer ao atualizar com `bb atualizar`.
SemVer: versão **maior** = o projeto precisa agir, e a seção diz como. A camada do projeto nunca é tocada.
Cada seção tem "O que muda" e "O que o projeto precisa fazer" ("Nada." quando não há passo manual).

## [2.0.1] - 2026-10-09

### O que muda

O validador da Wiki confere também o destino externo dos badges Markdown aninhados, além da imagem.
Página ou âncora ausente bloqueia entrega; badges válidos e validação da imagem são preservados.
Não adiciona dependências, não executa prosa e não altera os procedimentos privados.

### O que o projeto precisa fazer

Nada.

### Compatibilidade com a migração anterior

Projetos já migrados atualizam pelo pacote oficial e geram os arquivos conforme o procedimento habitual.
Se está migrando de antes da 2.0.0, o validador confiado da branch de destino pode ainda ler STACK.md e RNs
locais. Preserve somente esses contratos efetivamente consumidos, classifique a exceção transitória no manifesto,
atualize a branch confiada e então retire os contratos por outro PR com CI e revisão. Não desligue portões,
não altere aceites e não declare migração concluída enquanto a ponte existir. A Wiki é a fonte documental oficial.

## [2.0.0] - 2026-10-09

### O que muda

Documentação de sistemas públicos passa a usar a GitHub Wiki como fonte oficial. Privados mantêm os arquivos
locais e procedimentos anteriores. O README público é breve e dá acesso à Wiki, Discussions e painéis públicos.
CLI, guarda da stack, regras de negócio, checklist, geração e changelog resolvem o destino pela visibilidade.
O manifesto funcional `.bigbang-docs.json` fixa os commits da Wiki, o inventário de módulos e a matriz de
rastreabilidade. Propostas documentais são revisadas com o PR; publicação não usa force e rejeita HEAD concorrente.
Produção e Publicar sem release não concluem sem cobertura, links e publicação confirmada, também no Flash.

Discussions é padrão da comunidade; a IA responsável publica o primeiro post de modo idempotente. Painéis
públicos são conferidos separadamente, e painéis existentes exigem auditoria antes da mudança de visibilidade.
A automação não muda permissões de edição. Social preview é preparado no design kit e o upload é registrado
como confirmado ou pendente conforme a capacidade real da sessão.

### O que o projeto precisa fazer

Em público: confirme Wiki habilitada, Home criada e acesso de escrita; inventarie documentos e funcionalidades
antes de migrar. Preserve configurações e documentos antigos. Prepare `.bigbang-docs.json`, propostas da Wiki,
conteúdo funcional completo, navegação, imagens, requisitos e testes reais. No checklist, mova autorizações de
comandos para `.bigbang-producao.json`; comandos vindos da Wiki nunca são executados. Registre a referência
de ambiente na Wiki. Revise, publique por fast-forward e valide o HEAD; somente após confirmação retire os
documentos anteriores e corrija referências no PR. Atualize README, Discussions, painéis e Social preview.

Em privado: não migre documentos nem publique painéis. Preserve o padrão atual; adote Discussions no escopo
autorizado e mantenha a primeira publicação factual. `bb atualizar 2.0.0 --confirmo-migracao` exige a confirmação
dos passos acima; autorização já concedida na conversa vale para a execução, sem outro pedido redundante.

Framework e Actions não alteram automaticamente os caminhos do artefato. Se apenas estes componentes e a
documentação mudaram, conclua por Publicar sem release, sem recompilar nem versionar o aplicativo.

## [1.5.5] - 2026-10-09

### O que muda

O próprio framework executa a faxina após CI/publicação e fechamento de issues, além da recuperação diária.
A exclusão aguarda a tag da ponta da main, release estável com pacote/hash, conteúdo sincronizado e CI de
push verde nos SHAs exatos de main/develop. O checkout privilegiado usa apenas main, nunca código de PR.

Nos consumidores, `bb gerar` instala o botão Faxina com recuperação diária e simulação manual, complementando
a limpeza feita ao final das publicações reais e do Encerrar. Simulações desses fluxos não disparam faxina real.
Só branches incorporadas com trabalho concluído são
apagadas; main/develop/tags, PRs abertos e commits exclusivos ficam preservados. Encerrar agora falha se
a faxina apontar sobras, sem desfazer uma publicação já realizada. Resolva cada ponto e execute novamente.

Essa atualização da esteira não altera os caminhos do artefato nem exige versão nova do aplicativo.
Use `bb atualizar 1.5.5` e Publicar sem release após CI/revisão; o pacote do framework tem versão própria,
hash e atestação, sem substituir as releases anteriores.

### O que o projeto precisa fazer

Nada.

## [1.5.4] - 2026-10-08

### O que muda

Os índices das skills e do perfil compilado descrevem os recursos já implementados: atualização oficial por
hash/atestação e promoção dos mesmos binários da candidata. O README, o guia de contribuição e o relatório da
entrega distinguem produção comprovada, histórico de homologação e critérios de campo ainda pendentes.
Nenhum comando, adaptador, teste ou portão muda nesta atualização documental.

### O que o projeto precisa fazer

Nada.

### Atualização opcional

Use `bb atualizar 1.5.4` para obter os índices corrigidos. Projetos em 1.5.3 preservam o mesmo comportamento
de Flash, Tsuru, verificação por arquitetura e avanço pós-merge; não precisam de atualização para executar esses recursos.

## [1.5.3] - 2026-10-07

### O que muda

Mesclar PR recebe `PROJETO_OWNER`, `PROJETO_PLANEJAMENTO` e `PROJETO_EXECUCAO` das variáveis públicas do
repositório, como o botão Criar branches já recebia. Isso corrige a falha pós-merge que interrompia a criação
da próxima branch e o avanço automático até a integração. Aprovação, checks do SHA exato e publicação conservam
os mesmos portões; a correção não mescla nem publica um PR sem aprovação.

### O que o projeto precisa fazer

Nada.

### Atualização opcional

Use `bb atualizar 1.5.3` para regenerar o workflow oficial. Em um épico já afetado, o PR pode ter sido mesclado
mesmo que o run tenha falhado; confira seu estado antes de repetir ações. Criar branches, primeiro simulação,
é a recuperação canônica da próxima branch após o merge. Esta atualização não reexecuta merges anteriores.

## [1.5.2] - 2026-10-07

### O que muda

A candidata de deploy passa `--platform` ao Trivy para cada serviço e plataforma de `deploy.plataformas`, tanto
na varredura de vulnerabilidades quanto no SBOM CycloneDX. Isso permite gerar o SBOM ARM64 num runner AMD64 e
impede que a segunda arquitetura escape da varredura. Falha do scanner ou da leitura da configuração interrompe
a etapa. Cada serviço publica `sbom-<servico>.linux-<arquitetura>.json`; `sbom-<servico>.json` continua disponível
e representa a primeira plataforma configurada. Candidata, atestação e promoção conservam o digest do índice,
sem reconstruir a imagem nem substituir a referência por um digest filho.

### O que o projeto precisa fazer

Nada.

### Atualização opcional

Use `bb atualizar 1.5.2` para obter a correção oficial e regenerar os arquivos. Candidatas cujo SBOM falhou
precisam de uma nova execução com a camada atualizada; esta correção não publica a candidata por conta própria.

## [1.5.1] - 2026-10-07

### O que muda

`bb revisao aprovar` usa a API paginada de arquivos, que atende atualizações do framework com mais de 300 arquivos.
Renomes conferem o caminho antigo e o novo. Lista incompleta ou patch de aceite ausente interrompem o registro.
As decisões de revisão e o modo continuam vindo da branch de destino; nenhum portão foi dispensado.

### O que o projeto precisa fazer

Nada.

### Atualização opcional

Use `bb atualizar 1.5.1` para obter a correção oficial e regenerar os arquivos.

## [1.5.0] - 2026-10-06

### O que muda

- `bb alvos` descobre os contratos de destinos e formatos instalados e distingue implementados de reservados.
- `deploy.artefato` é opcional, com `imagem` como padrão. O gerador compõe também a camada do formato e recusa
  destinos incompletos ou combinações incompatíveis antes de escrever arquivos.
- **Actions conforme o alvo:** staging, produção e rollback recebem só os nomes de variáveis e segredos do
  contrato escolhido. O formato seleciona os scripts da construção e da candidata. `deploy.runner` e
  `deploy.preparar_rede` permitem configurar acesso a rede privada; simulações não preparam rede nem autenticam.
- **Tsuru existente:** adaptador para API v1.32.0, uma aplicação com um serviço OCI por digest e
  `TSURU_MIGRACAO=job` por padrão. O job manual por ambiente confere importação, imagem e uma execução nova
  de migração antes da publicação. `inicializacao` admite SQLite em volume persistente: a pré-checagem registra
  `migration=pending`, e o inicializador da imagem migra antes de abrir a porta. Saúde/readiness consulta o banco
  e os testes posteriores comprovam a entrega. Uma réplica permanente pode ter sobreposição transitória no
  rollout do mesmo volume, exigindo transações e compatibilidade do esquema. Rollback reimporta o digest
  estável sem desfazer migrações. Veja o [runbook](https://github.com/BrunodosSantosVaz/big-bang/wiki/Historico-bigbang-docs-deploy-tsuru).
- **Modo Flash:** `projeto.modo` é opcional (`padrao` por omissão), escolhido em `bb init --modo flash` ou depois
  por ADR e `bb gerar`. Testes continuam escritos antes do código; `bb testes` executa os afetados por
  dependências após concluir as alterações, ou tudo para estrutura, primeira entrega, major/minor e produção.
  Sem seletor da stack ou base confiável, roda tudo. Candidata exige a execução verde de `bb-ci.yml` no SHA
  exato; produção fica vinculada ao SHA dos testes completos e conserva aprovação humana.
- **Release em repositório privado:** a conferência de ancestralidade usa as referências já obtidas pelo
  checkout completo, sem novo `git fetch` após a retirada das credenciais.
- `aws` e `paas` eram reservas sem implementação e agora sua seleção é recusada explicitamente.
  `personalizado`, `pacote` e `estatico` também continuam reservados; não há entrega universal anunciada.

### O que o projeto precisa fazer

Nada.

### Adoção opcional e compatibilidade

Projetos `vps-docker` e compilados conservam o comportamento, com modo padrão e runner público por omissão.
Use `bb atualizar 1.5.0` para obter o pacote verificado e regenerar a camada gerada; não edite `.bigbang/` nem
workflows gerados no projeto.

Para adotar Flash, registre a decisão em ADR, escolha `projeto.modo = "flash"` e rode `bb gerar`.
Configure um seletor de dependências testado em `comandos.testes_alterados`; sem ele, a suíte continua completa.
Para adotar Tsuru, prepare apps/credenciais distintos por ambiente e, no modo padrão, os jobs manuais.
Para SQLite, prepare volume, backup, inicializador e readiness conforme o runbook, antes de alterar o alvo por
PR e ADR. A plataforma Node.js do servidor é uma preparação separada; esta versão promove imagens OCI por
digest, sem upload de fontes. Um script de rede pertence ao projeto e precisa de aprovação/revisão antes de publicação.

Projetos que selecionaram uma reserva sem adaptador funcional devem consultar `bb alvos` e escolher uma
integração implementada, ou aguardar sua implementação. Os testes do framework não substituem a homologação
real: o consumidor registra URL, SHA, digest, eventos/execução de migração e saúde.


## [1.4.0] - 2026-10-05

### O que muda

- **Link de aprovação para quem supervisiona (#153):** ao disparar *Publicar em produção*, *Publicar sem release* ou
  *Voltar versão* com `simular=false`, a IA roda `link-aprovacao.sh <workflow.yml>` e entrega ao humano que aprova
  o link direto do run e os passos (*Review deployments* → `producao` → *Approve and deploy*). A regra de ferro 2 do
  `AGENTS.md` e a skill `bb-entregar-epico` passam a exigir isso.
- Os três workflows de publicação deixam o mesmo bloco de instruções no resumo do job `conferir` quando
  `simular=false`.
- A produção continua sempre com o clique de um humano no ambiente `producao`.

### O que o projeto precisa fazer

Nada.

## [1.3.1] - 2026-10-05

### O que muda

- *Integrar release* aceita vários bugs numa release só: `bug=61,64` (uma candidata, uma homologação, uma
  publicação), como já acontecia com os épicos da sprint.

### O que o projeto precisa fazer

Nada.

## [1.3.0] - 2026-10-05

### O que muda

- **Arquivos de comunidade (DOC-16):** todo sistema tem `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md` e `SECURITY.md`,
  criados pelo `bb init` a partir de `.bigbang/modelos/comunidade/`, ou por `bb esteira comunidade` em sistemas já
  fundados. A CI (`bb esteira documentacao`) cobra os três.
- **Ícone global (DOC-17):** todo sistema tem `docs/design/icone.svg`, criado no design kit (F3), mostrado no
  protótipo e aprovado junto com ele, e usado em tudo que leva ícone (app, favicon, README). A CI cobra o arquivo
  depois do `DESIGN.md` ou da primeira release. O modelo de README abre com o ícone.
- O próprio Big Bang ganhou código de conduta, guia de contribuição, política de segurança e ícone.

Sistemas já fundados: no PR da atualização, a IA roda `bb esteira comunidade`, completa os arquivos e cria o
`docs/design/icone.svg` a partir do logo do `DESIGN.md` (e aplica o ícone no app, se ele ainda usar o padrão da
plataforma, numa tarefa ou bug próprio).

### O que o projeto precisa fazer

Nada.

## [1.2.1] - 2026-10-05

### O que muda

- **Bug sem branch:** o `bb assumir` de uma issue com label `bug` (ou `hotfix`) cria a branch `bugfix/<n>-<slug>`
  (ou `hotfix/`) a partir da `main` quando ela ainda não existe; antes, a posse falhava porque nada criava a branch.
- **Ordem de regressão em projetos Android/JVM:** o check do PR de bug reconhece como teste os arquivos em
  `src/test/`, `src/androidTest/`, `src/testFixtures/`, `__tests__/` e os nomes `XTest`, `XTests`, `XSpec`, `XIT`
  (Kotlin, Java, Scala, Groovy, Swift, C#); antes, um teste Kotlin no primeiro commit era tratado como correção.

### O que o projeto precisa fazer

Nada.

## [1.2.0] - 2026-10-05

### O que muda

- **Perfil deploy, alvo `vps-docker`, pronto para um deploy real (E9, #112–#115):**
  - várias imagens por sistema (`deploy.servicos = ["api=apps/api/Dockerfile", "web=apps/web/Dockerfile"]`):
    a candidata constrói uma por serviço, `imagem.txt` registra `servico=imagem@sha256:…` por linha, o alvo publica
    o conjunto junto e *Voltar versão* restaura o conjunto; serviços fora da lista (banco) nunca são recriados;
  - servidor ARM64: `deploy.plataformas = ["linux/arm64"]` (buildx com QEMU; ADR-0013);
  - health check em outro endereço: `deploy.caminho_saude` (padrão `/api/health`);
  - `VPS_DOCKER_SUDO=true` (`sudo -n docker`), `VPS_ENV_ARQUIVO` (env-file do servidor),
    `deploy.servico_migrar` e `deploy.servico_checar` (pré-checagem antes da migração; se falhar, nada muda no ar).
- Todas as chaves novas são opcionais, com o comportamento anterior como padrão: um projeto com um serviço `app` e
  `${BB_IMAGEM}` no compose continua funcionando sem mudança.
- SBOM de cada imagem gerado pelo Trivy fixado; atestado de procedência por `subject-checksums`.
- Correção: a migração agora roda com stdin fechado (`run -T </dev/null`); antes, um comando depois dela no mesmo
  script remoto podia ser engolido.

### O que o projeto precisa fazer

Nada.

## [1.1.0] - 2026-10-05

### O que muda

- **README sempre completo e atual (DOC-15):** modelo novo (`.bigbang/modelos/README-sistema.md`) com selos, imagem
  real e as seções Estado atual, Para que serve, Recursos, Instalação, Como usar, Para desenvolvedores, Versões e
  releases, Segurança e privacidade, Limitações, Contribuindo e Licença. Depois da primeira release, a CI
  (`bb esteira documentacao`) reprova README sem essas seções, sem o selo da CI, ou que ainda diga "Fundação",
  "em construção" ou "(a preencher)". O checklist de documentação de cada épico e as skills cobram o README.
- **Faxina (`faxina.sh`):** no *Encerrar*, no *Publicar em produção* e no *Publicar sem release*, apaga as branches
  mescladas cujo trabalho acabou (inclusive `framework/*` e `fundacao/*`) e lista o que sobrou (branches fora do
  padrão, issues abertas em versão publicada, PRs parados, posses). O encerramento da sprint e a retrospectiva
  conferem README, documentação e repositórios auxiliares sem uso.
- `AGENTS.md`: ao terminar qualquer alteração, documentar e atualizar o README; nada fica para trás.
- README do próprio Big Bang reescrito.

Sistemas que já publicaram uma versão: a CI passa a cobrar as seções do README; no PR da atualização, a IA completa
o `README.md` pelo modelo novo.

### O que o projeto precisa fazer

Nada.

## [1.0.0] - 2026-10-05

### O que muda

- Primeira versão estável: validada num sistema real, do zero a produção (piloto ScreenFakeCam,
  `.bigbang/docs/piloto-screenfakecam.md`).
- Kanban: o grupo de concorrência inclui a ação e a label do evento (eventos diferentes da mesma issue não se
  descartam mais).
- *Regras do PR* julga com a ponta atual da branch de destino, não com o `base.sha` congelado do evento.
- Tarefa de correção com título cortado em palavra inteira; `bb assumir` nomeia a pasta pelo repositório principal;
  `bb liberar` explica que a posse se libera antes de remover a pasta.

### O que o projeto precisa fazer

Nada.

## [0.12.0] - 2026-10-05

### O que muda

- *Integrar release* aceita vários épicos numa release: `epico=36,37` ou `epico=sprint` (todos os épicos em
  andamento da sprint). Um épico que depende de outro da mesma release não espera (ADR-0015).
- `bb-rodar-sprint` pergunta ao dono, no início de cada sprint, se a entrega é por sprint ou por épico, e trabalha
  em paralelo as tarefas desbloqueadas.

### O que o projeto precisa fazer

Nada.

## [0.11.7] - 2026-10-04

### O que muda

- *Regras do PR* no PR `release/*`: a trava de `tests/aceite/` não se aplica (o conteúdo já passou por ela nos PRs
  para o épico) e a rastreabilidade usa o `testes.padrao_teste` que vem na release.
- `docs/operacao/checklist-producao.md` nasce na F5 e está no checklist de documentação do épico; o *Integrar release*
  avisa quando ele falta.

### O que o projeto precisa fazer

Nada.

### Projetos já fundados sem o checklist de produção

Crie `docs/operacao/checklist-producao.md` a partir de `.bigbang/modelos/checklist-producao.md` antes da próxima
publicação.

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
