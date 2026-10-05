# Padrão de observabilidade (OBS)

Regras obrigatórias para todo sistema do Big Bang. **DEVE**/**NÃO DEVE** são obrigação; **DEVERIA** só se descumpre
com ADR; **PODE** é opção. Exceção só com ADR listado em `docs/padroes/excecoes.md`. Veja a
[tabela de rastreio](README.md).

### OBS-01 · Log estruturado

- **Regra:** Os logs DEVEM ser estruturados (JSON), com nível, horário UTC e ID de correlação.
- **Por quê:** Log estruturado pode ser filtrado; o ID de correlação liga todas as linhas de uma requisição.
- **Certo:** `{"level":"error","ts":"2026-10-03T14:05:00Z","correlation_id":"…","msg":"payment_failed"}`.
- **Errado:** `print("deu erro aqui")`.
- **Referência:** Twelve-Factor (logs); OpenTelemetry Logs.
- **Verificação:** item do `bb-revisor-pr`.

### OBS-02 · Endpoints de vida e prontidão

- **Regra:** A aplicação DEVE expor os endpoints de vida e prontidão (`ARQ-13`).
- **Por quê:** O deploy e o monitoramento precisam saber se a aplicação está viva e pronta.
- **Certo:** `/api/health` e `/api/ready`.
- **Errado:** nenhum endpoint de saúde.
- **Referência:** Kubernetes probes.
- **Verificação:** `bb checklist producao` e health check depois de cada deploy.

### OBS-03 · Métricas e rastreamento

- **Regra:** A aplicação DEVE ter métricas de erro, latência e saturação; DEVERIA ter rastreamento com OpenTelemetry
  quando a stack suportar.
- **Por quê:** Sem métricas, o primeiro aviso de problema é a reclamação do usuário.
- **Certo:** taxa de 5xx, p95 de latência e uso de CPU/memória por instância.
- **Errado:** nenhuma métrica além do "está no ar".
- **Referência:** Google SRE Book (quatro sinais de ouro); OpenTelemetry (https://opentelemetry.io).
- **Verificação:** item do `bb-revisor-pr` e revisão do runbook de operação.

### OBS-04 · Health check depois do deploy

- **Regra:** Todo deploy DEVE ser seguido de health check, com aviso se falhar.
- **Por quê:** Deploy que "deu certo" mas não responde precisa ser revertido na hora.
- **Certo:** a esteira consulta o caminho de saúde (`deploy.caminho_saude`, padrão `/api/health`) por até 2 minutos
  e alerta se não responder.
- **Errado:** deploy encerrado sem nenhuma verificação.
- **Referência:** Fabio Akita (staging com smoke e rollback rápido).
- **Verificação:** operação `saude` do alvo, chamada pela publicação em produção e pela candidata.

### OBS-05 · Erros capturados com contexto

- **Regra:** Erros DEVEM ser capturados com contexto, sem dado sensível.
- **Por quê:** Erro sem contexto não se reproduz; erro com dado sensível vaza.
- **Certo:** erro com rota, ID de correlação e ID do usuário (não o e-mail).
- **Errado:** erro com o corpo inteiro da requisição, incluindo a senha.
- **Referência:** OWASP Logging Cheat Sheet.
- **Verificação:** item do `bb-revisor-pr`.

### OBS-06 · Eventos de segurança registrados

- **Regra:** Os eventos de segurança DEVEM ser registrados (`SEG-14`).
- **Por quê:** Sem eles, não há como investigar um ataque nem perceber que ele está acontecendo.
- **Certo:** login falho, bloqueio, 429 e mudança de permissão no log, com ID de correlação.
- **Errado:** 429 devolvido sem nenhum registro.
- **Referência:** OWASP Top 10 A09 (falhas de log e monitoramento).
- **Verificação:** item do `bb-revisor-pr` e auditoria de segurança.
