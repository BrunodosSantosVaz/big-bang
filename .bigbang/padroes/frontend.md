# Padrão de front-end (FE)

Regras obrigatórias para todo sistema do Big Bang com interface. **DEVE**/**NÃO DEVE** são obrigação; **DEVERIA** só
se descumpre com ADR; **PODE** é opção. Exceção só com ADR listado em `docs/padroes/excecoes.md`. Veja a
[tabela de rastreio](README.md).

### FE-01 · Só tokens e componentes do design kit

- **Regra:** O front DEVE usar só os tokens e componentes do `DESIGN.md`; cor, espaçamento e fonte literais DEVEM ser
  reprovados pelo lint.
- **Por quê:** Consistência visual sem depender de memória; o design muda num lugar só.
- **Certo:** `color: var(--cor-primaria)`; `<Botao variante="primario">`.
- **Errado:** `color: #3366ff`; `margin: 13px`.
- **Referência:** Design Tokens (W3C Design Tokens Community Group).
- **Verificação:** lint de estilo da stack no job `check` (por exemplo Stylelint com regra de valores literais) e item
  do `bb-revisor-pr`.

### FE-02 · Modal no lugar de `alert()` e `confirm()`

- **Regra:** Confirmação e aviso DEVEM usar o modal do design kit; `alert()` e `confirm()` são proibidos.
- **Por quê:** Diálogos nativos bloqueiam a página, não seguem o design e não são acessíveis de forma consistente.
- **Certo:** `<ModalConfirmacao titulo="Excluir pedido?">`.
- **Errado:** `if (confirm("Tem certeza?"))`.
- **Referência:** my-saas-prompt; WAI-ARIA Authoring Practices (Dialog).
- **Verificação:** lint da stack (`no-alert` ou equivalente) no job `check`.

### FE-03 · A partir de 360 px

- **Regra:** A interface DEVE ser usável a partir de 360 px de largura, sem rolagem horizontal da página, com área de
  toque de pelo menos 44×44.
- **Por quê:** Boa parte do uso real acontece no celular.
- **Certo:** tabela vira lista de cartões em telas estreitas.
- **Errado:** formulário com largura fixa de 800 px.
- **Referência:** WCAG 2.2, critérios 1.4.10 (Reflow) e 2.5.8 (Target Size).
- **Verificação:** teste ponta a ponta em 360 px nos fluxos principais e item do `bb-revisor-pr`.

### FE-04 · Acessibilidade WCAG 2.2 AA

- **Regra:** A interface DEVE cumprir WCAG 2.2 nível AA (contraste, teclado, foco visível, rótulos), com verificador
  automático na CI.
- **Por quê:** Acessibilidade é requisito de qualidade e, em muitos casos, legal.
- **Certo:** todo campo com `<label>`; foco visível; contraste ≥ 4,5:1.
- **Errado:** ícone clicável sem nome acessível.
- **Referência:** WCAG 2.2 (https://www.w3.org/TR/WCAG22/); Lei 13.146/2015 (LBI).
- **Verificação:** verificador automático (por exemplo axe) no job `check`.

### FE-05 · Todos os estados da tela

- **Regra:** Toda tela DEVE tratar carregando, vazio, erro e sucesso.
- **Por quê:** Tela branca ou travada é o defeito mais visível para quem usa.
- **Certo:** lista com *skeleton*, mensagem de vazio com ação, erro com "tentar de novo".
- **Errado:** lista que mostra nada enquanto carrega e nada quando falha.
- **Referência:** padrões de tela do `DESIGN.md`.
- **Verificação:** item do `bb-revisor-pr` e protótipo aprovado.

### FE-06 · Formatos pt-BR

- **Regra:** A interface DEVE mostrar data e hora no fuso do usuário, moeda em reais e números no formato brasileiro.
- **Por quê:** `10/03` não pode ser lido como 3 de outubro.
- **Certo:** `Intl.NumberFormat("pt-BR", {style: "currency", currency: "BRL"})`.
- **Errado:** `R$ 1,234.56`.
- **Referência:** Unicode CLDR (locale pt-BR).
- **Verificação:** item do `bb-revisor-pr`.

### FE-07 · Variáveis de build só públicas

- **Regra:** Variáveis de build do front DEVEM conter só configuração pública (`SEG-IA-04`).
- **Por quê:** Tudo que vai para o pacote do front é público.
- **Certo:** `VITE_API_URL=https://app.exemplo.com/api`.
- **Errado:** `VITE_DATABASE_PASSWORD=…`.
- **Referência:** documentação do Vite e do Next.js (variáveis expostas ao cliente).
- **Verificação:** varredura de segredo no pacote do front (job `seguranca`).

### FE-08 · 401 e 403

- **Regra:** Resposta 401 DEVE encerrar a sessão e voltar ao login; 403 DEVE mostrar acesso negado.
- **Por quê:** Sessão expirada não pode deixar a tela num estado quebrado.
- **Certo:** interceptador HTTP que redireciona para `/login` no 401.
- **Errado:** tela em branco quando o token expira.
- **Referência:** checklist do Pegada de Silício.
- **Verificação:** item do `bb-revisor-pr` e `bb checklist producao`.

### FE-09 · Esconder botão é experiência, não segurança

- **Regra:** Esconder botão DEVE ser tratado só como experiência do usuário; a permissão é do backend (`SEG-IA-02`).
- **Por quê:** O front pode ser alterado por quem o usa.
- **Certo:** botão escondido e rota protegida no backend.
- **Errado:** botão escondido e rota aberta.
- **Referência:** OWASP Top 10 A01.
- **Verificação:** teste de API das rotas protegidas e item do `bb-revisor-pr`.

### FE-10 · Textos centralizados em português

- **Regra:** Os textos da interface DEVEM estar em português e centralizados, prontos para tradução futura.
- **Por quê:** Texto espalhado no código é difícil de revisar e de traduzir.
- **Certo:** `t("pedidos.vazio")` com o arquivo `pt-BR.json`.
- **Errado:** strings soltas em 40 componentes.
- **Referência:** W3C Internationalization Best Practices.
- **Verificação:** item do `bb-revisor-pr`.
