# Alvo `vps-docker`

Um servidor acessado por SSH que roda Docker Compose (seção 14.4 da [especificação](../../../../../docs/especificacao.md)).
O script [`scripts/alvo.sh`](scripts/alvo.sh) tem as quatro operações: `publicar`, `migrar`, `saude` e `voltar`.

## O que o projeto fornece

- `deploy/compose.yaml`, a partir de [`.bigbang/modelos/compose.yaml`](../../../../../modelos/compose.yaml): o serviço
  `app` com `image: ${BB_IMAGEM}` e o serviço `migrar` (a mesma imagem, o comando de migração, perfil `migrar`).
- No servidor, os segredos da aplicação (por exemplo em `/opt/<slug>/<ambiente>/app.env`), descritos no runbook.

## O que o dono configura em cada ambiente do GitHub (`staging` e `producao`)

| Nome | Tipo | Conteúdo |
| --- | --- | --- |
| `VPS_HOST`, `VPS_USUARIO`, `VPS_PORTA` | variáveis | o servidor (porta padrão 22) |
| `VPS_PASTA` | variável (opcional) | padrão `/opt/<slug>/<ambiente>` |
| `VPS_CHAVE_SSH` | segredo | chave privada de um usuário só de deploy |
| `VPS_KNOWN_HOSTS` | variável | a linha da chave do servidor (`ssh-keyscan`, conferida com o dono): nunca aceita no primeiro contato |
| `REGISTRY_USUARIO`, `REGISTRY_TOKEN` | variável e segredo (opcionais) | leitura de imagem privada no GHCR |

## Garantias

- A imagem é sempre referenciada **pelo digest**; uma tag é recusada.
- A migração roda com a imagem nova **antes** da troca; voltar versão nunca desfaz migração (DAD-02).
- `imagem.anterior.env` guarda a referência anterior no servidor.
- Testado contra um servidor em contêiner (`.bigbang/tests/test_alvo_vps.py`, job `alvo vps-docker` da CI).
