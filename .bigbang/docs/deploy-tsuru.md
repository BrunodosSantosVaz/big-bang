# Entrega no Tsuru existente

O alvo `tsuru` importa uma imagem OCI construída pela CI e referenciada por digest. Não faz build remoto de
Dockerfile nem instala servidor. Oferece migração por job manual ou na inicialização da aplicação, para um
arquivo SQLite persistente. Compatibilidade pesquisada no código oficial **Tsuru v1.32.0**; o servidor do
piloto usa essa API em ARM64. A homologação do Snake é uma evidência separada dos testes do adaptador.

## Configuração

Em F2 ou mediante ADR posterior, selecione `entrega.alvo = "tsuru"`, `deploy.artefato = "imagem"` (padrão) e
`deploy.servicos = ["app=Dockerfile"]`. Esta implementação aceita **um serviço por aplicação**; outra combinação
é recusada antes da geração. `deploy.plataformas` define a arquitetura da imagem, independentemente do alvo.
O Node.js/runtime já vai dentro da imagem: deploy por imagem não exige instalar plataforma Node no Tsuru.
A plataforma existente pode atender ao cadastro da app; o runtime executado é o da imagem importada.
O caminho e as URLs de saúde continuam no `[deploy]`; `BASE_PATH` do sistema deve corresponder à rota pública.
Após alterar a decisão, rode `bb gerar`.

Configure os nomes abaixo em **cada ambiente** do GitHub, com apps/jobs distintos em staging e produção:

| Tipo | Nome | Valor esperado |
| --- | --- | --- |
| Variável | `TSURU_TARGET` | Origem HTTPS da API, sem caminho, credencial, query ou fragmento |
| Variável | `TSURU_APP` | Nome da aplicação existente daquele ambiente |
| Variável | `TSURU_JOB_MIGRAR` | Nome do job manual de migração existente daquele ambiente |
| Variável | `TSURU_MIGRACAO` | `job` (padrão quando vazio) ou `inicializacao` |
| Segredo | `TSURU_TOKEN` | Token da automação restrito à aplicação/job/equipe necessários |

Token, senha, conexão de banco e credencial do registry nunca entram no TOML, front, histórico ou logs.
O token precisa ler aplicação/job/eventos, fazer deploy por imagem e disparar o job; não precisa criar servidor,
aplicações ou jobs. Prepare a credencial e os recursos explicitamente com o dono, respeitando suas autorizações.
As imagens privadas exigem acesso do Tsuru ao registry: configure esse acesso no servidor, sem imprimir o token.
O piloto público pode usar GHCR público.

## SQLite e migração na inicialização

Escolha `TSURU_MIGRACAO=inicializacao` quando o banco é um arquivo montado na aplicação. Não configure um job
independente: o volume da app não é automaticamente montado nele. Prepare um volume persistente separado por
ambiente, uma única réplica da app, backup e permissão de escrita para o usuário sem root da imagem.

A imagem deve executar as migrações transacionais/idempotentes no mesmo arquivo do servidor **antes de abrir a
porta**. Falha de migração encerra o processo; a imagem não pode servir com banco parcialmente migrado. Configure
`deploy.caminho_saude` e a readiness do Tsuru para o endpoint que consulta o banco (por exemplo `/api/ready`).
Comprove esse comportamento com testes de arquivo, migração, falha de inicialização e reinício do sistema.

Neste modo, `migrar` é uma pré-checagem: confirma identidade da app e no máximo uma unidade atual. O recibo registra
`migration=pending`, pois a migração acontecerá no processo novo. `publicar` importa a imagem por digest e espera
o evento verificável; saúde/readiness, smoke e ZAP continuam obrigatórios. Evento de deploy não é recibo de um job
de migração. A entrega completa só é confirmada depois da saúde e dos testes da aplicação.

Rollout pode sobrepor temporariamente a unidade antiga e a nova no mesmo nó e volume RWO. Use transações,
`busy_timeout` e migrações compatíveis com a versão anterior; não escale SQLite para réplicas independentes.
Rollback não dispara job nem desfaz o esquema. O inicializador da imagem antiga confere suas migrações já
aplicadas, sem reaplicá-las. Restaurar arquivo é uma operação separada de manutenção com backup.

