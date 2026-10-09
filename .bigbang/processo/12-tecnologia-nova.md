# 12 · Tecnologia nova

Os caminhos de documentação do sistema citados aqui são identificadores lógicos: leia com `bb documentacao ler <caminho>`. Em públicos, escreva e revise a proposta na Wiki; em privados, mantenha os arquivos locais. Aplique `.bigbang/processo/18-documentacao.md`, incluindo inventário, matriz, links e publicação confirmada também no Flash. README público é uma apresentação breve com Wiki, Discussions e painéis; conteúdo completo e screenshots ficam na Wiki.

Toda dependência **direta de execução** precisa estar aprovada na tabela do `STACK.md`. Dependências de
desenvolvimento (teste, lint, build) são livres.

## O portão

O check **Guarda da stack** (job `regras`) lê os arquivos de dependência da stack (`package.json`,
`pyproject.toml`/`requirements*.txt`, `go.mod`, `Cargo.toml`, `pom.xml`/`build.gradle*`, `composer.json`,
`*.csproj`) e reprova dependência direta de execução que não está na tabela entre `<!-- bb:dependencias:inicio -->` e
`<!-- bb:dependencias:fim -->` do `STACK.md`. Ecossistema não suportado → falha explícita pedindo suporte no
framework, nunca passa em silêncio.

## Quando a IA precisa de algo novo

Skill `bb-nova-tecnologia`, **antes de instalar**:

1. A IA para e explica ao dono:
   - o que é a tecnologia ou o pacote;
   - por que o que já existe no `STACK.md` não serve;
   - alternativas (incluindo resolver sem dependência nova);
   - custo, licença, manutenção (atividade do projeto, mantenedores) e risco (segurança, cadeia de suprimentos).
2. Se precisar, aciona o `bb-pesquisador` e grava a pesquisa em `docs/pesquisa/`.
3. **Dono aceita:** o mesmo PR traz o ADR em `docs/decisoes/` e a linha nova na tabela do `STACK.md`
   (`| Pacote | Ecossistema | Faixa de versão | Para quê | ADR |`). O PR cai em revisão humana, porque o `STACK.md`
   é zona sensível.
4. **Dono recusa:** a IA resolve com o que existe.

## Atualização maior de dependência de execução

Passa pelo mesmo portão: ADR curto com o que muda, o risco e o plano de migração.

## Mudança de stack

Trocar linguagem, framework, banco ou alvo é decisão do dono, registrada num ADR que substitui o anterior
(`ADR-0001-stack.md` passa a "substituída por ADR-x") e no histórico do `STACK.md`.

## O que a automação faz sozinha

Reprova o PR que traz dependência de execução não aprovada e troca a revisão para humana quando o PR toca o
`STACK.md` ou os arquivos de dependência.
