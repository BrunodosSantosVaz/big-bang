# ADR-0017: Modo Flash com testes escritos antes e execução seletiva

- **Situação:** aceita
- **Data:** 2026-10-06
- **Dono:** Bruno dos Santos Vaz (`BrunodosSantosVaz`)
- Tarefa: #183; épico: #174.

## Contexto e problema

O dono pediu acelerar a entrega, mantendo segurança e organização, e corrigiu explicitamente o requisito:

> unica coisa que eu quero é que os testes continuem sendo feitos antes, porem os testes rodem mais no final

A mesma decisão pede executar apenas os testes afetados e reservar a suíte completa para mudanças estruturais,
produção e versões maiores. Major/minor são versões maiores; patch é a miniversão, salvo alteração estrutural.

## Decisão e justificativa

Persistir `projeto.modo = "padrao" | "flash"` no TOML, escolher em `bb init --modo flash` ou mudar posteriormente
por PR e ADR. Sem a chave, padrão retrocompatível. Testes continuam anteriores ao código e o fluxo de branches e
as travas de aceite permanecem. Flash muda o momento e a seleção da execução, respeitando dependências entre testes
e código. `bb testes` usa o seletor aprovado da stack ou executa toda a suíte quando não puder selecionar com segurança.

Reutilizar o plano autorizado, revisão independente por IA e a CI verde do SHA exato na candidata. Revisão humana
explicitamente pedida e trabalho crítico continuam humanos. Produção sempre exige testes completos, ordem do dono
e aprovação do ambiente. Nenhuma regra SEG-IA é desligada. Documentação e README acompanham os PRs.

O dono pediu aplicar na finalização do próprio framework e do Snake. No framework, usa-se o processo leve já
existente e a decisão deste ADR; não se cria outro repositório nem se roda Fundação nele. No Snake, aplicação pela
atualização oficial do framework, TOML e ADR do projeto.

## Consequências

Stacks precisam fornecer um seletor testado; sem ele, Flash reduz esperas manuais mas executa a suíte completa.
Mudanças estruturais no próprio framework continuam disparando CI completa. A execução local repetida não é
obrigatória se o mesmo commit já possui evidência adequada na CI. Candidata recusa CI ausente, falha ou de outro SHA.

Veja o [contrato operacional](../../processo/17-flash.md).
