# Como contribuir com o Big Bang

Obrigado pelo interesse! O Big Bang é um framework para uma pessoa e suas IAs construírem sistemas profissionais.

## Relatar um problema ou sugerir algo

1. Procure nas [issues](https://github.com/BrunodosSantosVaz/big-bang/issues) se já existe.
2. Abra uma issue com o que você fez, o que esperava e o que aconteceu, a versão do framework (`.bigbang/VERSION`)
   e, se for de um sistema feito com o Big Bang, o trecho do log da esteira.
3. Falha de segurança: **não** abra issue pública com detalhes; veja [SECURITY.md](SECURITY.md).

## Enviar uma mudança

- Leia a [especificação](.bigbang/docs/especificacao.md): ela é a fonte da verdade, e cada decisão de projeto vira
  um ADR em [`.bigbang/docs/decisoes/`](.bigbang/docs/decisoes/).
- Branch a partir da `develop` (`feature/<issue>-<slug>`), commits em inglês
  ([Conventional Commits](https://www.conventionalcommits.org/pt-br/)), textos e documentação em português do Brasil.
- Só biblioteca padrão do Python 3.11+ na CLI `bb`; scripts da esteira em Bash, aprovados pelo `shellcheck`.
- Mudou algo em `.bigbang/`? Rode `bb checksums --escrever`, `bb gerar`, `python .bigbang/tests/atualizar_esperado.py`
  e a suíte: `python -m unittest discover -s .bigbang/tests` (com `BB_TESTE_DOCKER=1` para o alvo de deploy).
- Registre o que muda para os projetos em [`.bigbang/MIGRACAO.md`](.bigbang/MIGRACAO.md) e atualize o README.
- Abra o PR para a `develop` com *O que muda*, *Testes* e *Issue*; a CI precisa ficar verde.

## Código de conduta

Ao participar, você concorda com o [código de conduta](CODE_OF_CONDUCT.md).
