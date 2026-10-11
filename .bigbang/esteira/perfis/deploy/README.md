# Perfil deploy: alvos e artefatos

O destino do deploy é separado do formato do artefato. O catálogo é descoberto a partir dos contratos do
framework instalado, sem enum de provedores na CLI. Consulte `bb alvos` antes de escolher a entrega; o comando
não cria configurações, autentica, instala ferramentas nem publica nada.

```toml
[entrega]
perfil = "deploy"
alvo = "vps-docker"

[deploy]
artefato = "imagem" # opcional: é o padrão das configurações existentes
```

O trecho mostra apenas os seletores; as demais chaves do projeto continuam obrigatórias. O esquema TOML valida
a sintaxe dos nomes. `bb gerar` e `bb verificar` conferem a disponibilidade e a compatibilidade da entrega no
framework instalado, antes de planejar alterações de arquivos. Um nome sintaticamente válido não é prova de
suporte. Não há acesso ao servidor nessa conferência.

## Alvos e formatos disponíveis

| Categoria | Implementado | Reservado (não gera esteira) |
| --- | --- | --- |
| Alvo | `vps-docker`, `tsuru` (um serviço OCI por app), `personalizado` (scripts do projeto) | `aws`, `paas` |
| Formato | `imagem` (identidade por digest) | `pacote`, `estatico` (identidade por SHA-256) |

O [épico #174](https://github.com/BrunodosSantosVaz/big-bang/issues/174) entregou o catálogo (#175), composição de
credenciais, preparação e acesso à rede (#176) e Tsuru por imagem/job manual (#178), com migração na
inicialização para SQLite (#187). O alvo `personalizado` (#177) executa scripts mantidos pelo projeto usando o
manifesto de imagem imutável. Pacotes e arquivos (#179) e serviço AWS concreto (#180) continuam reservados. A
presença de uma reserva documenta a intenção, sem prometer funcionalidade. Entrega de deploy por hashes permanece
recusada enquanto o perfil implementar somente imagens; o perfil compilado conserva sua própria promoção de
binários por hashes.

O [runbook do Tsuru](https://github.com/BrunodosSantosVaz/big-bang/wiki/Historico-bigbang-docs-deploy-tsuru) documenta API, apps/jobs por ambiente, importação por
digest, `TSURU_MIGRACAO=job` (padrão) ou `inicializacao` e limites dessa implementação. Neste último modo,
a pré-checagem registra `migration=pending`; a imagem migra antes de ouvir a porta e saúde/readiness consulta
o banco. Exige uma réplica permanente, com possível sobreposição transitória no rollout do mesmo volume.

## Contrato de um alvo

Cada pasta `alvos/<nome>/` tem `alvo.toml`. Nomes usam minúsculas, números e hífens. As chaves são obrigatórias;
chaves extras e nomes duplicados são recusados.

```toml
descricao = "Servidor por SSH com Docker Compose"
situacao = "implementado" # ou "reservado"
artefatos = ["imagem"]
operacoes = ["publicar", "migrar", "saude", "voltar"] # checar é opcional
variaveis = ["VPS_HOST"]
segredos = ["VPS_CHAVE_SSH"] # somente nomes, nunca valores
```

Um alvo implementado exige `scripts/alvo.sh` presente, não vazio e dentro da própria pasta. O contrato declara
as operações; testes do adaptador devem provar que o script as cumpre, inclusive primeiro deploy, falha de
migração antes da troca e rollback sem desfazer migração (DAD-02/DAD-03, OBS-04). A presença do arquivo e dos
metadados não substitui esses testes nem a validação contra o servidor real.

Listas de variáveis/segredos só aceitam nomes de ambiente em maiúsculas e não podem repetir um nome entre si.
As Actions injetam somente essas referências, conforme o alvo. Os valores ficam nas variáveis e segredos dos
ambientes do GitHub. As Actions de VPS preservam seu comportamento para os projetos existentes.

## Alvo `personalizado`

O alvo usa somente o formato `imagem`, identificado por digest SHA-256. Configure os quatro scripts relativos à
raiz do projeto, fora de `.bigbang`; devem existir, não estar vazios e terminar em `.sh`:

```toml
[entrega]
perfil = "deploy"
alvo = "personalizado"

[deploy]
script_publicar = "scripts/deploy/publicar.sh"
script_migrar = "scripts/deploy/migrar.sh"
script_saude = "scripts/deploy/saude.sh"
script_voltar = "scripts/deploy/voltar.sh"
variaveis_personalizado = ["DEPLOY_APP"]
segredos_personalizado = ["DEPLOY_TOKEN"]
```

Os scripts recebem argumentos posicionais: `publicar` e `migrar` recebem `<ambiente> <manifesto>`, `saude` recebe
`<ambiente>`, e `voltar` recebe `<ambiente> <manifesto> <versao>`. O manifesto é um arquivo temporário com uma linha
`servico=imagem@sha256:<64 hex>` por serviço. O fluxo valida que todos os serviços aparecem uma vez e recusa tags
mutáveis, caminhos fora do projeto ou ausentes. No rollback, o framework baixa o `imagem.txt` da release escolhida
e passa o manifesto verificado; não executa migração. Falha ou ausência em qualquer script impede o próximo passo.

`variaveis_personalizado` e `segredos_personalizado` aceitam somente nomes, nunca valores. O framework injeta apenas
essas referências nos jobs de deploy do GitHub. Os scripts devem promover o manifesto recebido sem reconstruir ou
substituir a identidade imutável do artefato.

## Contrato de um formato

Cada pasta `artefatos/<nome>/` tem `artefato.toml`:

```toml
descricao = "Imagem OCI construída uma vez e promovida por digest"
situacao = "implementado"
identidade = "digest" # ou sha256, reservado até a entrega por hashes

[scripts]
construir = "esteira/perfis/deploy/scripts/candidata-imagem.sh"
candidata = "esteira/perfis/deploy/scripts/candidata-publicar.sh"
promover = "esteira/perfis/deploy/scripts/promover.sh"
```

Os caminhos são relativos a `.bigbang/`, sem `..`, caminho absoluto ou comando de shell. Os três scripts devem
existir e não ser vazios para um formato implementado. Uma reserva pode declarar `scripts = {}`. Esses caminhos
selecionam os scripts executados pela esteira. A entrega de novos formatos continua nas tarefas seguintes.
Não se deve marcar um formato novo como implementado antes dessa integração e seus testes.

## Composição e extensão

O gerador compõe, nesta ordem: núcleo → perfil deploy → `artefatos/<formato>/arquivos/` → `alvos/<alvo>/arquivos/`.
A camada posterior pode substituir um arquivo da anterior. Trocar o alvo remove arquivos gerados que ficaram
obsoletos; arquivos do projeto e workflows sem marca gerada permanecem próprios do projeto.

Novos adaptadores **do framework** chegam por PR e release do Big Bang, com contrato, implementação, testes,
documentação e checksums. O projeto consumidor recebe a versão com `bb atualizar`; não edita `.bigbang/`.
O alvo `personalizado` executa os scripts do projeto sem adicionar arquivos a `.bigbang/`.

Destinos AWS precisam de adaptadores concretos por serviço. Acesso via VPN ou runner próprio é um aspecto da rede,
não um formato de artefato nem um provedor. Produção e rollback mantêm os portões humanos existentes; nenhuma
reserva autoriza criar infraestrutura ou mudar esses portões.
