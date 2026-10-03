# Padrão de testes (TST)

Regras obrigatórias para todo sistema do Big Bang. **DEVE**/**NÃO DEVE** são obrigação; **DEVERIA** só se descumpre
com ADR; **PODE** é opção. Exceção só com ADR listado em `docs/padroes/excecoes.md`. Veja a
[tabela de rastreio](README.md).

### TST-01 · Pirâmide de testes

- **Regra:** O sistema DEVE ter testes de unidade (domínio e aplicação), integração (infraestrutura com banco real em
  contêiner), contrato (OpenAPI), aceite (por regra de negócio) e ponta a ponta só nos fluxos principais.
- **Por quê:** Muitos testes rápidos na base e poucos lentos no topo dão confiança sem travar a esteira.
- **Certo:** 300 de unidade, 60 de integração, 40 de aceite, 5 de ponta a ponta.
- **Errado:** só testes de ponta a ponta, lentos e instáveis.
- **Referência:** Test Pyramid (Mike Cohn; Martin Fowler).
- **Verificação:** comandos `testes` e `testes_aceite` no job `check` e item do `bb-revisor-pr`.

### TST-02 · Testes de aceite travados

- **Regra:** Testes de aceite DEVEM ficar em `tests/aceite/<épico>/`, com o ID da RN no nome, e DEVEM ficar travados
  depois de mesclados.
- **Por quê:** O teste de aceite é o contrato com o dono; quem implementa não pode mudar o contrato.
- **Certo:** `tests/aceite/57-estoque/test_rn0042_blocks_order_without_stock.py`.
- **Errado:** a IA ajusta a asserção do teste de aceite para a tarefa passar.
- **Referência:** Acceptance Test-Driven Development; especificação, seção 11.7.
- **Verificação:** check `regras` (trava de aceite).

### TST-03 · Teste antes

- **Regra:** O teste de aceite DEVE existir antes da tarefa; o teste de regressão DEVE vir antes da correção do bug.
- **Por quê:** Teste escrito depois tende a confirmar o código, não o requisito.
- **Certo:** commit 1 com o teste que falha; commit 2 com a correção.
- **Errado:** correção e teste no mesmo commit, sem prova de que o teste falhava.
- **Referência:** Test-Driven Development (Kent Beck); Fabio Akita, *github-resolution*.
- **Verificação:** fluxo do épico (as tarefas esperam o teste) e check `regras` (regressão).

### TST-04 · Testes determinísticos

- **Regra:** Testes DEVEM ser determinísticos: sem rede externa, com relógio controlado e com dados fictícios (nunca
  dados reais).
- **Por quê:** Teste que falha "às vezes" ensina todo mundo a ignorar a CI.
- **Certo:** relógio injetado em `2026-01-15T12:00:00Z`; gateway falso.
- **Errado:** teste que chama a API real do banco e usa `now()`.
- **Referência:** xUnit Test Patterns (Gerard Meszaros); LGPD (minimização).
- **Verificação:** item do `bb-revisor-pr`.

### TST-05 · Cobertura mínima

- **Regra:** As camadas de domínio e aplicação DEVEM ter cobertura mínima de `testes.cobertura_minima` (padrão 80%).
- **Por quê:** Cobertura não prova qualidade, mas cobertura baixa prova que falta teste.
- **Certo:** relatório de cobertura com 86% em `domain/` e `application/`.
- **Errado:** cobertura alta inflada por testes sem asserção.
- **Referência:** Google Testing Blog, *Code Coverage Best Practices*.
- **Verificação:** comando `cobertura` no job `check`.

### TST-06 · Autorização com dois usuários

- **Regra:** Cada recurso DEVE ter teste com dois usuários, um tentando ler e alterar o dado do outro (`SEG-IA-03`).
- **Por quê:** É a falha mais comum em API (BOLA) e a mais fácil de passar despercebida.
- **Certo:** usuário B recebe 404 ao pedir `/api/orders/<id do pedido de A>`.
- **Errado:** só testes com um usuário.
- **Referência:** OWASP API Security Top 10 API1 (BOLA).
- **Verificação:** item do `bb-revisor-pr` e auditoria de segurança.

### TST-07 · Limite de requisições com 429

- **Regra:** Endpoints com limite de requisições DEVEM ter teste que passa do limite e espera 429 (`SEG-IA-05`).
- **Por quê:** Limite sem teste é removido sem ninguém perceber.
- **Certo:** seis tentativas de login seguidas → a sexta recebe 429.
- **Errado:** limite configurado e nunca exercitado.
- **Referência:** OWASP API Security Top 10 API4 (consumo irrestrito de recursos).
- **Verificação:** item do `bb-revisor-pr` e `bb checklist producao`.

### TST-08 · Cenários de concorrência e falha parcial

- **Regra:** Onde há dinheiro ou estado crítico, DEVE haver testes de concorrência, falha parcial e repetição.
- **Por quê:** Duas requisições simultâneas ou uma queda no meio podem cobrar duas vezes ou perder dinheiro.
- **Certo:** dois pagamentos com a mesma chave de idempotência ao mesmo tempo → uma única cobrança.
- **Errado:** só o caminho feliz testado num fluxo de pagamento.
- **Referência:** Fabio Akita (testes de cenário onde há dinheiro); `SEG-21`.
- **Verificação:** revisão humana (zona sensível) e item do `bb-revisor-pr`.

### TST-09 · Teste de arquitetura

- **Regra:** O sistema DEVE ter teste automatizado das camadas (`ARQ-01`).
- **Por quê:** A arquitetura se degrada um import por vez; o teste impede.
- **Certo:** contrato do import-linter proibindo `domain` → `infra`.
- **Errado:** regra de camadas só no documento.
- **Referência:** ArchUnit; import-linter; dependency-cruiser.
- **Verificação:** comando `arquitetura` no job `check`.

### TST-10 · Teste instável não vai para quarentena sem issue

- **Regra:** Teste instável NÃO DEVE ir para quarentena sem issue; DEVE ser corrigido, ou removido com aprovação do
  dono.
- **Por quê:** Quarentena sem dono vira teste desligado para sempre.
- **Certo:** `skip(reason="#130 flaky on timezone")` com a issue aberta e prazo.
- **Errado:** `@skip` sem motivo.
- **Referência:** Google Testing Blog, *Flaky Tests at Google*.
- **Verificação:** item do `bb-revisor-pr`.

### TST-11 · Nunca enfraquecer teste

- **Regra:** Ninguém DEVE enfraquecer teste para passar: remover asserção, pular teste ou aumentar tempo limite sem
  motivo.
- **Por quê:** Teste enfraquecido esconde o defeito que deveria pegar.
- **Certo:** corrigir o código até o teste passar.
- **Errado:** trocar `assertEqual(total, 100)` por `assertTrue(total)`.
- **Referência:** Regra de ferro 7 do `AGENTS.md`; `COD-12`.
- **Verificação:** item do `bb-revisor-pr` e check `regras` (trava de aceite).

### TST-12 · Testes de fumaça no staging

- **Regra:** Os testes de fumaça DEVEM ser marcados para rodar no staging a cada deploy.
- **Por quê:** Ninguém homologa um ambiente que não sobe.
- **Certo:** `npm run test:smoke` contra `url_staging` na candidata.
- **Errado:** deploy no staging sem nenhuma verificação automática.
- **Referência:** Fabio Akita (staging com smoke test).
- **Verificação:** workflow da candidata no perfil deploy (`deploy.smoke`).
