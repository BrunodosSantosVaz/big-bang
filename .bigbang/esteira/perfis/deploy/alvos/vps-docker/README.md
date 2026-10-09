# Alvo `vps-docker`

Um servidor acessado por SSH que roda Docker Compose (seção 14.4 da [especificação](https://github.com/BrunodosSantosVaz/big-bang/wiki/Especificacao)).
O script [`scripts/alvo.sh`](scripts/alvo.sh) tem as operações `publicar`, `checar`, `migrar`, `saude` e `voltar`.

## O que o projeto fornece

- `deploy/compose.yaml`, a partir de [`.bigbang/modelos/compose.yaml`](../../../../../modelos/compose.yaml): cada
  serviço publicado (`deploy.servicos`, padrão `app`) com `image: ${BB_IMAGEM_<SERVICO>}`, o serviço de migração
  (`deploy.servico_migrar`, perfil com o mesmo nome) e, se quiser, o de pré-checagem (`deploy.servico_checar`).
  Serviços fora de `deploy.servicos` (banco, proxy) nunca são recriados pelo deploy.
- No servidor, os segredos da aplicação (por exemplo em `/opt/<slug>/<ambiente>/app.env`), descritos no runbook.

## O que o dono configura em cada ambiente do GitHub (`staging` e `producao`)

| Nome | Tipo | Conteúdo |
| --- | --- | --- |
| `VPS_HOST`, `VPS_USUARIO`, `VPS_PORTA` | variáveis | o servidor (porta padrão 22) |
| `VPS_PASTA` | variável (opcional) | padrão `/opt/<slug>/<ambiente>` |
| `VPS_CHAVE_SSH` | segredo | chave privada de um usuário só de deploy |
| `VPS_KNOWN_HOSTS` | variável | a linha da chave do servidor (`ssh-keyscan`, conferida com o dono): nunca aceita no primeiro contato |
| `VPS_DOCKER_SUDO` | variável (opcional) | `true` quando o usuário de deploy roda `sudo -n docker` (sudo sem senha só para o docker) |
| `VPS_ENV_ARQUIVO` | variável (opcional) | arquivo de ambiente no servidor, passado com `--env-file` a todo comando do compose |
| `REGISTRY_USUARIO`, `REGISTRY_TOKEN` | variável e segredo (opcionais) | leitura de imagem privada no GHCR |

## O que o projeto configura no `bigbang.toml` (`[deploy]`, todas opcionais)

| Chave | Padrão | Para quê |
| --- | --- | --- |
| `servicos` | `["app=Dockerfile"]` | uma imagem por serviço (`servico=Dockerfile`, construída a partir da raiz) |
| `plataformas` | `["linux/amd64"]` | arquitetura do servidor (`linux/arm64` para ARM) |
| `caminho_saude` | `"/api/health"` | endereço do health check (começa com `/`) |
| `servico_migrar` | `"migrar"` | serviço que roda a migração |
| `servico_checar` | `""` | serviço de pré-checagem do servidor, rodado antes da migração |

## Garantias

- A imagem é sempre referenciada **pelo digest**; uma tag é recusada. Com vários serviços, o conjunto inteiro é
  publicado junto, e *Voltar versão* restaura o conjunto da Release.
- A pré-checagem e a migração rodam com as imagens novas **antes** da troca; se falharem, a versão no ar não muda.
  Voltar versão nunca desfaz migração (DAD-02).
- `imagem.anterior.env` guarda a referência anterior no servidor.
- Testado contra um servidor em contêiner (`.bigbang/tests/test_alvo_vps.py`, job `alvo vps-docker` da CI).
