# 11 · Segurança operacional

Segurança no dia a dia: auditorias, achados, incidentes e segredos vazados. As regras técnicas estão em
`.bigbang/padroes/seguranca.md`.

## Auditoria de segurança

Quando: o dono diz "audita a segurança"; antes da primeira produção; ao fim de todo épico em zona sensível.

Skill `bb-auditar-seguranca`:

1. Detecta a stack e o nível ASVS do projeto (`seguranca.nivel_asvs`).
2. Roda as ferramentas: Gitleaks, Opengrep/Bandit, OSV-Scanner, Trivy e ZAP no staging quando houver.
3. Revisa as cinco garantias `SEG-IA-01` a `SEG-IA-05` e a lista do nível ASVS.
4. Reporta **só achados verificados no código**, cada um com arquivo e linha, trecho, por que é explorável e
   severidade. Nada de especulação.
5. Grava o relatório em `docs/seguranca/auditorias/AAAA-MM-DD.md`.
6. Abre uma issue por achado: labels `bug` + `seguranca` + `severidade:*`, título `[Segurança] <descrição curta>`, com
   evidência, correção sugerida e critérios de aceite.
7. Achado crítico ou alto recebe `bloqueia-producao`: nenhuma publicação passa enquanto ele estiver aberto.

A correção segue o fluxo de bug ([10-bugs-e-hotfix.md](10-bugs-e-hotfix.md)), nunca na mesma sessão da auditoria.

## Falso positivo

Exceção só com ADR e registro em `docs/padroes/excecoes.md`. **Nunca se desliga a varredura.** As regras `SEG-IA-*`
não admitem exceção que desligue a varredura.

## Segredo vazado

Segredo encontrado no código, no histórico, num log ou no pacote do front é tratado **como vazado**, mesmo que o
repositório seja privado:

1. A IA avisa o dono imediatamente — sem repetir o valor do segredo.
2. O dono **revoga** o segredo no provedor.
3. O dono **cria um novo** e o guarda como segredo do repositório ou do ambiente.
4. A IA remove o uso do código (variável de ambiente ou cofre) e abre o bug com teste que impede a volta.
5. Registro do incidente em `docs/operacao/` (o que vazou, quando, onde, o que foi feito). Reescrever o histórico do
   Git não substitui a revogação.

## Incidente

1. Conter: *Voltar versão* (deploy) ou retirar a Release (compilado), se for o caso.
2. Abrir issue `bug` com `severidade:critica` e `hotfix`.
3. Corrigir pelo fluxo de hotfix.
4. Registrar o incidente no runbook (linha do tempo, causa, correção, o que muda) e rodar a `bb-retrospectiva`.

## Rotação de segredos

Todo segredo (incluindo o `PROJETO_TOKEN`, que tem validade definida) tem rotação descrita no runbook do sistema:
quem, como e com que frequência.

## O que a automação faz sozinha

Roda Gitleaks, Opengrep/Bandit, OSV-Scanner e CodeQL em todo PR e push, e semanalmente no histórico completo;
reprova o PR com achado; bloqueia a publicação enquanto houver issue `bloqueia-producao` aberta.