## Preparar o sistema, sem recriar o Tsuru

1. Confirme API, pool, arquitetura, recursos e rota do Tsuru existente.
2. Prepare apps distintos, configuração e banco por ambiente; a aplicação não pode usar a credencial de migração.
3. Crie o job **manual** de cada ambiente, com comando revisado que executa a migração dentro da imagem do
   sistema. Configure nele a conexão/credencial de migração e limite de tempo; a aplicação permanece com seu
   próprio papel de banco. Jobs agendados, sem comando ou já executando são recusados pelo adaptador.
4. Configure a rota/base path e saúde antes da primeira candidata. A app pode existir sem unidades antes do
   primeiro deploy; o job e a configuração precisam existir para a migração prévia.
5. Configure vars/secret no ambiente e escolha runner público ou `deploy.runner` para rede privada. Um script de
   VPN aprovado pode usar `deploy.preparar_rede`; falha de rede interrompe o deploy. Nenhuma preparação roda em
   simulação.

Esses passos pertencem à instalação do projeto. O adaptador não os executa implicitamente ao escolher um alvo.
Não altere recursos de outras aplicações no servidor.

## Ordem e prova de entrega

`migrar` lê o job, verifica modo manual/comando e ausência de execução ativa, importa a **nova imagem por digest**
e consulta o evento do Tsuru. O evento precisa concluir sem erro, identificar o job correto e registrar a mesma
imagem de origem. Depois, confere a referência interna importada e o comando, registra as identidades anteriores,
dispara o job e espera **uma execução nova** chegar a `succeeded`. `trigger` aceito, sucesso antigo, execução
concorrente, troca de imagem, erro e timeout não autorizam a publicação.

`publicar` importa o mesmo digest na app existente e verifica seu evento de sucesso/origem. O Tsuru pode espelhar
a imagem no registry interno e atribuir outra referência; o recibo registra **origem, referência interna e evento**.
Isso comprova o import por imagem e não promete igualdade entre nomes/digests do registry interno e do GHCR.
O recibo da migração inclui também a identidade da execução. Corpos/logs completos da API não são impressos.

Depois vêm saúde, smoke e ZAP no staging. Candidatas compartilham a trava `bb-staging`; produção/rollback mantêm
concorrência protegida e aprovação humana. No modo job, falha de migração impede a publicação da app. No modo
inicialização, falha impede a nova unidade de ficar pronta; não prometa disponibilidade da versão anterior sem
conferir a estratégia de rollout configurada no servidor.

`voltar` lê `imagem.txt` de uma release estável e reimporta seu digest, **sem executar nem desfazer migrações**.
Use migrações de expansão/contração; a saúde continua obrigatória no workflow de rollback. Retomar publicação
após um erro exige conferir eventos e estado no Tsuru; timeout não é prova de que o servidor não executou o pedido.

## Pesquisa e validação

- [Deploy por imagem](https://docs.tsuru.io/tsuru_client/tsuru_deploy/).
- [Job manual e limite de tempo](https://docs.tsuru.io/tsuru_client/tsuru_job_create/).
- [Tokens de automação](https://docs.tsuru.io/tsuru_client/tsuru_token_create/).
- [Rotas reais da API v1.32.0](https://github.com/tsuru/tsuru/blob/v1.32.0/api/server.go): o trigger é
  `POST /1.13/jobs/{name}/trigger`; comentários antigos de handlers não substituem o registro de rotas.
- [Evento do deploy](https://github.com/tsuru/tsuru/blob/v1.32.0/api/deploy.go),
  [dados do evento](https://github.com/tsuru/tsuru/blob/v1.32.0/types/event/event.go) e
  [estado da execução](https://github.com/tsuru/tsuru/blob/v1.32.0/provision/kubernetes/job.go).

Testes do framework cobrem proveniência, falha/timeout/identidade de execução, primeiro deploy, rejeição de tag,
limites de serviço, geração por alvo, ordem da esteira, saúde finita, rollback e proteção de credencial em redirects.
A prova de homologação real deve registrar URL, SHA, digest, evento/job e saúde no projeto consumidor.
