# Documentação do próprio Big Bang

- [`especificacao.md`](especificacao.md): a especificação completa do framework (fonte única; não alterar sem
  decisão do dono).
- [`decisoes/`](decisoes/): ADRs do framework, no formato MADR.

## Manutenção do framework

- Toda mudança em `.bigbang/` precisa vir com o `.bigbang/CHECKSUMS` regravado:
  `python .bigbang/bin/bb.py checksums --escrever`. A CI roda `bb verificar` e reprova se ele estiver desatualizado.
- Depois de mudar um modelo, uma skill ou a versão, rode `python .bigbang/bin/bb.py gerar` para atualizar a camada
  gerada do próprio template (o `AGENTS.md` e as cópias das skills).
- Testes: `python -m unittest discover -s .bigbang/tests`.

## Imagens e plataformas

A candidata de deploy verifica cada combinação de serviço e plataforma configurada, conservando os digests
do índice. O [runbook Tsuru](deploy-tsuru.md#pesquisa-e-validação) descreve o SBOM por arquitetura e o primário
compatível; os passos de atualização estão em [MIGRACAO.md](../MIGRACAO.md).
