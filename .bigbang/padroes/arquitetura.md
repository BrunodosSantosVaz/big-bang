# Padrão de arquitetura (ARQ)

Regras obrigatórias para todo sistema do Big Bang. **DEVE**/**NÃO DEVE** são obrigação; **DEVERIA** só se descumpre
com ADR; **PODE** é opção. Exceção a qualquer regra só com ADR listado em `docs/padroes/excecoes.md`. A coluna de
verificação de cada regra está também na [tabela de rastreio](README.md).

### ARQ-01 · Camadas com dependências apontando para dentro

- **Regra:** O sistema DEVE ser organizado nas camadas domínio, aplicação, infraestrutura e interface (API/UI), e as
  dependências DEVEM apontar para dentro: interface → aplicação → domínio; infraestrutura implementa portas da
  aplicação ou do domínio.
- **Por quê:** Regras de negócio isoladas mudam pouco e são testáveis sem banco nem HTTP; trocar um detalhe técnico
  não quebra o negócio.
- **Certo:** `src/orders/domain/order.py` não importa nada de `src/orders/infra/`.
- **Errado:** `domain/order.py` com `from sqlalchemy import Column`.
- **Referência:** Clean Architecture (Robert C. Martin); Hexagonal Architecture (Alistair Cockburn).
- **Verificação:** teste de arquitetura da stack (import-linter, dependency-cruiser, ArchUnit ou equivalente),
  rodado pelo comando `arquitetura` no job `check` da CI.

### ARQ-02 · Domínio sem framework

- **Regra:** O domínio NÃO DEVE depender de framework, banco, HTTP, interface ou biblioteca de terceiros com efeito
  colateral.
- **Por quê:** O domínio é o que dá valor ao sistema; acoplado a um framework, envelhece junto com ele.
- **Certo:** entidade `Order` em classe pura, com validações próprias.
- **Errado:** entidade que herda de `Model` do ORM ou recebe um `Request`.
- **Referência:** Clean Architecture; Domain-Driven Design (Eric Evans).
- **Verificação:** teste de arquitetura da stack (job `check`).

### ARQ-03 · Caso de uso na aplicação

- **Regra:** Cada operação de negócio DEVE ser um caso de uso na camada de aplicação; controller, rota e tela NÃO
  DEVEM conter regra de negócio.
- **Por quê:** A mesma regra é chamada por API, tela, fila ou script sem duplicação, e é testada sem a interface.
- **Certo:** `POST /api/orders` chama `PlaceOrder.execute(command)`.
- **Errado:** o controller confere o estoque e calcula o desconto.
- **Referência:** Clean Architecture (use cases); SOLID (responsabilidade única).
- **Verificação:** item do `bb-revisor-pr` e teste de arquitetura da stack.

### ARQ-04 · Acesso a dados por portas

- **Regra:** O acesso a dados DEVE passar por portas (interfaces) definidas para dentro e implementadas na
  infraestrutura (repositórios).
- **Por quê:** Casos de uso testáveis com repositório em memória; banco trocável sem tocar no negócio.
- **Certo:** `OrderRepository` (interface) na aplicação; `SqlOrderRepository` na infraestrutura.
- **Errado:** caso de uso montando SQL ou chamando o ORM direto.
- **Referência:** Hexagonal Architecture (ports and adapters); Repository (Martin Fowler, PoEAA).
- **Verificação:** teste de arquitetura da stack e item do `bb-revisor-pr`.

### ARQ-05 · Injeção de dependência na borda

- **Regra:** As dependências DEVEM ser montadas na borda da aplicação (*composition root*); NÃO DEVE existir *service
  locator* global.
- **Por quê:** As dependências ficam explícitas nos construtores e os testes trocam implementações sem truque.
- **Certo:** `main.py` cria `SqlOrderRepository` e o entrega a `PlaceOrder(repo)`.
- **Errado:** `Container.get("orders")` chamado de dentro do caso de uso.
- **Referência:** Dependency Injection Principles, Practices, and Patterns (Seemann e van Deursen).
- **Verificação:** item do `bb-revisor-pr`.

### ARQ-06 · Front fala só com o próprio backend

- **Regra:** O front-end DEVE falar só com o backend da própria aplicação, via API; NÃO DEVE conectar direto a banco
  nem usar SDK de terceiro com credencial (ver `SEG-IA-01`).
- **Por quê:** Toda decisão de acesso e todo segredo ficam no servidor, onde o usuário não consegue alterá-los.
- **Certo:** a tela chama `GET /api/orders`; o backend fala com o banco e com o gateway de pagamento.
- **Errado:** cliente do banco com chave pública no navegador; SDK de pagamento com chave secreta no front.
- **Referência:** OWASP ASVS (arquitetura); OWASP Top 10 A01 (controle de acesso quebrado).
- **Verificação:** item do `bb-revisor-pr` e varredura de segredo no pacote do front (job `seguranca`).

### ARQ-07 · Twelve-Factor

- **Regra:** A aplicação DEVE seguir o Twelve-Factor: configuração por variável de ambiente, processo sem estado,
  logs na saída padrão, paridade entre ambientes e o **mesmo artefato** em todos os ambientes.
- **Por quê:** O artefato homologado é o publicado; só a configuração muda entre staging e produção.
- **Certo:** `DATABASE_URL` lida do ambiente; imagem promovida pelo digest.
- **Errado:** `config_prod.py` dentro do pacote; build separado para produção.
- **Referência:** The Twelve-Factor App (https://12factor.net).
- **Verificação:** a esteira (candidata e publicação usam o mesmo artefato) e item do `bb-revisor-pr`.

### ARQ-08 · UUID nas entidades expostas

- **Regra:** Entidades expostas DEVEM usar UUID (v7 quando a stack suportar); identificador sequencial NÃO DEVE
  aparecer em URL pública.
- **Por quê:** ID sequencial revela volume de negócio e facilita enumerar recursos de outros usuários.
- **Certo:** `/api/orders/0192f0c4-…`.
- **Errado:** `/api/orders/1043`.
- **Referência:** RFC 9562 (UUID); OWASP API Security Top 10 API1 (BOLA).
- **Verificação:** item do `bb-revisor-pr`.

### ARQ-09 · Integração externa atrás de adaptador

- **Regra:** Toda integração externa DEVE ficar atrás de um adaptador, com timeout, nova tentativa com espera
  crescente e, quando crítica, *circuit breaker*.
- **Por quê:** Serviço externo lento ou fora do ar não pode derrubar o sistema nem travar requisições.
- **Certo:** `PaymentGateway` (porta) e `AcmePaymentAdapter` com timeout de 5 s e 3 tentativas.
- **Errado:** chamada HTTP sem timeout dentro do caso de uso.
- **Referência:** Release It! (Michael Nygard); Hexagonal Architecture.
- **Verificação:** item do `bb-revisor-pr`.

### ARQ-10 · Monólito modular por padrão

- **Regra:** O sistema DEVE ser um monólito modular; serviço separado só com ADR.
- **Por quê:** Uma pessoa com IAs não opera bem a complexidade de rede, deploy e dados distribuídos sem necessidade.
- **Certo:** módulos `orders/`, `billing/` no mesmo processo, com fronteiras claras.
- **Errado:** três microsserviços para um sistema de dez telas, sem ADR.
- **Referência:** MonolithFirst (Martin Fowler).
- **Verificação:** revisão humana (mudança de arquitetura exige ADR aprovado pelo dono).

### ARQ-11 · Decisão arquitetural vira ADR

- **Regra:** Toda decisão arquitetural DEVE virar ADR no formato MADR, com as alternativas descartadas.
- **Por quê:** Quem chega depois (inclusive outra IA) entende o porquê e não desfaz a decisão por engano.
- **Certo:** `docs/decisoes/ADR-0007-fila-de-emails.md` com 3 opções e a escolhida.
- **Errado:** troca de biblioteca de fila explicada só na mensagem de commit.
- **Referência:** MADR (https://adr.github.io/madr/).
- **Verificação:** item do `bb-revisor-pr` e checklist da tarefa de documentação.

### ARQ-12 · Diagramas C4 em Mermaid

- **Regra:** O sistema DEVE manter diagramas C4 de contexto e contêineres (componentes quando útil) em Mermaid,
  atualizados pela tarefa de documentação.
- **Por quê:** Diagrama em texto é versionado e revisado junto com o código.
- **Certo:** `docs/arquitetura/conteineres.md` com bloco `C4Container`.
- **Errado:** imagem exportada de ferramenta externa, sem fonte.
- **Referência:** C4 model (https://c4model.com).
- **Verificação:** checklist da tarefa de documentação e item do `bb-revisor-pr`.

### ARQ-13 · Rotas sob `/api` e endpoints de saúde

- **Regra:** Em aplicação web, as rotas DEVEM ficar sob `/api`; `/api/health` (vivo) e `/api/ready` (pronto) DEVEM
  responder sem autenticação e sem expor detalhes internos.
- **Por quê:** O deploy, o monitoramento e o voltar versão dependem de saber se a aplicação está viva e pronta.
- **Certo:** `GET /api/health` → `200 {"status":"ok"}`.
- **Errado:** `/health` devolvendo versão do banco e variáveis de ambiente.
- **Referência:** Kubernetes liveness/readiness probes; checklist de produção (Pegada de Silício).
- **Verificação:** `bb checklist producao` e health check depois de cada deploy.

### ARQ-14 · Tempo em UTC

- **Regra:** Tempo DEVE ser armazenado em UTC; o fuso do usuário só é aplicado na apresentação.
- **Por quê:** Comparar, ordenar e somar datas com fusos misturados gera erro silencioso, sobretudo em horário de verão.
- **Certo:** coluna `timestamptz`; a tela converte para `America/Sao_Paulo`.
- **Errado:** `datetime.now()` sem fuso gravado no banco.
- **Referência:** ISO 8601; RFC 3339.
- **Verificação:** item do `bb-revisor-pr`.
