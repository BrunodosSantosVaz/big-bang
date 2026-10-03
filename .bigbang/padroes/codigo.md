# Padrão de código (COD)

Regras obrigatórias para todo sistema do Big Bang. **DEVE**/**NÃO DEVE** são obrigação; **DEVERIA** só se descumpre
com ADR; **PODE** é opção. Exceção só com ADR listado em `docs/padroes/excecoes.md`. Veja a
[tabela de rastreio](README.md).

### COD-01 · SOLID

- **Regra:** O código DEVE seguir SOLID: uma responsabilidade por classe ou módulo; extensão sem alterar o que
  funciona; abstrações substituíveis; interfaces pequenas; dependência de abstração, não de implementação.
- **Por quê:** Mudanças ficam locais, e cada parte pode ser testada e trocada isoladamente.
- **Certo:** `InvoiceCalculator` só calcula; `InvoiceRepository` só persiste.
- **Errado:** `InvoiceManager` que calcula, grava, manda e-mail e gera PDF.
- **Referência:** SOLID (Robert C. Martin, *Agile Software Development*).
- **Verificação:** item do `bb-revisor-pr`.

### COD-02 · Clean Code

- **Regra:** Nomes DEVEM dizer a intenção; funções DEVEM ser curtas e fazer uma coisa; NÃO DEVE haver efeito colateral
  escondido.
- **Por quê:** Código é lido muito mais vezes do que escrito, por pessoas e por IAs.
- **Certo:** `def is_overdue(invoice, today) -> bool`.
- **Errado:** `def check(x)` que também atualiza o banco.
- **Referência:** Clean Code (Robert C. Martin).
- **Verificação:** item do `bb-revisor-pr` e lint.

### COD-03 · DRY, KISS, YAGNI

- **Regra:** O código NÃO DEVE ter duplicação de conhecimento; DEVE usar a solução mais simples que resolve; NÃO DEVE
  conter nada especulativo.
- **Por quê:** Cada linha a mais é custo de manutenção e superfície de erro.
- **Certo:** uma função de formatação de moeda usada em todo o sistema.
- **Errado:** fábrica genérica de plugins para um único caso.
- **Referência:** The Pragmatic Programmer (Hunt e Thomas).
- **Verificação:** detector de duplicação na CI (COD-10) e item do `bb-revisor-pr`.

### COD-04 · Sem número mágico

- **Regra:** O código NÃO DEVE ter número ou texto mágico; DEVE usar constantes nomeadas.
- **Por quê:** O nome explica o significado e muda num lugar só.
- **Certo:** `MAX_LOGIN_ATTEMPTS = 5`.
- **Errado:** `if attempts > 5:` espalhado em três arquivos.
- **Referência:** Refactoring (Martin Fowler), "Replace Magic Literal".
- **Verificação:** lint da stack (regra de número mágico, quando existir) e item do `bb-revisor-pr`.

### COD-05 · Erros explícitos

- **Regra:** O tratamento de erro DEVE ser explícito, com erros de domínio; o código NÃO DEVE engolir exceção.
- **Por quê:** Erro engolido vira dado errado em produção, sem rastro.
- **Certo:** `raise OutOfStockError(product_id)` e tratamento na borda com resposta 409.
- **Errado:** `except Exception: pass`.
- **Referência:** Clean Code, cap. 7; OWASP ASVS V7 (tratamento de erros).
- **Verificação:** lint da stack e item do `bb-revisor-pr`.

### COD-06 · Comentário explica o porquê

- **Regra:** Comentário DEVE explicar o porquê; NÃO DEVE haver código comentado; `TODO` só com número de issue.
- **Por quê:** O código diz o quê; o porquê se perde se não for escrito. Código comentado apodrece.
- **Certo:** `# The bank rejects files above 500 lines (#87)`; `# TODO(#112): paginate`.
- **Errado:** `# increments i`; `# TODO: fix later`.
- **Referência:** Clean Code, cap. 4.
- **Verificação:** item do `bb-revisor-pr` ("slop").

### COD-07 · Idioma e glossário

- **Regra:** Identificadores, comentários e commits DEVEM ser em inglês; o glossário em `docs/produto/glossario.md`
  DEVE ligar cada termo de negócio (português) ao nome no código.
- **Por quê:** Padrão de mercado no código, português para quem usa, e uma ponte única entre os dois.
- **Certo:** glossário `Pedido ↔ Order`; classe `Order`.
- **Errado:** `class Pedido` num módulo e `class Order` em outro para a mesma coisa.
- **Referência:** Decisão 15 do dono; Domain-Driven Design (linguagem ubíqua).
- **Verificação:** item do `bb-revisor-pr` e checklist da tarefa de documentação.

### COD-08 · Lint, formatador e tipagem estrita

- **Regra:** O código DEVE passar no lint e no formatador sem aviso e DEVE usar tipagem estrita (TypeScript `strict`,
  mypy/pyright estrito ou equivalente).
- **Por quê:** Erros baratos são pegos pela máquina, e a revisão foca no que importa.
- **Certo:** `"strict": true` no `tsconfig.json`.
- **Errado:** `// eslint-disable` no topo do arquivo; `any` para calar o compilador.
- **Referência:** Documentação da ferramenta da stack.
- **Verificação:** comandos `lint` e `tipos` no job `check` da CI.

### COD-09 · Limites de tamanho e complexidade

- **Regra:** O código DEVE respeitar estes limites, ajustáveis no `STACK.md` com ADR: complexidade ciclomática ≤ 10 por função; arquivo ≤ 400
  linhas; função ≤ 40 linhas; até 4 parâmetros.
- **Por quê:** Limites objetivos impedem funções gigantes que ninguém consegue revisar.
- **Certo:** função de 25 linhas que delega para três auxiliares nomeadas.
- **Errado:** função de 180 linhas com oito `if` aninhados.
- **Referência:** McCabe (1976), *A Complexity Measure*.
- **Verificação:** lint da stack configurado com os limites (job `check`).

### COD-10 · Sem código morto e com detector de duplicação

- **Regra:** O código NÃO DEVE ter código morto; a CI DEVE rodar um detector de duplicação com limite.
- **Por quê:** Código morto confunde quem lê e as IAs, que tentam mantê-lo.
- **Certo:** função sem uso removida no mesmo PR que tirou o último chamador.
- **Errado:** `old_calculate_v2` esquecida no módulo.
- **Referência:** Refactoring (Martin Fowler), "Remove Dead Code".
- **Verificação:** lint e detector de duplicação da stack no job `check`.

### COD-11 · Commits pequenos e Conventional Commits

- **Regra:** Commits DEVEM seguir Conventional Commits em inglês e ser pequenos; DEVE haver um PR por tarefa.
- **Por quê:** A versão e o changelog saem dos títulos; PR pequeno é revisável.
- **Certo:** `feat(orders): block order without stock`.
- **Errado:** `ajustes` com 2.000 linhas e três tarefas.
- **Referência:** Conventional Commits 1.0.0.
- **Verificação:** check `regras` (título do PR) e item do `bb-revisor-pr`.

### COD-12 · Slop é defeito

- **Regra:** O código NÃO DEVE ter abstração especulativa, refatoração fora do escopo da issue nem teste enfraquecido.
- **Por quê:** Código gerado por IA tende a inflar; cada excesso é dívida e esconde mudanças perigosas.
- **Certo:** PR que muda só o necessário para a tarefa.
- **Errado:** PR da tarefa de relatório que também "melhora" o módulo de login.
- **Referência:** Fabio Akita, *github-resolution* ("slop é defeito").
- **Verificação:** item do `bb-revisor-pr` (escopo e "slop").

### COD-13 · Dependência nova só pelo portão

- **Regra:** Dependência de execução nova DEVE passar pelo portão de tecnologia (`bb-nova-tecnologia`): ADR e linha na
  tabela do `STACK.md`, com aprovação do dono.
- **Por quê:** Cada dependência é risco de segurança, licença e manutenção.
- **Certo:** PR com o ADR, a linha nova do `STACK.md` e o uso.
- **Errado:** `npm install left-pad` direto na tarefa.
- **Referência:** NIST SSDF PW.4 (reuso de software bem protegido); SLSA.
- **Verificação:** check `regras` (guarda da stack) e revisão humana (o `STACK.md` é zona sensível).
