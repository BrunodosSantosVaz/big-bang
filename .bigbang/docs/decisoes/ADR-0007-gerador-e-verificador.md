# ADR-0007: Como o gerador e o verificador funcionam

- **Situação:** aceita
- **Data:** 2026-10-03
- **Decisores:** Bruno dos Santos Vaz (dono); Claude Code

## Contexto e problema

A especificação (seções 3.3, 5.1 e 14.6) define a camada gerada, o aviso em todo arquivo gerado, a composição núcleo
\+ perfil + alvo, o `CHECKSUMS` e o `bb verificar`, mas deixa em aberto como detectar arquivo gerado editado, como
tratar formatos sem comentário, quando a esteira passa a existir num projeto e como manter o `CHECKSUMS` durante o
desenvolvimento do próprio framework.

## Fatores de decisão

- Nenhum estado escondido que possa divergir do repositório.
- Funcionar igual no Windows e no Linux.
- Arquivos que as ferramentas exigem num formato fixo (frontmatter das skills, JSON) continuam válidos.
- O template do Big Bang passa no mesmo `bb verificar` que os projetos.

## Opções consideradas

1. Manifesto com o hash de cada arquivo gerado, gravado na geração.
2. **Regenerar em memória e comparar com o disco.**

## Decisão e justificativa

Escolhida: **opção 2**, no estilo de geradores de projeto como o Projen. Decisões que a acompanham:

- **Detecção de edição:** o `bb verificar` monta em memória tudo que o `bb gerar` escreveria e compara com o disco.
  Arquivo diferente, ausente ou obsoleto reprova. Sem manifesto, nada fica desatualizado.
- **Camadas** (`.bigbang/esteira/<camada>/arquivos/`, espelhando a raiz do projeto): `sempre` (gerada inclusive antes
  da Fundação; proibida de escrever em `.github/`), `nucleo`, `perfis/<perfil>` e `perfis/deploy/alvos/<alvo>`. Uma
  camada posterior pode substituir um arquivo da anterior. Arquivos `*.tmpl` têm os marcadores `{{secao.chave}}`
  substituídos; `${{ … }}` do GitHub Actions nunca é marcador; marcador sem valor é erro. Listas e tabelas viram JSON
  (válido em YAML e TOML).
- **Esteira instalada:** a esteira (`nucleo`, perfil, alvo) só é gerada com `bb gerar --esteira` (F5) e, a partir daí,
  sempre que `.github/` tiver algum arquivo gerado. Isso evita gerar workflows antes de o GitHub estar montado (F4),
  sem arquivo de estado. Ao instalar, os workflows `bb-framework-*` são removidos.
- **Aviso de arquivo gerado:** em comentário da linguagem do destino. Exceções para não quebrar formatos fixos: depois
  do frontmatter YAML (`SKILL.md` precisa começar com `---`) e depois do *shebang*. **JSON não tem comentário**: o
  arquivo fica sem aviso e é protegido pela regeneração e pela lista de zonas sensíveis. Tipo de arquivo sem formato de
  comentário conhecido é erro, para ninguém esquecer o aviso.
- **Gerados obsoletos:** arquivos em `.github/` com prefixo `bb-` ou com o aviso, e as pastas `bb-*` de skills e
  subagentes, que não estão no plano, são removidos pelo `bb gerar` e reprovados pelo `bb verificar`.
- **Blocos marcados:** o `AGENTS.md` recebe o bloco `bigbang:inicio/fim` (de `AGENTS.inicial.md` antes da Fundação e
  de `AGENTS.base.md` depois); o resto do arquivo é do projeto. O `STACK.md`, quando existe, tem o bloco
  `bb:config:inicio/fim` regerado a partir do `bigbang.toml`.
- **CHECKSUMS:** sha256 de cada arquivo de `.bigbang/` com CRLF normalizado para LF (checkout no Windows com
  `core.autocrlf` confere igual). Ficam de fora `CHECKSUMS`, caches do Python e o `README.md`/`LICENSE` que o
  `bb init` move para `.bigbang/`. No repositório do Big Bang, o `CHECKSUMS` é regravado em todo PR que muda
  `.bigbang/` (`bb checksums --escrever`), e a CI roda `bb verificar`; assim a release (E10) só empacota.
- **Esquema do `bigbang.toml`:** estrito (seção ou chave desconhecida reprova); a seção do perfil não usado pode
  existir e é ignorada, como no modelo.
- **Códigos de saída estáveis:** 0 ok, 2 uso inválido, 3 configuração inválida, 4 chave inexistente, 5 verificação
  reprovada, 6 comando externo falhou, 7 estado inválido.

## Consequências

### Positivas

- `bb verificar` não depende de estado e sempre diz a verdade sobre o disco.
- O próprio template é verificado na CI do Big Bang.

### Negativas

- Toda mudança em `.bigbang/` exige regravar o `CHECKSUMS` (a CI avisa).
- Arquivos JSON gerados (por exemplo `.claude/settings.json`, no E8) não carregam o aviso no próprio arquivo.
- Mudança de versão altera o aviso de todos os gerados, então os resultados esperados dos cenários
  (`.bigbang/tests/esperado/`) precisam ser regenerados (`.bigbang/tests/atualizar_esperado.py`).

## Referências

- Especificação, seções 3.3, 5.1, 5.4, 5.5, 14.6 e 15.5.
- Projen (arquivos gerados marcados e fonte única): https://projen.io
