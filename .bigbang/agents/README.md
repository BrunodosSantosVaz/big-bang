# Procedimentos dos subagentes

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Legíveis por qualquer IA. No Claude Code, o `bb gerar` cria os subagentes correspondentes em `.claude/agents/`.

| Procedimento | Subagente do Claude Code | Uso |
| --- | --- | --- |
| [revisor-pr.md](revisor-pr.md) | `bb-revisor-pr` | revisão hostil de PR, com contexto limpo e só leitura |
| [pesquisador.md](pesquisador.md) | `bb-pesquisador` | pesquisa para a Fundação F2 e para tecnologia nova |
