# Entrega no Tsuru existente

O alvo `tsuru` importa uma imagem OCI construída pela CI e referenciada por digest. Não faz build remoto de
Dockerfile nem instala servidor. Compatibilidade pesquisada no código oficial **Tsuru v1.32.0**; o servidor do
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
| Segredo | `TSURU_TOKEN` | Token da automação restrito à aplicação/job/equipe necessários |

Token, senha, conexão de banco e credencial do registry nunca entram no TOML, front, histórico ou logs.
O token precisa ler aplicação/job/eventos, fazer deploy por imagem e disparar o job; não precisa criar servidor,
aplicações ou jobs. Prepare a credencial e os recursos explicitamente com o dono, respeitando suas autorizações.
As imagens privadas exigem acesso do Tsuru ao registry: configure esse acesso no servidor, sem imprimir o token.
O piloto público pode usar GHCR público.

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
concorrência protegida e aprovação humana. Falha de migração deixa a aplicação em sua versão anterior.

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
