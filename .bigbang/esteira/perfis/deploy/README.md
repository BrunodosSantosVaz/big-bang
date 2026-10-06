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

## Disponível nesta etapa

| Categoria | Implementado | Reservado (não gera esteira) |
| --- | --- | --- |
| Alvo | `vps-docker` | `tsuru`, `personalizado`, `aws`, `paas` |
| Formato | `imagem` (identidade por digest) | `pacote`, `estatico` (identidade por SHA-256) |

Este é o contrato inicial do [épico #174](https://github.com/BrunodosSantosVaz/big-bang/issues/174). A composição de
credenciais, preparação e acesso à rede será implementada na #176; personalizado na #177; Tsuru na #178; pacotes
e arquivos na #179; serviço AWS concreto na #180. A presença de uma reserva documenta a intenção, sem prometer
funcionalidade. Entrega por hashes permanece recusada enquanto o perfil implementar somente imagens.

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
São informações do contrato; sua injeção nas Actions ainda pertence à #176. As Actions atuais de VPS preservam
seu comportamento nesta etapa.

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
descrevem o contrato existente; o consumo dinâmico na esteira e a entrega de novos formatos serão implementados
nas tarefas seguintes. Não se deve marcar um formato novo como implementado antes dessa integração e seus testes.

## Composição e extensão

O gerador compõe, nesta ordem: núcleo → perfil deploy → `artefatos/<formato>/arquivos/` → `alvos/<alvo>/arquivos/`.
A camada posterior pode substituir um arquivo da anterior. Trocar o alvo remove arquivos gerados que ficaram
obsoletos; arquivos do projeto e workflows sem marca gerada permanecem próprios do projeto.

Novos adaptadores **do framework** chegam por PR e release do Big Bang, com contrato, implementação, testes,
documentação e checksums. O projeto consumidor recebe a versão com `bb atualizar`; não edita `.bigbang/`.
Personalizações do projeto terão o alvo `personalizado`, quando estiver implementado.

Destinos AWS precisam de adaptadores concretos por serviço. Acesso via VPN ou runner próprio é um aspecto da rede,
não um formato de artefato nem um provedor. Produção e rollback mantêm os portões humanos existentes; nenhuma
reserva autoriza criar infraestrutura ou mudar esses portões.
