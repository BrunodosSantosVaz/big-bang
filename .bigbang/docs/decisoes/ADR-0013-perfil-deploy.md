# ADR-0013: Perfil deploy e alvo vps-docker

- **Situação:** aceita
- **Data:** 2026-10-04
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

A seção 14.4 pede uma imagem construída uma vez, publicada no GHCR com digest, implantada no staging com migração,
smoke e ZAP, e a mesma imagem em produção, com migração antes da troca, health check depois e um *Voltar versão* que
nunca desfaz migração. O primeiro alvo é `vps-docker` (SSH + Docker Compose).

## Decisão e justificativa

- **Digest em tudo:** a candidata grava `imagem@sha256:…` em `imagem.txt` na pre-release; a produção publica esse
  digest e a Release `vX.Y.Z` o registra de novo. O alvo recusa tag. *Voltar versão* lê o digest da Release escolhida.
- **Alvo `vps-docker`** (`alvos/vps-docker/scripts/alvo.sh`): quatro operações (`publicar`, `migrar`, `saude`,
  `voltar`). O projeto descreve o app em `deploy/compose.yaml` (serviço `app` com `image: ${BB_IMAGEM}` e serviço
  `migrar` no perfil `migrar`); o alvo copia o arquivo, guarda a referência anterior e troca a versão. A chave do
  servidor vem de `VPS_KNOWN_HOSTS`: **nunca se aceita a chave no primeiro contato**. A chave SSH vai para um arquivo
  temporário, nunca para a linha de comando. Os segredos da aplicação ficam no servidor (runbook).
- **Candidata:** testes; imagem uma vez (`docker build`, push com a tag `vX.Y.Z-rc.N`, digest do registro); Trivy
  fixado por versão e SHA-256, reprovando vulnerabilidade alta ou crítica (SEG-19); staging pelo alvo (migrar,
  publicar, saude), smoke com `BB_URL` e ZAP baseline com a imagem fixada por digest (só regra FAIL reprova); SBOM
  CycloneDX e atestado da imagem (repositório público); pre-release e homologação.
- **Produção** (`perfis/deploy/scripts/promover.sh`, chamado pelo portão comum do *Publicar em produção*): migrar →
  publicar → saude; falha no health check vira **alerta** e não interrompe a limpeza (o dono decide sobre voltar).
- **Teste:** `test_alvo_vps.py` roda o ciclo inteiro contra um servidor em contêiner (sshd + Docker CLI sobre o socket
  do host, registro local): migra e publica a 1.0.0, migra a 2.0.0 com a 1.0.0 ainda no ar, publica a 2.0.0 e volta
  para a 1.0.0 sem desfazer a migração. Roda num job próprio da CI do Big Bang.
- `aws` e `paas` seguem sem implementação, como manda a especificação: entram quando o primeiro sistema precisar, com
  as mesmas quatro operações.

## Atualização (1.2.0): lacunas do deploy real (#112–#115)

Comparando o alvo com o deploy real de um sistema do dono (VM ARM64, duas imagens, banco no mesmo compose, `sudo
docker`, segredos num env-file do servidor e health em outro endereço), o alvo ganhou, sem mudar o padrão:

- **Várias imagens:** `deploy.servicos` (`servico=Dockerfile`); a candidata constrói uma imagem por serviço
  (`deploy.imagem-<servico>` quando há mais de um) e grava `servico=imagem@sha256:…` por linha em `imagem.txt`.
  O alvo publica o conjunto inteiro e *Voltar versão* restaura o conjunto. O banco nunca é recriado.
- **ARM64:** `deploy.plataformas` vai para `docker buildx build --platform`; com mais de uma plataforma, o digest é o
  do índice. Escolha: **QEMU no runner x86** (funciona em repositório público e privado, sem configuração; build mais
  lento). Runner ARM nativo (`ubuntu-24.04-arm`) é mais rápido e grátis só em repositório público: fica como opção
  do projeto, trocando o `runs-on` do job `imagem` por ADR do projeto.
- **Health configurável:** `deploy.caminho_saude` (padrão `/api/health`), validado no esquema.
- **Servidor:** `VPS_DOCKER_SUDO` (`sudo -n docker`), `VPS_ENV_ARQUIVO` (env-file extra), `deploy.servico_migrar` e
  `deploy.servico_checar` (pré-checagem antes da migração; se falhar, nada muda no ar).
- **SBOM** de cada imagem gerado pelo Trivy já fixado, e atestado de procedência de todas por `subject-checksums`.

## Consequências

### Positivas

- O que o dono homologou no staging é, pelo digest, o que vai para produção; voltar versão é publicar um digest antigo.

### Negativas

- A validação no **servidor real do dono** (critério do E9) ainda depende de ele fornecer o servidor e configurar
  as variáveis e os segredos dos ambientes `staging` e `producao`.
- O destino precisa de Docker Compose v2 com suporte a `--env-file` e perfis.

## Referências

- Especificação, seção 14.4; DAD-02, DAD-03, SEG-19, OBS-04.
- Trivy https://github.com/aquasecurity/trivy (v0.75.0) · ZAP https://www.zaproxy.org (2.17.0)
