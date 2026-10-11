# Processo do fluxo v3

Estes documentos valem para projetos com `workflow.model = "grouping"` (quadro único e épico agrupador). Projetos
que ainda usam o fluxo anterior seguem `.bigbang/processo/` até migrar (`bb migrate`).

| Documento | Assunto |
| --- | --- |
| [board.md](board.md) | Quadro único, estados, recibos, travas, reprovação e controlador |
| [planning.md](planning.md) | Da ideia ao Ready: decisões do dono, protótipo, flag e homologação |
| [sprint.md](sprint.md) | Seleção, `bb sprint start`, sub-issues e branches |
| [execution.md](execution.md) | Tarefa: posse, branch da `develop`, testes, PR, `gate`, revisão e merge |
| [delivery.md](delivery.md) | Release, candidata, QA, publicação, manutenção, volta de versão e faxina |
| [bugs.md](bugs.md) | Triagem, `fix/` e `hotfix/` a partir da `main` |
| [modes.md](modes.md) | Modos normal, flash e autonomous e o contrato `autonomy.toml` |

Os documentos comuns aos dois fluxos continuam em `.bigbang/processo/`:

- Fundação (02);
- segurança operacional (11);
- tecnologia nova (12);
- atualização do framework (15);
- conversas (16);
- documentação (18).
