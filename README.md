<p align="center"><img src=".bigbang/docs/imagens/icone.svg" width="96" alt="Ícone do Big Bang"></p>

# Big Bang

Framework para desenvolver e entregar sistemas com IAs, GitHub e uma esteira verificável. Organiza Fundação, planejamento, testes, revisão independente, homologação, produção e encerramento.

Para donos de produto e equipes que trabalham com IAs: comece pelo [guia de início](https://github.com/BrunodosSantosVaz/big-bang/wiki/Guia-de-inicio) e pela Fundação. Ela registra produto, stack, design e controles antes da implementação.

A **v3** usa um quadro único de 15 estados, de Brainstorm a Done, com Rejected e Cancelled. O épico agrupa tarefas, que fecham no merge; a release é cortada da `develop`. Feature flags, check único `gate`, posse por travas atômicas e estados registrados em recibos fazem parte do fluxo.

Os modos são **normal**, **flash** e **autonomous**. Flash executa os testes ao fim das alterações e seleciona os afetados; mudanças estruturais exigem a suíte completa. Testes são escritos antes do código em todos os modos. Autonomous exige `autonomy.toml` e os controles previstos no contrato, com revisão independente.

Identificadores e CLI usam inglês, com os nomes em português mantidos como aliases. Quem já usa a v2 pode adotar a v3 opcionalmente com `bb migrate` e a skill `bb-migrate`, por etapas com simulação, snapshot e volta.

A documentação oficial deste repositório público está na **[Wiki](https://github.com/BrunodosSantosVaz/big-bang/wiki)**. Repositórios privados conservam a documentação local. A validação inclui links, imagens e destinos de badges.

- [Começar a usar](https://github.com/BrunodosSantosVaz/big-bang/wiki/Guia-de-inicio)
- [Referência da CLI](https://github.com/BrunodosSantosVaz/big-bang/wiki/Referencia-CLI)
- [Relatório de testes e entrega](https://github.com/BrunodosSantosVaz/big-bang/wiki/Relatorio-de-testes-2-0-1)
- [Histórico e decisões](https://github.com/BrunodosSantosVaz/big-bang/wiki/Historico)
- [Rastreabilidade e cobertura](https://github.com/BrunodosSantosVaz/big-bang/wiki/Rastreabilidade)
- [Releases e pacote oficial](https://github.com/BrunodosSantosVaz/big-bang/releases)
- [Discussions](https://github.com/BrunodosSantosVaz/big-bang/discussions) · [Boas-vindas da IA](https://github.com/BrunodosSantosVaz/big-bang/discussions/210)

A v3 organiza o trabalho num único Project. Enquanto este repositório conclui a migração, os painéis públicos atuais continuam disponíveis: [Planejamento](https://github.com/users/BrunodosSantosVaz/projects/28), [Execução](https://github.com/users/BrunodosSantosVaz/projects/29) e [Bugs](https://github.com/users/BrunodosSantosVaz/projects/30). Escrita exige permissão explícita.

[Design e Social preview](https://github.com/BrunodosSantosVaz/big-bang/wiki/Design) registram identidade, arquivos e situação do upload da imagem. [Segurança](SECURITY.md), [contribuição](CONTRIBUTING.md) e [código de conduta](CODE_OF_CONDUCT.md) apresentam os canais da comunidade. Licença [MIT](LICENSE).

A esteira própria da v3 é gerada com `bb generate --framework` no repositório de origem. Os botões
`bb-framework-*` usam o fluxo agrupador; os workflows atuais permanecem obrigatórios durante a transição.
