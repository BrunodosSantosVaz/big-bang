# 02 · Fundação (F0 a F5)

A Fundação transforma um repositório recém-criado a partir do Big Bang num sistema com produto definido, stack
escolhida, design aprovado, GitHub montado e esteira funcionando. Ela termina com um **esqueleto andante** (*walking
skeleton*): a menor versão do sistema que já passa pela esteira inteira até produção.

Quem conduz: a skill `bb-iniciar-projeto`, que chama a skill de cada etapa.

## Como cada etapa é registrada

- Cada etapa é uma issue com a label `fundacao`, uma branch `fundacao/<n>-<slug>` e um PR para a `develop`.
- Não há épico, candidata nem homologação na Fundação.
- A IA mescla o PR quando o dono diz "aprovado" na conversa, registrando a frase dele no PR. O PR guarda o histórico
  da decisão.
- Logo depois do PR da F5 que instala a esteira, *Publicar sem release* (rodado localmente pela IA, porque o botão
  ainda não existe na `main`) avança a `main` até a `develop`. Sem isso nada da esteira funciona: o GitHub só dispara
  os workflows de issue e os botões a partir da branch padrão. O épico Esqueleto andante vem depois.

## As etapas

| Etapa | O que acontece | O dono decide | Saída |
| --- | --- | --- | --- |
| **F0** · Ligar ao GitHub | Confere `git`, Python 3.11+ e `gh`; cria `develop`; `bb init` | Visibilidade e licença | `bigbang.toml`, README do sistema, label `fundacao`, issue de F0 |
| **F1** · Entrevista do produto | Até 10 perguntas, uma por vez, com opções | As respostas | `PRODUTO.md`, nível ASVS |
| **F2** · Stack, arquitetura e hospedagem | Pesquisa (`bb-pesquisador`) e 2 a 3 opções completas, com recomendação | A stack | `STACK.md`, `bigbang.toml` completo, `ADR-0001-stack.md`, C4 |
| **F3** · Design kit (em paralelo com F2) | Identidade, tokens, padrões de tela, protótipo | Aprovar ou pedir ajustes | `DESIGN.md`, `docs/design/`, protótipo |
| **F4** · Montar o GitHub | Passo a passo de permissões, um item por vez | Executar cada passo que é dele | Painéis, labels, ambientes, rulesets |
| **F5** · Esteira e esqueleto andante | `bb gerar`; épico "Esqueleto andante" até produção | Homologar e aprovar produção | `.github/`, skills, primeiro deploy ou release |

Ordem: F0 vem antes de tudo (as issues precisam existir); depois F1; F2 e F3 andam em paralelo (a parte do design
que depende da stack fecha depois de F2); F4 e F5 por último.

### F0 · Ligar ao GitHub e escolher a visibilidade

1. Conferir `git`, Python 3.11+ (também como comando `python`, usado pelos hooks do Claude Code; no Ubuntu/Debian,
   `python-is-python3`) e `gh auth status` com os escopos `repo`, `project` e `workflow`. Para o que faltar,
   a IA mostra o comando exato (por exemplo `gh auth refresh -s project,workflow`) e espera o dono rodar. A IA nunca
   pede nem guarda token na conversa.
2. Conferir que o repositório existe e tem `main`; criar `develop` a partir da `main`.
3. Perguntar a visibilidade (privado por padrão). Se público, oferecer licenças com o efeito de cada uma: MIT ou
   Apache-2.0 para uso livre; AGPL-3.0 para obrigar quem oferece o sistema como serviço a abrir o código. Em qualquer
   escolha, explicar limites e custos da esteira **consultando a documentação e a página de preços do GitHub no
   momento**: cota de minutos de Actions em repositório privado (Windows e macOS consomem mais), proteções (rulesets,
   aprovação de ambiente) que o plano gratuito não aplica em repositório privado, e o fato de logs, artefatos e o
   resumo do *Ver painéis* ficarem visíveis em repositório público.
4. Rodar `bb init`: cria o `bigbang.toml` a partir do modelo, move o README de boas-vindas e o `LICENSE` do framework
   para `.bigbang/`, cria o `LICENSE` do sistema (se público), cria a label `fundacao` e a issue de F0.

### F1 · Entrevista do produto

No máximo 10 perguntas, uma por vez, com opções: o que o sistema faz numa frase; quem usa e quantos; onde roda (web,
desktop, celular, linha de comando); login e perfis de acesso; funciona sem internet?; mexe com dinheiro, saúde ou
dado pessoal?; integrações obrigatórias; orçamento mensal de hospedagem; o que o dono já domina; prazo do primeiro
uso real. Saída: `PRODUTO.md` e o nível ASVS (L1 ou L2) no `bigbang.toml`. Com dado pessoal ou dinheiro, L2 é
obrigatório.

### F2 · Stack, arquitetura e hospedagem

