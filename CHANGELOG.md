# Changelog do Big Bang

Mudanças do framework em português, no formato Keep a Changelog. Passos de atualização e histórico das versões
anteriores estão em [MIGRACAO.md](.bigbang/MIGRACAO.md). A versão instalada é registrada em `.bigbang/VERSION`.

## [1.5.3] - 2026-10-07

### Corrigido

- Mesclar PR fornece as variáveis públicas dos painéis ao pós-merge, permitindo criar próximas branches e
  disparar a integração final sem intervenção manual causada por variável ausente.
- Regressão executa o caminho pós-merge com as variáveis declaradas no workflow, sem as injeções da harness.

## [1.5.2] - 2026-10-07

### Corrigido

- SBOM ARM64 em runner AMD64 seleciona a plataforma configurada, usando o digest imutável do índice.
- Todas as arquiteturas de todos os serviços passam pelo Trivy; falhas interrompem a candidata.
- SBOMs por plataforma acompanham a promoção, mantendo o arquivo primário da primeira plataforma.

## [1.5.1] - 2026-10-07

### Corrigido

- Registro de revisão independente de PRs grandes pela API paginada, sem depender do diff limitado a 300 arquivos.
- Caminhos anteriores de renomes continuam sujeitos à revisão sensível; patch de aceite ausente e lista incompleta impedem aprovação.

## [1.5.0] - 2026-10-06

### Adicionado

- Modo Flash persistente: testes escritos antes do código, execução posterior dos afetados e revisão independente.
- Catálogo extensível de alvos e artefatos (`bb alvos`), com validação de disponibilidade e capacidades.
- Adaptador do Tsuru existente para um serviço OCI por aplicação e digest, com `TSURU_MIGRACAO=job` por padrão
  ou `inicializacao` para SQLite em volume persistente.
- Pré-checagem de inicialização registra `migration=pending`; a imagem migra antes de ouvir a porta. Readiness
  consulta o banco; uma réplica permanente pode ter sobreposição transitória no rollout do mesmo volume.
- Seleção de runner e preparação de rede nas publicações, conforme a configuração aprovada do projeto.

### Alterado

- Actions recebem as referências de variáveis/segredos e os scripts de artefato do contrato escolhido.
- Candidata em Flash reutiliza somente a CI oficial verde do SHA exato. Estrutura, primeira entrega, major/minor
  e produção exigem testes completos; ausência de base ou seletor seguro também executa tudo.
- Produção é vinculada ao SHA testado e preserva aprovação humana; retomada de versão publicada conclui a limpeza.

### Corrigido

- Release do framework em repositório privado valida a `main` com as referências do checkout completo, sem
  depender de credenciais Git persistidas para um novo fetch.
- Configuração de revisão vem da branch de destino; o PR não altera a política que o julga.
- Mudanças estruturais em subpastas também forçam a suíte completa.

### Limitações

- VPS/Docker, runner público e modo padrão continuam sendo os padrões de projetos existentes.
- Plataforma Node.js nativa é preparação separada do servidor; o alvo Tsuru entrega imagem OCI, sem upload de fontes.
- AWS/paas, alvo personalizado e formatos de deploy `pacote`/`estatico` permanecem reservados.
- Testes do adaptador não comprovam homologação de uma aplicação no Tsuru real; essa evidência pertence ao consumidor.
