# Padrão de documentação (DOC)

Regras obrigatórias para todo sistema do Big Bang. **DEVE**/**NÃO DEVE** são obrigação; **DEVERIA** só se descumpre
com ADR; **PODE** é opção. Exceção só com ADR listado em `docs/padroes/excecoes.md`. Veja a
[tabela de rastreio](README.md).

### DOC-01 · Documentação no repositório

- **Regra:** A documentação DEVE ficar no repositório, em Markdown, versionada com o código, na estrutura de `docs/`
  definida pelo Big Bang.
- **Por quê:** Documento fora do repositório desatualiza e nenhuma IA o encontra.
- **Certo:** `docs/negocio/regras/RN-0042-bloquear-pedido-sem-estoque.md`.
- **Errado:** regra de negócio só numa planilha ou numa conversa.
- **Referência:** Docs as Code (Write the Docs).
- **Verificação:** item do `bb-revisor-pr` e checklist da tarefa de documentação.

### DOC-02 · Uma regra de negócio por arquivo, nunca apagada

- **Regra:** Cada regra de negócio DEVE ter um arquivo `RN-NNNN`; regra que muda DEVE ganhar RN nova e a antiga vira
  `substituida`; RN NÃO DEVE ser apagada.
- **Por quê:** O histórico de regras explica comportamentos antigos e dados antigos.
- **Certo:** RN-0042 `substituida_por: RN-0057`.
- **Errado:** editar a RN-0042 para dizer o contrário do que dizia.
- **Referência:** Especificação, seções 6.4 e 9.
- **Verificação:** check `regras` (rastreabilidade: nenhuma RN apagada).

### DOC-03 · Rastreabilidade RN ↔ teste

- **Regra:** Toda RN vigente DEVE ter teste de aceite que a cita; todo teste de aceite DEVE citar uma RN existente.
- **Por quê:** Regra sem teste não é garantida; teste sem regra não se sabe por que existe.
- **Certo:** `test_rn0042_blocks_order_without_stock`.
- **Errado:** `test_order_3`.
- **Referência:** Rastreabilidade de requisitos (ISO/IEC/IEEE 29148).
- **Verificação:** check `regras` (rastreabilidade).

### DOC-04 · Decisões em ADR

- **Regra:** Toda decisão relevante DEVE virar ADR no formato MADR.
- **Por quê:** Sem o porquê registrado, a próxima IA desfaz a decisão.
- **Certo:** `ADR-0003-uuid-v7.md` com as opções descartadas.
- **Errado:** decisão explicada só no PR.
- **Referência:** MADR (https://adr.github.io/madr/).
- **Verificação:** checklist da tarefa de documentação e item do `bb-revisor-pr`.

### DOC-05 · arc42 enxuto e C4

- **Regra:** A arquitetura DEVE ser documentada em arc42 enxuto mais C4.
- **Por quê:** Estrutura conhecida, que qualquer pessoa ou IA sabe onde procurar.
- **Certo:** `docs/arquitetura/README.md` com as seções do modelo.
- **Errado:** um texto corrido de 20 páginas sem estrutura.
- **Referência:** arc42 (https://arc42.org); C4 (https://c4model.com).
- **Verificação:** checklist da tarefa de documentação.

### DOC-06 · Contrato OpenAPI como fonte

- **Regra:** A API DEVE ter contrato OpenAPI como fonte.
- **Por quê:** O contrato gera documentação, clientes e testes de contrato.
- **Certo:** `docs/api/openapi.yaml` validado na CI.
- **Errado:** rotas documentadas só num README.
- **Referência:** OpenAPI 3.1 (https://spec.openapis.org/oas/v3.1.0).
- **Verificação:** teste de contrato no job `check` e item do `bb-revisor-pr`.

### DOC-07 · Diátaxis

- **Regra:** Guias de uso DEVEM ficar separados de referência, seguindo Diátaxis (tutorial, guia prático, referência,
  explicação).
- **Por quê:** Quem quer aprender e quem quer consultar leem de jeitos diferentes.
- **Certo:** `docs/guias/emitir-nota.md` (guia) e `docs/api/` (referência).
- **Errado:** guia que mistura passo a passo com a tabela completa de campos.
- **Referência:** Diátaxis (https://diataxis.fr).
- **Verificação:** item do `bb-revisor-pr`.

### DOC-08 · Changelog

- **Regra:** O `CHANGELOG.md` DEVE seguir o Keep a Changelog, em português (Adicionado, Alterado, Corrigido,
  Removido, Segurança).
- **Por quê:** Quem usa precisa saber o que mudou em cada versão.
- **Certo:** `## [1.4.0] - 2026-10-20` com `### Adicionado`.
- **Errado:** lista de commits copiada.
- **Referência:** Keep a Changelog 1.1.0 (https://keepachangelog.com/pt-BR/1.1.0/).
- **Verificação:** portão do *Publicar em produção* (changelog com a seção da versão).

### DOC-09 · Runbooks

- **Regra:** O sistema DEVE ter runbooks de deploy, voltar versão, backup e restauração, incidente e rotação de
  segredo.
- **Por quê:** Na hora do problema não há tempo de descobrir como fazer.
- **Certo:** `docs/operacao/voltar-versao.md` testado no esqueleto andante.
- **Errado:** "pergunte para quem configurou".
- **Referência:** Google SRE Book (playbooks).
- **Verificação:** checklist da tarefa de documentação.

### DOC-10 · Inventário LGPD

- **Regra:** O sistema DEVE manter o inventário LGPD em `docs/dados/`.
- **Por quê:** É obrigação legal e guia o que pode ser coletado e por quanto tempo.
- **Certo:** tabela dado → finalidade → base legal → retenção → exclusão.
- **Errado:** dado pessoal novo sem entrada no inventário.
- **Referência:** Lei 13.709/2018 (LGPD), art. 37; `SEG-20`.
- **Verificação:** checklist da tarefa de documentação.

### DOC-11 · Glossário PT ↔ EN

- **Regra:** O sistema DEVE manter o glossário que liga cada termo de negócio em português ao nome no código.
- **Por quê:** Evita dois nomes para a mesma coisa (`COD-07`).
- **Certo:** `| Pedido | Order | ... |`.
- **Errado:** `Order`, `Purchase` e `Request` para o mesmo conceito.
- **Referência:** Domain-Driven Design (linguagem ubíqua).
- **Verificação:** checklist da tarefa de documentação.

### DOC-12 · Memória e pesquisa das IAs

- **Regra:** As IAs DEVEM alimentar `docs/memoria.md` (pegadinhas para as próximas sessões) e `docs/pesquisa/` (toda
  pesquisa feita).
- **Por quê:** Tudo que não virou código vira texto; sem isso cada sessão redescobre o mesmo problema.
- **Certo:** "O banco X exige arquivo com CRLF; ver #87" em `docs/memoria.md`.
- **Errado:** pesquisa de duas horas que só existiu na conversa.
- **Referência:** Fabio Akita ("faça o agente escrever tudo que não virou código").
- **Verificação:** item do `bb-revisor-pr` e `bb-retrospectiva`.

### DOC-13 · Tarefa de documentação por épico

- **Regra:** Todo épico DEVE ter uma tarefa de documentação com o checklist do Big Bang.
- **Por quê:** Documentação que fica "para depois" não acontece.
- **Certo:** issue `documentacao` criada pelo *Iniciar sprint*.
- **Errado:** épico integrado sem a tarefa de documentação concluída.
- **Referência:** Especificação, seção 9.4.
- **Verificação:** *Iniciar sprint* cria a issue; *Integrar release* exige a tarefa concluída.

### DOC-14 · Markdown válido e sem link quebrado

- **Regra:** A documentação DEVE ser Markdown válido e sem link quebrado.
- **Por quê:** Link quebrado é documentação que mente.
- **Certo:** `[ADR-0003](../decisoes/ADR-0003-uuid-v7.md)` apontando para um arquivo que existe.
- **Errado:** link para um arquivo renomeado.
- **Referência:** CommonMark (https://commonmark.org).
- **Verificação:** checagem de Markdown e links no job `check` da CI.

### DOC-15 · README do sistema completo e atual

- **Regra:** O `README.md` do sistema DEVE estar completo e descrever o sistema como ele está em produção: selos de
  CI, produção e homologação, uma imagem real, e as seções Estado atual, Para que serve, Recursos, Instalação, Como
  usar, Para desenvolvedores, Versões e releases, Segurança e privacidade, Limitações conhecidas, Contribuindo e
  Licença. Toda tarefa que muda o que o usuário vê, instala ou configura atualiza o README no mesmo PR; a tarefa de
  documentação do épico confere o README inteiro.
- **Por quê:** O README é a porta de entrada do sistema; um README "em construção" com versões em produção mente.
- **Certo:** "Estado atual: v0.3.0 em produção — obturador e leitor de QR", com o print da tela principal.
- **Errado:** "Em Fundação" depois da primeira release; seções "(a preencher)".
- **Referência:** modelo `.bigbang/modelos/README-sistema.md`; o README do próprio Big Bang como exemplo de nível.
- **Verificação:** `bb esteira documentacao` no job `check` da CI (depois da primeira release, seções obrigatórias,
  selo da CI e nada de "Fundação", "em construção" ou "(a preencher)"); checklist da tarefa de documentação.

### DOC-16 · Arquivos de comunidade

- **Regra:** Todo sistema DEVE ter `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md` e `SECURITY.md` na raiz, além do
  `README.md` e da licença (se público), para o GitHub mostrar o perfil de comunidade completo.
- **Por quê:** Quem chega ao repositório precisa saber como se comportar, como contribuir e como relatar uma falha
  de segurança sem expô-la em público.
- **Certo:** os três arquivos criados pelo `bb init` (ou `bb esteira comunidade`) e completados pelo projeto.
- **Errado:** repositório só com README e licença; falha de segurança relatada numa issue pública.
- **Referência:** modelos em `.bigbang/modelos/comunidade/`; Contributor Covenant 2.1; relato privado de
  vulnerabilidade do GitHub.
- **Verificação:** `bb esteira documentacao` no job `check` da CI, em todo sistema fundado.

### DOC-17 · Ícone global do sistema

- **Regra:** Todo sistema DEVE ter um único ícone, `docs/design/icone.svg`, criado no design kit (F3), mostrado no
  protótipo e aprovado junto com ele, e usado em tudo que leva ícone: ícone do app (launcher), favicon, manifesto
  PWA, cabeçalho do README e imagem do repositório.
- **Por quê:** Um sistema sem ícone próprio aparece com o ícone padrão da plataforma e parece inacabado; ícones
  diferentes em cada lugar confundem quem usa.
- **Certo:** o SVG aprovado no protótipo gera o ícone adaptativo do Android e o favicon.
- **Errado:** app com o robô padrão do Android; favicon diferente do ícone do app.
- **Referência:** `DESIGN.md` (seção Identidade); skill `bb-design-kit`.
- **Verificação:** `bb esteira documentacao` no job `check` da CI (depois do `DESIGN.md` ou da primeira release);
  aprovação do protótipo pelo dono.
