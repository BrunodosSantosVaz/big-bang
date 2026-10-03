# Padrão de API (API)

Regras obrigatórias para todo sistema do Big Bang que expõe API. **DEVE**/**NÃO DEVE** são obrigação; **DEVERIA** só
se descumpre com ADR; **PODE** é opção. Exceção só com ADR listado em `docs/padroes/excecoes.md`. Veja a
[tabela de rastreio](README.md).

### API-01 · REST com verbos e status corretos

- **Regra:** A API DEVE ser REST: recursos no plural, verbos e status HTTP corretos.
- **Por quê:** Clientes, caches e ferramentas entendem a semântica sem documentação extra.
- **Certo:** `POST /api/orders` → `201` com `Location`; `DELETE` → `204`.
- **Errado:** `POST /api/deleteOrder` → `200 {"ok":false}`.
- **Referência:** RFC 9110 (HTTP Semantics).
- **Verificação:** item do `bb-revisor-pr` e teste de contrato.

### API-02 · Contrato OpenAPI 3.1

- **Regra:** A API DEVE ter contrato OpenAPI 3.1 como fonte (gerado do código ou escrito antes, decidido em F2),
  versionado no repositório.
- **Por quê:** Uma fonte única evita documentação divergente do comportamento.
- **Certo:** `docs/api/openapi.yaml` conferido contra as rotas na CI.
- **Errado:** contrato escrito uma vez e nunca atualizado.
- **Referência:** OpenAPI 3.1 (https://spec.openapis.org/oas/v3.1.0).
- **Verificação:** teste de contrato no job `check`.

### API-03 · Erros em Problem Details

- **Regra:** Os erros DEVEM usar o formato *Problem Details* (RFC 9457).
- **Por quê:** Formato único de erro simplifica o front e os clientes.
- **Certo:** `{"type":"…/estoque-insuficiente","title":"Estoque insuficiente","status":409}`.
- **Errado:** `{"erro":"deu ruim"}` com status 200.
- **Referência:** RFC 9457.
- **Verificação:** teste de contrato e item do `bb-revisor-pr`.

### API-04 · Paginação com limite máximo

- **Regra:** Listas DEVEM ter paginação com limite máximo; filtros e ordenação DEVEM estar documentados.
- **Por quê:** Lista sem limite derruba o servidor e vaza dados em massa.
- **Certo:** `GET /api/orders?limit=50&cursor=…`, com `limit` máximo de 100.
- **Errado:** `GET /api/orders` devolvendo 200 mil registros.
- **Referência:** OWASP API Security API4 (consumo irrestrito de recursos).
- **Verificação:** item do `bb-revisor-pr`.

### API-05 · Idempotência em operação cara ou financeira

- **Regra:** Criação cara ou operação que move dinheiro DEVE aceitar chave de idempotência.
- **Por quê:** Redes repetem requisições; sem chave, o cliente é cobrado duas vezes.
- **Certo:** cabeçalho `Idempotency-Key` guardado por 24 h.
- **Errado:** botão "Pagar" clicado duas vezes gera duas cobranças.
- **Referência:** IETF draft *The Idempotency-Key HTTP Header Field*; `SEG-21`.
- **Verificação:** teste de cenário (`TST-08`) e revisão humana (zona sensível).

### API-06 · Versão no caminho para terceiros

- **Regra:** Quando a API for consumida por terceiros, a versão DEVE ficar no caminho (`/api/v1`).
- **Por quê:** Mudança incompatível não pode quebrar clientes que você não controla.
- **Certo:** `/api/v1/orders` mantida enquanto `/api/v2/orders` é adotada.
- **Errado:** mudar o formato da resposta sem aviso para integradores.
- **Referência:** Microsoft REST API Guidelines (versionamento).
- **Verificação:** item do `bb-revisor-pr`.

### API-07 · Datas e dinheiro

- **Regra:** Datas DEVEM estar em ISO 8601 UTC; dinheiro DEVE ser decimal em texto ou inteiro em centavos, sempre com
  a moeda.
- **Por quê:** Ponto flutuante perde centavos e data sem fuso é ambígua.
- **Certo:** `{"total":{"valor":"1234.56","moeda":"BRL"},"criado_em":"2026-10-03T14:05:00Z"}`.
- **Errado:** `{"total":1234.5600000001,"data":"03/10/2026"}`.
- **Referência:** ISO 8601; ISO 4217.
- **Verificação:** teste de contrato e item do `bb-revisor-pr`.
