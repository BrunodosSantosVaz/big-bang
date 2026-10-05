# Política de segurança

<!-- DOC-16: criado pelo bb init a partir de .bigbang/modelos/comunidade/. Pertence ao projeto. -->

## Versões com suporte

Só a versão mais recente em produção ([Releases](https://github.com/{{projeto.repositorio}}/releases/latest))
recebe correções de segurança.

## Como relatar uma vulnerabilidade

**Não abra uma issue pública com os detalhes.** Use o
[relato privado de vulnerabilidade](https://github.com/{{projeto.repositorio}}/security/advisories/new) do GitHub
(aba *Security* → *Report a vulnerability*). Se ele não estiver disponível, abra uma issue só pedindo contato, sem
detalhes exploráveis.

Inclua: a versão afetada, os passos para reproduzir, o impacto que você observou e, se tiver, uma sugestão de
correção.

## O que acontece depois

- Confirmação do recebimento em até 7 dias.
- Triagem com severidade; correção pelo fluxo de hotfix (teste que reproduz a falha, correção, homologação e
  publicação).
- Crédito a quem relatou na Release da correção, se a pessoa quiser.

## Como o projeto se protege

Varredura de segredos, análise estática, dependências e CodeQL em todo PR; regras de segurança do
[Big Bang](https://github.com/BrunodosSantosVaz/big-bang) (`.bigbang/padroes/seguranca.md`) cobradas pela CI.
