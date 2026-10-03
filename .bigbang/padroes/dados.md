# Padrão de dados (DAD)

Regras obrigatórias para todo sistema do Big Bang que guarda dados. **DEVE**/**NÃO DEVE** são obrigação;
**DEVERIA** só se descumpre com ADR; **PODE** é opção. Exceção só com ADR listado em `docs/padroes/excecoes.md`. Veja
a [tabela de rastreio](README.md).

### DAD-01 · Migração versionada

- **Regra:** Toda mudança de esquema DEVE ser uma migração versionada pela ferramenta da stack; NÃO DEVE haver
  alteração manual no banco.
- **Por quê:** Todos os ambientes chegam ao mesmo esquema pelo mesmo caminho.
- **Certo:** `migrations/0007_add_order_status.sql`.
- **Errado:** `ALTER TABLE` rodado à mão em produção.
- **Referência:** Refactoring Databases (Ambler e Sadalage).
- **Verificação:** `bb checklist producao` (migrações do zero e da versão anterior) e revisão humana (`migrations/**` é
  zona sensível).

### DAD-02 · Expandir e contrair

- **Regra:** Mudanças de esquema DEVEM seguir expandir-e-contrair; remoção de coluna ou tabela só DEVE acontecer numa
  release posterior, com revisão humana.
- **Por quê:** Voltar versão nunca desfaz migração; a versão anterior precisa funcionar com o esquema novo.
- **Certo:** release 1 cria `email_verificado` e passa a gravar; release 2 deixa de ler `ativo`; release 3 remove
  `ativo`.
- **Errado:** renomear coluna na mesma release que muda o código.
- **Referência:** Parallel Change (Danilo Sato, martinfowler.com); Fabio Akita (migração não se desfaz com `git revert`).
- **Verificação:** item do `bb-revisor-pr` e revisão humana.

### DAD-03 · Migração em passo próprio no deploy

- **Regra:** No deploy, a migração DEVE rodar em passo próprio, antes da troca de versão.
- **Por quê:** Migração no início da aplicação corre com várias instâncias ao mesmo tempo e esconde falhas.
- **Certo:** `docker compose run --rm app migrate` e só depois a troca da imagem.
- **Errado:** a aplicação roda as migrações ao subir.
- **Referência:** Twelve-Factor (admin processes).
- **Verificação:** operação `migrar` do alvo de deploy.

### DAD-04 · Dinheiro sem ponto flutuante

- **Regra:** Dinheiro DEVE ser guardado em decimal ou inteiro em centavos, NUNCA em ponto flutuante.
- **Por quê:** `0.1 + 0.2 != 0.3`.
- **Certo:** `numeric(12,2)` ou `bigint` de centavos.
- **Errado:** `float` ou `double`.
- **Referência:** IEEE 754 (limitações de representação decimal).
- **Verificação:** item do `bb-revisor-pr`.

### DAD-05 · Datas com fuso

- **Regra:** Datas DEVEM ser guardadas com fuso (UTC).
- **Por quê:** Ver `ARQ-14`.
- **Certo:** `timestamptz`.
- **Errado:** `timestamp` sem fuso preenchido com hora local.
- **Referência:** ISO 8601; documentação do banco da stack.
- **Verificação:** item do `bb-revisor-pr`.

### DAD-06 · Restrições no banco

- **Regra:** O banco DEVE ter restrições (unicidade, chave estrangeira, não nulo), além da validação na aplicação, com
  teste de duplicidade.
- **Por quê:** Duas requisições simultâneas passam pela validação da aplicação; só o banco garante.
- **Certo:** `unique (empresa_id, numero_nota)` e teste que insere duas vezes.
- **Errado:** unicidade conferida só com `SELECT` antes do `INSERT`.
- **Referência:** Documentação do banco da stack.
- **Verificação:** teste de integração e item do `bb-revisor-pr`.

### DAD-07 · Índices para o filtro do dono

- **Regra:** Consultas filtradas por dono ou empresa DEVEM ter índice.
- **Por quê:** Todo acesso filtra pelo dono (`SEG-IA-03`); sem índice, o sistema fica lento quando cresce.
- **Certo:** `create index on orders (owner_id, created_at)`.
- **Errado:** varredura completa da tabela a cada listagem.
- **Referência:** Use The Index, Luke (Markus Winand).
- **Verificação:** item do `bb-revisor-pr`.

### DAD-08 · Backup criptografado e restauração testada

- **Regra:** O sistema DEVE ter backup automático e criptografado, com restauração testada e descrita no runbook.
- **Por quê:** Backup que nunca foi restaurado não é backup.
- **Certo:** backup diário criptografado e restauração ensaiada a cada trimestre, registrada.
- **Errado:** backup no mesmo servidor do banco, sem teste.
- **Referência:** NIST SP 800-34 (contingência); `SEG-20`.
- **Verificação:** runbook (`DOC-09`) e revisão humana.

### DAD-09 · Minimização de dados pessoais

- **Regra:** O sistema DEVE coletar só os dados pessoais necessários e excluir ou anonimizar conforme o inventário
  LGPD.
- **Por quê:** Dado que não existe não vaza.
- **Certo:** guardar só o ano de nascimento quando basta saber a maioridade.
- **Errado:** guardar foto do documento "por precaução".
- **Referência:** LGPD, art. 6º, III (necessidade).
- **Verificação:** inventário LGPD (`DOC-10`) e revisão humana.

### DAD-10 · Dados de exemplo fictícios

- **Regra:** Dados de exemplo e de teste DEVEM ser sempre fictícios.
- **Por quê:** Dado real em teste vaza por log, captura de tela e repositório.
- **Certo:** CPF gerado por algoritmo de teste; "Empresa Exemplo Ltda".
- **Errado:** cópia do banco de produção para o ambiente local.
- **Referência:** LGPD; `TST-04`.
- **Verificação:** item do `bb-revisor-pr` e Gitleaks no job `seguranca`.
