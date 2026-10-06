# ADR-0019: Migração na inicialização para SQLite no Tsuru

- **Situação:** aceita (banco leve e entrega completa autorizados pelo dono; #187).
- **Data:** 2026-10-06.

## Contexto e problema

O dono recusou PostgreSQL para o ranking do Snake. SQLite usa arquivo persistente local, que um job Tsuru
independente não monta automaticamente. A entrega por job da ADR-0018 continua adequada para bancos externos.

## Decisão e justificativa

Adicionar `TSURU_MIGRACAO=inicializacao` por ambiente, com `job` como padrão compatível. A pré-checagem de migração
confirma identidade da app e no máximo uma unidade, registrando `migration=pending`. Não inventar resultado de
migração. A imagem imutável executa migração transacional/idempotente no volume montado antes de ouvir a porta;
falha encerra a unidade. Publicação continua por digest e evento verificável, seguida de saúde que consulta o
banco, smoke e scanners. O volume e os recursos pertencem à instalação explícita do projeto.

## Consequências

Não há servidor de banco nem job separado para SQLite. O sistema testa inicialização, falha, arquivo durável e
migrações; o framework testa estratégia, pré-checagem, proveniência e rejeições. Uma réplica permanente admite
sobreposição temporária no rollout do mesmo nó/volume, exigindo transações, timeout de lock e esquema compatível.
Rollback não desfaz esquema: o inicializador antigo confere migrações já aplicadas. Disponibilidade da versão
anterior depende da estratégia de rollout, e a entrega não é considerada saudável antes das verificações.

Veja o [runbook](../deploy-tsuru.md). A plataforma Node.js pode ser instalada para outros sistemas; esta versão
promove imagens OCI da CI e não afirma oferecer upload de fontes pelo alvo Tsuru.
