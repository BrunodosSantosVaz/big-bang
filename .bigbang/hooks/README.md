# Hooks do Claude Code

`proteger_arquivos.py` e `proteger_comandos.py` (seção 15.4). Ajudam o Claude Code; a garantia é a CI.

Os hooks usam o protocolo `PreToolUse` verificado em 2026-10-04 na
[documentação oficial](https://code.claude.com/docs/en/hooks): JSON pela entrada padrão; decisão
`hookSpecificOutput.permissionDecision` (`deny` ou `ask`), com razão, e saída 0. Entrada inválida falha fechada
com saída 2 e mensagem sem o conteúdo do evento. Silêncio deixa as permissões normais continuarem, nunca aprova.

O gerador registra ambos em `.claude/settings.json` desde o template. Usa execução direta `command` + `args`,
sem shell, Python 3.11+ disponível como `python` no PATH e caminho ancorado em `CLAUDE_PROJECT_DIR`, inclusive
com espaços. Exige Claude Code com suporte a essa forma de execução; confira a configuração pelo `/hooks`.
O JSON `cwd` identifica a pasta atual, inclusive worktree; não confunda com a raiz de início da sessão.

Edição de aceite/framework/gerados é negada; documentos de decisão pedem confirmação. O bloco gerado do
AGENTS.md pode ser preservado enquanto se edita a seção do projeto; alteração no bloco é negada.
O bloco do STACK.md também é protegido e alterações fora dele continuam exigindo confirmação.

Comandos Git/GitHub usuais têm os bloqueios da seção 15.4. Formas dinâmicas/aliases/opções globais não conferíveis
pedem confirmação. O hook não é intérprete completo de Bash/PowerShell nem isolamento de processos: comandos
escritos em scripts, outras ferramentas e escritas pelo terminal não são uma fronteira de segurança.
Não contorne o hook; CI, rulesets, revisão e regras do AGENTS.md continuam obrigatórios para todas as IAs.

No próprio framework, autores usam o fluxo de contribuição da seção 17; as cópias pré-geradas continuam protegendo
projetos criados pelo template. O hook não concede uma exceção automática baseada no nome de um repositório.
