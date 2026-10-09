# 17 · Modo Flash

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Flash reduz interrupções manuais e repetições de testes. **Os testes continuam escritos e revisados antes do
código**, com a mesma trava de aceite. Uma tarefa continua tendo issue, posse, branch, PR e revisão independente.

## Escolher no início ou mudar depois

Na Fundação: `bb init --nome "Meu sistema" --modo flash` (mais as escolhas de dono, repositório e licença).
O modo fica registrado na issue F0. Sem opção, o padrão é `padrao`.

Em projeto existente, com decisão do dono registrada em ADR: coloque `modo = "flash"` na seção `[projeto]` de
`bigbang.toml` e rode `bb gerar`. A escolha persiste nas próximas sessões e o AGENTS gerado passa a orientá-la.
Para voltar, use `modo = "padrao"` e regenere. Projetos antigos sem a chave continuam no padrão.
Labels e tags de release não são fonte alternativa de configuração: o marcador permanente é o TOML.

## Diferenças

| Etapa | Padrão | Flash |
| --- | --- | --- |
| Escrever testes | Antes da implementação | Antes da implementação |
| Implementar | Executar comandos completos por tarefa | Concluir as alterações antes da rodada de testes afetados |
| Autorizações | Portões por etapa | Reutilizar a autorização do plano; consultar só decisões novas, conflitos e ações sem autorização |
| Revisão | IA; zona sensível troca para humana | IA independente; pedido explícito de revisão humana e trabalho crítico permanecem humanos |
| Testes de mudanças comuns | Unidade, integração, aceite e cobertura completos | Seletor da stack, com dependências, aceite e cobertura afetados |
| Mudança estrutural | Suíte completa | Suíte completa |
| Release major/minor, primeira release | Suíte completa | Suíte completa |
| Patch | Suíte completa | Afetados, salvo alteração estrutural |
| Candidata | Repete testes | Espera e reutiliza a execução verde de `bb-ci.yml` no mesmo SHA; não aceita outro commit |
| Produção | Ordem e aprovação humana | Ordem, suíte completa e aprovação humana, inclusive patches; publicação vinculada ao SHA testado |
| Lint, tipos, arquitetura, scanners, documentação | Obrigatórios | Obrigatórios |

## Seleção de testes

`bb testes --base origin/develop` mostra a decisão e executa os comandos. `--simular` só mostra o plano;
`--completo` força toda a suíte. `--fase producao` sempre executa tudo. Na candidata, a CI lê a versão da branch
`release/X.Y.Z` e compara a major/minor com a versão estável anterior. Sem base ou versão anterior confiável, roda tudo.

Configure `[comandos] testes_alterados` em F2 conforme a stack. Esse comando deve selecionar testes que importam
direta ou indiretamente os arquivos alterados, incluindo unidade, integração e aceite, e verificar a cobertura das
camadas afetadas no mesmo limite do projeto. **Não basta executar só os arquivos de teste editados.**

O comando recebe `BB_BASE_TESTES` (SHA verificado) e `BB_ARQUIVOS_ALTERADOS` (caminho de arquivo JSON com a lista
de alterações, incluindo arquivos apagados, renomeados, locais e novos). Leia essa lista como dados, sem `eval` ou
expansão em shell. Um seletor desconhecido, vazio ou sem garantia de dependências exige a suíte completa; não use
`passWithNoTests` para esconder uma seleção incorreta. O seletor pertence ao projeto e precisa de teste e revisão.

O framework força testes completos para mudanças de esteira, framework, decisões centrais, dependências/lockfiles,
configuração, migrações, infraestrutura e empacotamento. `[testes] caminhos_estruturais` permite **acrescentar**
caminhos específicos da stack; nunca retirar os padrões obrigatórios.

Concentre a rodada depois do código concluído. Use o resultado da CI do mesmo commit na revisão e na candidata;
não repita a suíte por hábito. Nova alteração, falha, ambiente diferente ou evidência insuficiente justifica nova
rodada. Smoke, saúde, migração e scanner do ambiente continuam rodando durante a entrega.

## Limites e adoção no próprio framework

Flash não autoriza inventar decisões de produto/stack/design, mudar teste congelado, dispensar scanner, instalar
dependência não aprovada, publicar produção ou aprovar o próprio código. Refinamento/protótipo/homologação pedidos
ao dono permanecem explícitos; uma autorização já dada não deve ser solicitada outra vez.

O próprio Big Bang usa seu processo leve, sem Fundação e sem TOML de sistema. O dono autorizou Flash em 06/10/2026,
registrado no ADR-0017: execução contínua do escopo, revisão independente por IA e uso da CI como evidência. Mudanças
do framework/gerador/esteira são estruturais, portanto a CI completa permanece obrigatória. AWS e novos formatos
ficam para depois; a prioridade atual é Tsuru existente e a conclusão do Snake 3310.

## O que a automação faz sozinha

Registra o modo em F0, valida e gera a orientação persistente, decide a seleção de testes, exige suíte completa nos casos obrigatórios e reutiliza a CI do mesmo SHA na candidata. Mantém scanners e aprovação humana de produção.
