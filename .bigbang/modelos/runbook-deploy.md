# Runbook: publicar em produção (perfil deploy)

<!-- Salve como docs/operacao/deploy.md e complete os campos do projeto. DOC-09. -->

## Antes

- O épico ou bug está `homologado` no staging, com a candidata `vX.Y.Z-rc.N`.
- O botão **Publicar em produção** com `simular=true` mostra "Portão aprovado".

## Publicar

1. Rode **Publicar em produção** com a versão e `simular=false`.
2. Aprove o ambiente `producao` em Actions (só o dono).
3. A esteira roda a pré-checagem (se houver), migra com as imagens novas, troca a versão pelos **mesmos digests** da
   candidata e confere o caminho de saúde (`deploy.caminho_saude`, padrão `/api/health`).

## Conferir

- `curl -fsS <url_producao><caminho_saude>`
- A Release `vX.Y.Z` (Latest) registra os digests em `imagem.txt` (uma linha `servico=imagem@sha256:…` por serviço).
- No servidor: `cat /opt/<slug>/producao/imagem.env` (a anterior fica em `imagem.anterior.env`).

## Se o health check falhar

Siga o runbook [voltar versão](voltar-versao.md). Migrações não são desfeitas: o esquema continua compatível com a
versão anterior (expandir-e-contrair, DAD-02).

## O que o servidor precisa

- Docker Engine com Docker Compose v2 (perfis e vários `--env-file`).
- Um usuário só de deploy, com a chave pública de `VPS_CHAVE_SSH`. Se ele não estiver no grupo `docker`, ligue
  `VPS_DOCKER_SUDO=true` e permita **só o docker** sem senha (`/etc/sudoers.d/deploy`:
  `deploy ALL=(root) NOPASSWD: /usr/bin/docker`).
- A pasta `VPS_PASTA` (padrão `/opt/<slug>/<ambiente>`), onde o alvo grava `compose.yaml` e `imagem.env`.
- Rede externa do proxy reverso (se o `compose.yaml` usar uma) criada antes do primeiro deploy:
  `docker network create <rede>`.
- Servidor ARM64: `deploy.plataformas = ["linux/arm64"]` (a candidata constrói para essa arquitetura).

## Segredos da aplicação

<!-- Onde ficam (ex.: /opt/<slug>/producao/app.env, ou o arquivo de VPS_ENV_ARQUIVO, que o alvo passa a todo comando
     do compose), quem tem acesso, como trocar (rotação: SEG-15). A pré-checagem (deploy.servico_checar) confere que
     as variáveis obrigatórias existem antes de migrar. -->
