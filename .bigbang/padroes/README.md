# Padrões obrigatórios

Regras que todo sistema do Big Bang segue, com o número que a IA cita quando aplica ou aponta uma regra
(`ARQ-03`, `SEG-07`…). **DEVE**/**NÃO DEVE** indicam obrigação; **DEVERIA** indica recomendação forte que só se
descumpre com ADR; **PODE** indica opção (equivalentes em português da RFC 2119).

| Arquivo | Prefixo | Assunto |
| --- | --- | --- |
| [arquitetura.md](arquitetura.md) | `ARQ` | Camadas, dependências, Twelve-Factor, ADRs, C4 |
| [seguranca.md](seguranca.md) | `SEG-IA`, `SEG` | As cinco garantias, OWASP ASVS/Top 10, LGPD, esteira, checklist de produção |
| [codigo.md](codigo.md) | `COD` | SOLID, Clean Code, limites, idioma, commits |
| [testes.md](testes.md) | `TST` | Pirâmide, aceite travado, determinismo, cobertura |
| [documentacao.md](documentacao.md) | `DOC` | Regras de negócio, ADR, arc42/C4, OpenAPI, changelog, runbooks |
| [api.md](api.md) | `API` | REST, OpenAPI, Problem Details, paginação, idempotência |
| [dados.md](dados.md) | `DAD` | Migrações, expandir-e-contrair, dinheiro, backup, LGPD |
| [frontend.md](frontend.md) | `FE` | Design kit, acessibilidade, 360 px, formatos pt-BR |
| [observabilidade.md](observabilidade.md) | `OBS` | Logs, saúde, métricas, eventos de segurança |

## Como cada regra está escrita

Cada regra tem: **Regra** (com DEVE/NÃO DEVE), **Por quê**, exemplo **Certo** e **Errado**, **Referência** publicada
e **Verificação** (check da CI, teste obrigatório, item do `bb-revisor-pr` ou revisão humana).

## Exceções

Exceção a uma regra só com ADR aprovado pelo dono, listado em `docs/padroes/excecoes.md` do sistema. As regras
`SEG-IA-*` não admitem exceção que desligue a varredura.

## Tabela de rastreio

Cada regra → como é verificada → onde a verificação existe. A coluna **Implementada em** traz o arquivo do framework
que já implementa a verificação ou o épico do [roteiro](../docs/especificacao.md) que vai implementá-la
(`E4` núcleo da esteira; `E5` perfil compilado; `E6` testes, revisão, documentação e
segurança; `E8` skills e hooks; `E9` perfil deploy). Quando um épico entrega a verificação, a linha passa a apontar
para o arquivo. O teste `.bigbang/tests/test_padroes.py` confere que esta tabela bate com as regras.

| Regra | Padrão | Verificação | Implementada em |
| --- | --- | --- | --- |
| ARQ-01 | [arquitetura.md](arquitetura.md) | teste de arquitetura da stack (import-linter, dependency-cruiser, ArchUnit ou equivalente), rodado pelo comando `arquitetura` no job `check` da CI. | E4 |
| ARQ-02 | [arquitetura.md](arquitetura.md) | teste de arquitetura da stack (job `check`). | E4 |
| ARQ-03 | [arquitetura.md](arquitetura.md) | item do `bb-revisor-pr` e teste de arquitetura da stack. | E6 |
| ARQ-04 | [arquitetura.md](arquitetura.md) | teste de arquitetura da stack e item do `bb-revisor-pr`. | E6 |
| ARQ-05 | [arquitetura.md](arquitetura.md) | item do `bb-revisor-pr`. | E6 |
| ARQ-06 | [arquitetura.md](arquitetura.md) | item do `bb-revisor-pr` e varredura de segredo no pacote do front (job `seguranca`). | E6 |
| ARQ-07 | [arquitetura.md](arquitetura.md) | a esteira (candidata e publicação usam o mesmo artefato) e item do `bb-revisor-pr`. | E4, E6, E9 |
| ARQ-08 | [arquitetura.md](arquitetura.md) | item do `bb-revisor-pr`. | E6 |
| ARQ-09 | [arquitetura.md](arquitetura.md) | item do `bb-revisor-pr`. | E6 |
| ARQ-10 | [arquitetura.md](arquitetura.md) | revisão humana (mudança de arquitetura exige ADR aprovado pelo dono). | E4 |
| ARQ-11 | [arquitetura.md](arquitetura.md) | item do `bb-revisor-pr` e checklist da tarefa de documentação. | E4, E6 |
| ARQ-12 | [arquitetura.md](arquitetura.md) | checklist da tarefa de documentação e item do `bb-revisor-pr`. | E4, E6 |
| ARQ-13 | [arquitetura.md](arquitetura.md) | `bb checklist producao` e health check depois de cada deploy. | E6, E9 |
| ARQ-14 | [arquitetura.md](arquitetura.md) | item do `bb-revisor-pr`. | E6 |
| SEG-IA-01 | [seguranca.md](seguranca.md) | teste que tenta ler e gravar dado de outro usuário com a chave pública; check do job `seguranca` que reprova migração com tabela sem RLS quando `banco_no_navegador = true`. | E4, E6 |
| SEG-IA-02 | [seguranca.md](seguranca.md) | teste de API chamando cada rota protegida sem a permissão; `bb-revisor-pr`; regras do Opengrep no job `seguranca`. | E4, E6 |
| SEG-IA-03 | [seguranca.md](seguranca.md) | teste com dois usuários por recurso (`TST-06`) e varredura ZAP no staging. | E4, E9 |
| SEG-IA-04 | [seguranca.md](seguranca.md) | check que varre o pacote do front já construído; Gitleaks no PR e no histórico (job `seguranca`); bloqueio de push do GitHub. | E6 |
| SEG-IA-05 | [seguranca.md](seguranca.md) | teste que passa do limite e espera 429 (`TST-07`); `bb-revisor-pr`. | E4, E6 |
| SEG-01 | [seguranca.md](seguranca.md) | validação do esquema do `bigbang.toml` por `bb verificar` e revisão humana (o `bigbang.toml` é zona sensível). | E4, `.bigbang/bb/config.py` |
| SEG-02 | [seguranca.md](seguranca.md) | `bb-revisor-pr` e auditoria de segurança. | E6, E8 |
| SEG-03 | [seguranca.md](seguranca.md) | `bb-revisor-pr`; regras do Opengrep no job `seguranca`. | E6 |
| SEG-04 | [seguranca.md](seguranca.md) | `bb-revisor-pr` e teste de aceite da regra. | E4, E6 |
| SEG-05 | [seguranca.md](seguranca.md) | `bb-revisor-pr` e auditoria de segurança. | E6, E8 |
| SEG-06 | [seguranca.md](seguranca.md) | `bb-revisor-pr`; teste de API das rotas protegidas (`SEG-IA-02`). | E4, E6 |
| SEG-07 | [seguranca.md](seguranca.md) | `bb-revisor-pr`; regras do Opengrep no job `seguranca`. | E6 |
| SEG-08 | [seguranca.md](seguranca.md) | Opengrep, Bandit (Python) e CodeQL no job `seguranca`. | E6 |
| SEG-09 | [seguranca.md](seguranca.md) | Opengrep e CodeQL no job `seguranca`; `bb-revisor-pr`. | E6 |
| SEG-10 | [seguranca.md](seguranca.md) | varredura ZAP no staging e `bb-revisor-pr`. | E6, E9 |
| SEG-11 | [seguranca.md](seguranca.md) | `bb checklist producao` e `bb-revisor-pr`. | E6 |
| SEG-12 | [seguranca.md](seguranca.md) | `bb-revisor-pr` e auditoria de segurança. | E6, E8 |
| SEG-13 | [seguranca.md](seguranca.md) | varredura ZAP no staging e `bb-revisor-pr`. | E6, E9 |
| SEG-14 | [seguranca.md](seguranca.md) | `bb-revisor-pr`; regras do Opengrep no job `seguranca`. | E6 |
| SEG-15 | [seguranca.md](seguranca.md) | Gitleaks no job `seguranca`; `bb checklist producao` (README documenta variáveis sem valores). | E6 |
| SEG-16 | [seguranca.md](seguranca.md) | `bb-revisor-pr` e auditoria de segurança. | E6, E8 |
| SEG-17 | [seguranca.md](seguranca.md) | OSV-Scanner no job `seguranca`; Dependabot. | E6 |
| SEG-18 | [seguranca.md](seguranca.md) | `bb verificar` (regras dos workflows) no job `check`. | E4, `.bigbang/bb/workflow_rules.py`, `.bigbang/bb/verify.py` |
| SEG-19 | [seguranca.md](seguranca.md) | Trivy no workflow da candidata (perfil deploy). | E9 |
| SEG-20 | [seguranca.md](seguranca.md) | checklist da tarefa de documentação; revisão humana em zona sensível. | E4 |
| SEG-21 | [seguranca.md](seguranca.md) | revisão humana (zona sensível) e testes de cenário (`TST-08`). | E4 |
| SEG-22 | [seguranca.md](seguranca.md) | regra no `AGENTS.md`; `bb-triar-issue`; `bb-revisor-pr` (texto do PR que tenta mudar a revisão é achado). | E6, E8, `.bigbang/AGENTS.base.md` |
| SEG-23 | [seguranca.md](seguranca.md) | `bb-revisor-pr` e auditoria de segurança. | E6, E8 |
| SEG-24 | [seguranca.md](seguranca.md) | portão do *Iniciar sprint* (Definition of Ready) e revisão humana do refinamento. | E4 |
| COD-01 | [codigo.md](codigo.md) | item do `bb-revisor-pr`. | E6 |
| COD-02 | [codigo.md](codigo.md) | item do `bb-revisor-pr` e lint. | E4, E6 |
| COD-03 | [codigo.md](codigo.md) | detector de duplicação na CI (COD-10) e item do `bb-revisor-pr`. | E6 |
| COD-04 | [codigo.md](codigo.md) | lint da stack (regra de número mágico, quando existir) e item do `bb-revisor-pr`. | E4, E6 |
| COD-05 | [codigo.md](codigo.md) | lint da stack e item do `bb-revisor-pr`. | E4, E6 |
| COD-06 | [codigo.md](codigo.md) | item do `bb-revisor-pr` ("slop"). | E6 |
| COD-07 | [codigo.md](codigo.md) | item do `bb-revisor-pr` e checklist da tarefa de documentação. | E4, E6 |
| COD-08 | [codigo.md](codigo.md) | comandos `lint` e `tipos` no job `check` da CI. | E4 |
| COD-09 | [codigo.md](codigo.md) | lint da stack configurado com os limites (job `check`). | E4 |
| COD-10 | [codigo.md](codigo.md) | lint e detector de duplicação da stack no job `check`. | E4 |
| COD-11 | [codigo.md](codigo.md) | check `regras` (título do PR) e item do `bb-revisor-pr`. | E4, E6 |
| COD-12 | [codigo.md](codigo.md) | item do `bb-revisor-pr` (escopo e "slop"). | E6 |
| COD-13 | [codigo.md](codigo.md) | check `regras` (guarda da stack) e revisão humana (o `STACK.md` é zona sensível). | E4, E6 |
| TST-01 | [testes.md](testes.md) | comandos `testes` e `testes_aceite` no job `check` e item do `bb-revisor-pr`. | E4, E6 |
| TST-02 | [testes.md](testes.md) | check `regras` (trava de aceite). | E6 |
| TST-03 | [testes.md](testes.md) | fluxo do épico (as tarefas esperam o teste) e check `regras` (regressão). | E4, E6 |
| TST-04 | [testes.md](testes.md) | item do `bb-revisor-pr`. | E6 |
| TST-05 | [testes.md](testes.md) | comando `cobertura` no job `check`. | E4 |
| TST-06 | [testes.md](testes.md) | item do `bb-revisor-pr` e auditoria de segurança. | E6, E8 |
| TST-07 | [testes.md](testes.md) | item do `bb-revisor-pr` e `bb checklist producao`. | E6 |
| TST-08 | [testes.md](testes.md) | revisão humana (zona sensível) e item do `bb-revisor-pr`. | E4, E6 |
| TST-09 | [testes.md](testes.md) | comando `arquitetura` no job `check`. | E4 |
| TST-10 | [testes.md](testes.md) | item do `bb-revisor-pr`. | E6 |
| TST-11 | [testes.md](testes.md) | item do `bb-revisor-pr` e check `regras` (trava de aceite). | E6 |
| TST-12 | [testes.md](testes.md) | workflow da candidata no perfil deploy (`deploy.smoke`). | E9 |
| DOC-01 | [documentacao.md](documentacao.md) | item do `bb-revisor-pr` e checklist da tarefa de documentação. | E4, E6 |
| DOC-02 | [documentacao.md](documentacao.md) | check `regras` (rastreabilidade: nenhuma RN apagada). | E6 |
| DOC-03 | [documentacao.md](documentacao.md) | check `regras` (rastreabilidade). | E6 |
| DOC-04 | [documentacao.md](documentacao.md) | checklist da tarefa de documentação e item do `bb-revisor-pr`. | E4, E6 |
| DOC-05 | [documentacao.md](documentacao.md) | checklist da tarefa de documentação. | E4 |
| DOC-06 | [documentacao.md](documentacao.md) | teste de contrato no job `check` e item do `bb-revisor-pr`. | E4, E6 |
| DOC-07 | [documentacao.md](documentacao.md) | item do `bb-revisor-pr`. | E6 |
| DOC-08 | [documentacao.md](documentacao.md) | portão do *Publicar em produção* (changelog com a seção da versão). | E4 |
| DOC-09 | [documentacao.md](documentacao.md) | checklist da tarefa de documentação. | E4 |
| DOC-10 | [documentacao.md](documentacao.md) | checklist da tarefa de documentação. | E4 |
| DOC-11 | [documentacao.md](documentacao.md) | checklist da tarefa de documentação. | E4 |
| DOC-12 | [documentacao.md](documentacao.md) | item do `bb-revisor-pr` e `bb-retrospectiva`. | E6, E8 |
| DOC-13 | [documentacao.md](documentacao.md) | *Iniciar sprint* cria a issue; *Integrar release* exige a tarefa concluída. | E4 |
| DOC-14 | [documentacao.md](documentacao.md) | checagem de Markdown e links no job `check` da CI. | E4 |
| API-01 | [api.md](api.md) | item do `bb-revisor-pr` e teste de contrato. | E4, E6 |
| API-02 | [api.md](api.md) | teste de contrato no job `check`. | E4 |
| API-03 | [api.md](api.md) | teste de contrato e item do `bb-revisor-pr`. | E4, E6 |
| API-04 | [api.md](api.md) | item do `bb-revisor-pr`. | E6 |
| API-05 | [api.md](api.md) | teste de cenário (`TST-08`) e revisão humana (zona sensível). | E4 |
| API-06 | [api.md](api.md) | item do `bb-revisor-pr`. | E6 |
| API-07 | [api.md](api.md) | teste de contrato e item do `bb-revisor-pr`. | E4, E6 |
| DAD-01 | [dados.md](dados.md) | `bb checklist producao` (migrações do zero e da versão anterior) e revisão humana (`migrations/**` é zona sensível). | E4, E6 |
| DAD-02 | [dados.md](dados.md) | item do `bb-revisor-pr` e revisão humana. | E4, E6 |
| DAD-03 | [dados.md](dados.md) | operação `migrar` do alvo de deploy. | E9 |
| DAD-04 | [dados.md](dados.md) | item do `bb-revisor-pr`. | E6 |
| DAD-05 | [dados.md](dados.md) | item do `bb-revisor-pr`. | E6 |
| DAD-06 | [dados.md](dados.md) | teste de integração e item do `bb-revisor-pr`. | E4, E6 |
| DAD-07 | [dados.md](dados.md) | item do `bb-revisor-pr`. | E6 |
| DAD-08 | [dados.md](dados.md) | runbook (`DOC-09`) e revisão humana. | E4, E9 |
| DAD-09 | [dados.md](dados.md) | inventário LGPD (`DOC-10`) e revisão humana. | E4 |
| DAD-10 | [dados.md](dados.md) | item do `bb-revisor-pr` e Gitleaks no job `seguranca`. | E6 |
| FE-01 | [frontend.md](frontend.md) | lint de estilo da stack no job `check` (por exemplo Stylelint com regra de valores literais) e item do `bb-revisor-pr`. | E4, E6 |
| FE-02 | [frontend.md](frontend.md) | lint da stack (`no-alert` ou equivalente) no job `check`. | E4 |
| FE-03 | [frontend.md](frontend.md) | teste ponta a ponta em 360 px nos fluxos principais e item do `bb-revisor-pr`. | E4, E6 |
| FE-04 | [frontend.md](frontend.md) | verificador automático (por exemplo axe) no job `check`. | E4 |
| FE-05 | [frontend.md](frontend.md) | item do `bb-revisor-pr` e protótipo aprovado. | E6, E8 |
| FE-06 | [frontend.md](frontend.md) | item do `bb-revisor-pr`. | E6 |
| FE-07 | [frontend.md](frontend.md) | varredura de segredo no pacote do front (job `seguranca`). | E6 |
| FE-08 | [frontend.md](frontend.md) | item do `bb-revisor-pr` e `bb checklist producao`. | E6 |
| FE-09 | [frontend.md](frontend.md) | teste de API das rotas protegidas e item do `bb-revisor-pr`. | E4, E6 |
| FE-10 | [frontend.md](frontend.md) | item do `bb-revisor-pr`. | E6 |
| OBS-01 | [observabilidade.md](observabilidade.md) | item do `bb-revisor-pr`. | E6 |
| OBS-02 | [observabilidade.md](observabilidade.md) | `bb checklist producao` e health check depois de cada deploy. | E6, E9 |
| OBS-03 | [observabilidade.md](observabilidade.md) | item do `bb-revisor-pr` e revisão do runbook de operação. | E6, E9 |
| OBS-04 | [observabilidade.md](observabilidade.md) | operação `saude` do alvo, chamada pela publicação em produção e pela candidata. | E9 |
| OBS-05 | [observabilidade.md](observabilidade.md) | item do `bb-revisor-pr`. | E6 |
| OBS-06 | [observabilidade.md](observabilidade.md) | item do `bb-revisor-pr` e auditoria de segurança. | E6, E8 |
