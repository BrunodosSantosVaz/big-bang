# ADR-0018: Deploy no Tsuru existente

- **Situação:** aceita (requisito do dono e execução Flash autorizados; #174/#178).
- **Data:** 2026-10-06.

## Contexto e problema

O Snake deve rodar dentro do Tsuru que o dono já mantém, sem provisionar outro servidor. A inspeção identificou
API v1.32.0, Kubernetes e ARM64. Enviar um comando de migração não comprova que ele terminou.

## Decisão e justificativa

Implementar adaptador isolado usando Python stdlib e HTTPS, sem instalar CLI/binary externo. Apps e jobs manuais
são preparados explicitamente. A CI entrega um serviço OCI por aplicação, sempre por digest. Migração importa a
imagem nova, verifica evento/proveniência e espera execução nova bem sucedida antes de publicar. Rollback usa a
imagem registrada da release e nunca migra. Eventos e identidades compõem recibos auditáveis; logs/segredos não
são enviados à saída. Actions recebem só os nomes de ambiente do alvo e preservam aprovação humana de produção.
O catálogo admite limite genérico `servicos_maximos`, sem enum de provedores no núcleo.

## Consequências

A versão inicial não compõe vários serviços numa app Tsuru; o gerador recusa essa configuração. O registry interno
pode alterar a referência da imagem importada: a origem imutável da CI é conferida no evento, e a referência interna
é registrada separadamente. Candidatas são serializadas no staging. A instalação precisa configurar app/job/banco,
credencial restrita e rota por ambiente. O adaptador não cria recursos automaticamente nem recria o Tsuru.

Veja o [contrato e runbook](../deploy-tsuru.md) para campos, passos, fontes e evidências de teste.
