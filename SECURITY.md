# Política de segurança

## Versões com suporte

Só a versão mais recente do framework ([Releases](https://github.com/BrunodosSantosVaz/big-bang/releases/latest))
recebe correções de segurança.

## Como relatar uma vulnerabilidade

**Não abra uma issue pública com os detalhes.** Use o
[relato privado de vulnerabilidade](https://github.com/BrunodosSantosVaz/big-bang/security/advisories/new) do GitHub
(aba *Security* → *Report a vulnerability*). Se ele não estiver disponível, abra uma issue só pedindo contato, sem
detalhes exploráveis.

Inclua: a versão afetada, os passos para reproduzir, o impacto que você observou e, se tiver, uma sugestão de
correção.

## O que acontece depois

- Confirmação do recebimento em até 7 dias.
- Triagem com severidade; correção numa versão nova do framework, com teste que reproduz a falha.
- Crédito a quem relatou na Release da correção, se a pessoa quiser.

## Como o projeto se protege

Cada versão é publicada com o SHA-256 e a atestação de origem do pacote; `bb atualizar` confere os dois antes de
trocar o framework de um sistema. As regras de segurança que o framework impõe aos sistemas estão em
[`.bigbang/padroes/seguranca.md`](.bigbang/padroes/seguranca.md).