O subagente `bb-pesquisador` levanta as opções atuais e grava em `docs/pesquisa/`. A IA apresenta de duas a três
opções completas, cada uma com linguagem, framework, banco, alvo (AWS, Docker em VPS, PaaS) ou empacotamento,
ferramentas de teste/lint/tipos/arquitetura, custo mensal estimado, curva de aprendizado para o dono e riscos, e
recomenda uma. O dono escolhe. Saída: `STACK.md` (com a tabela de dependências de execução permitidas),
`bigbang.toml` completo (perfil, alvo, caminhos do artefato, arquivo de versão, ecossistemas do Dependabot, zonas
sensíveis, comandos), `ADR-0001-stack.md` com as
alternativas descartadas e `docs/arquitetura/` com os diagramas C4 de contexto e contêineres.

### F3 · Design kit

Identidade (logo em SVG, **ícone global** `docs/design/icone.svg`, paleta, tipografia, biblioteca de ícones), tokens,
padrões de tela (lista, formulário, detalhe, vazio, erro, carregando), componentes base e um protótipo navegável das 3
a 5 telas principais, acessível no nível AA, que já mostra o ícone onde ele aparece (app, favicon). O dono valida o
protótipo e o ícone juntos; reprovado volta com o comentário dele. Sem interface, F3 se resume ao ícone global
(DOC-17), que todo sistema tem: README, imagem do repositório e o que mais levar ícone.

### F4 · Montar o GitHub

Um item por vez, conferido pela IA com `gh` antes do próximo:

1. Escopo `project` no `gh`.
2. `PROJETO_TOKEN`: PAT clássico com `repo` e `project` (e `workflow` só se a esteira precisar empurrar arquivos de
   `.github/workflows/`), **com validade definida**, um por projeto, guardado como segredo pelo próprio dono
   (`gh secret set PROJETO_TOKEN`). Motivo: o `GITHUB_TOKEN` das Actions não enxerga Projects de usuário e os eventos
   dele não disparam outros workflows.
3. Secret scanning e bloqueio de push ligados.
4. Ambiente `producao` com aprovação obrigatória do dono, aceitando só a `main`; no perfil deploy, também `staging`.
5. Rulesets em `main`, `develop` e `epico/*`: exigem PR e os checks `check`, `regras` e `seguranca`; bloqueiam force
   push e exclusão.
6. No perfil deploy: credenciais do alvo, preferindo federação OIDC (nada de chave fixa). No perfil compilado:
   os segredos de assinatura `BB_ASSINATURA_ARQUIVO` (keystore ou certificado em base64), `BB_ASSINATURA_SENHA`,
   `BB_ASSINATURA_ALIAS` e, se diferente, `BB_ASSINATURA_SENHA_CHAVE`, gerados e guardados pelo dono.
7. Variáveis do repositório (`PROJETO_OWNER`, números dos painéis) e opções de merge (permitir *merge commit*;
   "apagar branch após merge" desligado, porque quem apaga é a esteira).

Os itens 3, 4, 5 e 7 são aplicados por `.bigbang/scripts/configurar-repositorio.sh <dono/repo>` (rode antes com
`--simular`); os itens 2 e 6 são segredos e só o dono os cria. Depois, a IA cria os três painéis com colunas, campos
e visões (`criar-paineis.sh`), as labels completas (`criar-labels.sh`) e acrescenta as issues da Fundação já
concluídas.

### F5 · Esteira e esqueleto andante

`bb gerar` monta `.github/`, `.agents/skills/`, `.claude/` e os blocos marcados a partir do framework e do
`bigbang.toml` (removendo os workflows `bb-framework-*`). O PR da F5 instala só a esteira e documentos: nenhum código do
artefato entra na `develop` por ele (invariante da seção 11.5). Enquanto nenhum caminho do artefato existe, a CI pula
os comandos da stack com aviso. O PR da F5 também cria `docs/operacao/checklist-producao.md` a partir do modelo,
dizendo como o projeto verifica cada item (`cmd:`, `portao:` ou `nao-se-aplica:` com motivo). Todos os botões rodam
primeiro com `simular=true`. Em
seguida, um épico de verdade, "Esqueleto andante", segue o fluxo normal: estrutura de camadas da stack, health check,
teste de arquitetura, a primeira regra de negócio com seu teste de aceite, e publicação em produção — incluindo um
*Voltar versão* de teste no perfil deploy. **A Fundação só termina quando esse ciclo fecha.**

## Como retomar

A skill `bb-iniciar-projeto` descobre a etapa atual pelas issues `fundacao` (abertas e fechadas) e pelos arquivos
já existentes (`bigbang.toml`, `PRODUTO.md`, `STACK.md`, `DESIGN.md`, `.github/workflows/bb-*.yml`), resume o que já
foi decidido e continua da próxima etapa. Pode-se interromper a Fundação a qualquer momento: nada se perde, porque
cada etapa fica numa issue e num PR.

## O que a automação faz sozinha

Na Fundação, quase nada: a esteira completa só existe a partir de F5. Até lá, a IA usa `gh` e os comandos `bb`
diretamente, sempre mostrando ao dono o que vai fazer fora do repositório antes de fazer.
