# Runbook: voltar versão

<!-- Salve como docs/operacao/voltar-versao.md. Testado no esqueleto andante da Fundação (F5). DOC-09. -->

## Perfil deploy

1. Escolha a versão anterior que estava bem (Releases).
2. Rode **Voltar versão** com essa versão e `simular=true`: confira a imagem (digest) que voltaria.
3. Rode de novo com `simular=false` e aprove o ambiente `producao` (só o dono).
4. A esteira publica a imagem registrada em `imagem.txt` daquela Release e confere `/api/health`.

Voltar versão **nunca desfaz migração**. Por isso toda mudança de esquema segue expandir-e-contrair (DAD-02): a versão
anterior funciona com o esquema novo.

## Perfil compilado

Quem usa baixa a Release anterior (Releases do repositório) e confere o hash:

```
sha256sum -c SHA256SUMS-<sistema>.txt
```

## Depois

Abra um bug `severidade:critica` com o que aconteceu e siga o fluxo de hotfix. Registre o incidente em
`docs/operacao/` (linha do tempo, causa, correção, o que muda).
