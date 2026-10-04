# Modelos

Pontos de partida para os arquivos do projeto. Os marcadores `{{secao.chave}}` são substituídos pelos valores do
`bigbang.toml`; os comentários `<!-- … -->` dizem o que escrever. Os links dentro dos modelos são relativos ao destino
de cada arquivo no projeto, não a esta pasta.

| Modelo | Destino no projeto | Quando nasce |
| --- | --- | --- |
| [PRODUTO.md](PRODUTO.md) | `PRODUTO.md` | F1 |
| [STACK.md](STACK.md) | `STACK.md` | F2 |
| [DESIGN.md](DESIGN.md) | `DESIGN.md` | F3 |
| [ADR.md](ADR.md) | `docs/decisoes/ADR-NNNN-<slug>.md` (MADR) | A cada decisão |
| [RN.md](RN.md) | `docs/negocio/regras/RN-NNNN-<slug>.md` | Refinamento e teste do épico |
| [arc42.md](arc42.md) | `docs/arquitetura/README.md` | F2 |
| [c4-contexto.md](c4-contexto.md) | `docs/arquitetura/contexto.md` | F2 |
| [c4-conteineres.md](c4-conteineres.md) | `docs/arquitetura/conteineres.md` | F2 |
| [bigbang.toml.exemplo](bigbang.toml.exemplo) | `bigbang.toml` | F0 (`bb init`), completado em F1, F2 e F4 |
| [flags.toml](flags.toml) | `flags.toml` | F5 (vazio) |
| [checklist-producao.md](checklist-producao.md) | `docs/operacao/checklist-producao.md` | F2/F5 (cada item com sua verificação) |
| [compose.yaml](compose.yaml) | `deploy/compose.yaml` | F2, perfil deploy com alvo vps-docker |
| [runbook-deploy.md](runbook-deploy.md) | `docs/operacao/deploy.md` | F5, perfil deploy |
| [runbook-voltar-versao.md](runbook-voltar-versao.md) | `docs/operacao/voltar-versao.md` | F5 |
