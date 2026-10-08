# Entrega Flash/Tsuru e testes do Big Bang — atualização de 08/10/2026

## Distribuição publicada

[Big Bang v1.5.3](https://github.com/BrunodosSantosVaz/big-bang/releases/tag/v1.5.3), tag imutável no commit
`b7321f21397cdbe52cc67680bcac59d30ab2c651`. A [publicação oficial](https://github.com/BrunodosSantosVaz/big-bang/actions/runs/37594888593)
terminou com sucesso e inclui pacote, SHA-256 e atestação GitHub. O SHA-256 conferido do arquivo
`bigbang-v1.5.3.tar.gz` é `a5694622b6b8d5041cc069aef2a4f164cdc83c4d367da82dcb2c1f68a53bd1a4`.

A atualização oficial 1.5.3 do Snake pelo [PR #64](https://github.com/BrunodosSantosVaz/snake-3310/pull/64)
conferiu pacote/hash/atestação pelo instalador e revisão independente/CI exata, preservando o jogo publicado.
A atualização anterior pelo [PR #52](https://github.com/BrunodosSantosVaz/snake-3310/pull/52)
conferiu hash e atestação antes de instalar a distribuição. A atualização anterior, pelos PRs #45, #46 e #48,
instalou a versão 1.5.1 e preservou Flash, Tsuru e a aplicação nos épicos. As tags anteriores não foram alteradas.

## Resultado da suíte completa

A [CI da versão publicada](https://github.com/BrunodosSantosVaz/big-bang/actions/runs/37594346530) terminou com os cinco jobs
verdes no SHA exato da versão. A [CI da revisão independente do PR #199](https://github.com/BrunodosSantosVaz/big-bang/actions/runs/37593707875)
também passou antes do merge.

A sincronização main→develop pelo [PR #200](https://github.com/BrunodosSantosVaz/big-bang/pull/200)
preservou a árvore completa da distribuição, após revisão independente e [CI completa](https://github.com/BrunodosSantosVaz/big-bang/actions/runs/37596012579).

| Verificação | Resultado |
| --- | --- |
| Python 3.11 | 498 testes contabilizados: 497 passaram e um ciclo Docker reservado ao job dedicado |
| Python 3.13 | 498 testes contabilizados: 497 passaram e o mesmo ciclo reservado ao job dedicado |
| Alvo VPS/Docker | 15 testes passaram: 14 de protocolo com SSH simulado e um ciclo Docker/SSH real de publicação, migração, saúde e retorno |
| Shellcheck | Todos os scripts Bash rastreados aprovados, severidade style |
| Gitleaks | Histórico completo aprovado |
| `bb verificar` | CHECKSUMS, camada gerada e workflows aprovados nas duas versões Python |
| Distribuição | Pacote 1.5.3 baixado e hash/atestação conferidos; a atualização oficial do Snake pelo PR #52 conferiu o pacote 1.5.2 |
| SBOM ARM64 real | Trivy 0.75.0 em AMD64 leu a imagem ARM64 da cobrinha e gerou CycloneDX 1.7 com 101 componentes; HIGH/CRITICAL zero |

O skip das suítes Python não deixou o ciclo Docker sem executar: `BB_TESTE_DOCKER=1` o habilitou no job específico.
Nesse ciclo, o servidor e o SSH são reais, mas a obtenção do `imagem.txt` de uma Release pelo `gh` é simulada.
Ele comprova o ciclo automatizado em contêiner; não substitui o ensaio completo num VPS externo exigido por #99.
As correções #191, #195 e #198 tiveram regressões escritas antes do código. A #195 acrescentou seis testes que falharam
antes da correção de arquitetura: SBOM e vulnerabilidades agora são verificados por serviço e plataforma,
preservando o digest do índice e o SBOM principal para compatibilidade. A #198 acrescentou três testes para
as variáveis públicas dos projetos no fluxo Mesclar PR; dois reproduziram a falha na criação das branches depois
de uma mesclagem efetiva. A correção preservou os scripts, tokens, permissões e portões. Falhas intermediárias foram corrigidas
antes da CI final; nenhum check foi enfraquecido. A execução Flash reutilizou evidência adequada do SHA exato,
sem repetir suítes locais completas por hábito.

## Alcance e trabalhos posteriores

Flash é persistido em `projeto.modo` e pode ser escolhido na Fundação ou adotado depois por PR/ADR.
Testes continuam anteriores ao código; execução afetada ocorre ao concluir a implementação. Estrutura, produção
e versões major/minor exigem suíte completa, e as revisões independentes e verificações de segurança permanecem.

Os alvos implementados são Tsuru, VPS/Docker e entrega compilada. O catálogo pode crescer; AWS, deploy por pacotes
e alvo personalizado continuam no épico #174. A prova VPS num servidor externo do dono (#99) é um critério de campo
pendente, distinto do ciclo Docker real já aprovado na CI. Não foi apresentada como teste executado.

## Recibos dos consumidores

### ScreenFakeCam

[ScreenFakeCam v0.3.2](https://github.com/BrunodosSantosVaz/screenfakecam/releases/tag/v0.3.2) foi publicada pelo
[portão oficial de produção](https://github.com/BrunodosSantosVaz/screenfakecam/actions/runs/37587716471).
O APK `screenfakecam-v0.3.2-android.apk` tem 1.235.989 bytes e SHA-256
`29d89a99d2839185138259dafc688ee85fbcb087a6a788a8ebc8612dd3a43fca`;
é idêntico, byte a byte, ao APK da candidata homologada. O SBOM promovido também é idêntico, SHA-256
`62100900817910c2f69080922f1eab47c7a680c25ce4063a0b37c0bc7bddaa32`, com 303 componentes, incluindo
101 Maven e todos os 100 módulos de execução dos locks Gradle. Hashes e atestação GitHub foram conferidos.

O certificado RSA-4096 é o mesmo das versões anteriores, SHA-256
`4edaf7eae89d5da175d0817739b5866f9e7180acdcb3f260bb84b7143742e20d`.
A homologação real, registrada nas issues #70, #72 e #81, usou emulador Android 15/API 35: atualização assinada
sobre 0.3.1 sem apagar dados, imagem 10001×2001, zoom e pan por teclado com foco correto, foto efetivamente salva
na galeria sem EXIF e leitura de QR com resultado exato. Não houve recompilação na promoção. Aparelho físico,
Android 8/9 e TalkBack não foram apresentados como provas desta entrega.

README e documentação final foram publicados pelo [fluxo sem release do épico #84](https://github.com/BrunodosSantosVaz/screenfakecam/actions/runs/37595429285),
após integração, revisão independente e CI completa. Main e develop ficaram em
`19ebfd55d826e594a09f9e61515b3407adceadf7`. A comparação dos assets antes e depois confirmou os mesmos IDs,
tamanhos e digests; nenhuma recompilação nem mudança da tag estável ocorreu. O [recibo público](https://github.com/BrunodosSantosVaz/screenfakecam/issues/84#issuecomment-6034304028)
registra o encerramento das quatro issues e a liberação das posses. O consumidor continua no modo normal.

### Snake 3310 e Tsuru

Homologação validada em `https://tsuru.frontzap.com.br/snake-3310-hom/`: importação pelo digest OCI,
jogo/modal/ranking no Chromium, persistência após reinício, volume SQLite privado e backup cifrado com restauração.
A primeira candidata interrompeu corretamente a publicação ao falhar na leitura ARM64 pelo scanner AMD64;
a correção oficial 1.5.2 resolveu a seleção de arquitetura sem relaxar o portão.
A [produção v0.1.0](https://github.com/BrunodosSantosVaz/snake-3310/releases/tag/v0.1.0) foi publicada pelo
[run oficial 37766740098](https://github.com/BrunodosSantosVaz/snake-3310/actions/runs/37766740098), após suíte completa,
revisão independente e aprovação do ambiente delegada pela autorização explícita do dono. A imagem e os dois SBOMs
foram promovidos com os mesmos digests da candidata, sem reconstrução.

Em 08/10/2026, a candidata [v0.1.0-rc.2](https://github.com/BrunodosSantosVaz/snake-3310/releases/tag/v0.1.0-rc.2)
foi conferida por [revisão independente](https://github.com/BrunodosSantosVaz/snake-3310/pull/60#issuecomment-6051531113).
Fonte `7a770ff4be050598f8cebea9718d372145e1d3eb`, origem OCI
`sha256:12fb06c1c51f72772358d7cf6dfd2a7b4468af13c5f4917946d290477b2acac1`;
[Candidata 37596185419](https://github.com/BrunodosSantosVaz/snake-3310/actions/runs/37596185419) com cinco jobs aprovados,
[CI exata](https://github.com/BrunodosSantosVaz/snake-3310/actions/runs/37596189652) com 135 testes, 13 aceites e 128 na cobertura de 100%.
O SBOM ARM64 tem 101 componentes, SHA-256
`6c6e25ae78bf9806924f2c74d77419a3e343b2ff3dff5b2d0874458b7aba1e96`.
A atestação confere a imagem OCI e sua fonte; não se atribui uma atestação separada ao arquivo SBOM.
ZAP registrou zero FAIL e nove avisos, com cabeçalhos da raiz do Tsuru fora do caminho do jogo e avisos de cache/COEP.

O ensaio remoto em Chromium confirmou movimento, pausa, reinício, modal/foco, um POST 201 real ao ranking,
viewport de 360 px, texto 200%, alvos de toque de 44 px, axe sem violações nos estados ensaiados e nenhum erro JavaScript.
O reinício efetivo da app preservou o placar sintético no SQLite; novo pod Ready e uma única unidade foram observados.
O diretório do volume tem UID/GID 1000 e modo 0700; o banco tem modo 0600, uma migração e `quick_check=ok`.
Snapshot cifrado real após o envio foi restaurado e comparado pelo script de backup.

Produção repetiu o ensaio no navegador com sucesso, incluindo POST201 único e leitura posterior do ranking.
Reinício pela API Tsuru preservou o placar sintético no banco. Após o rollout foi observada uma única unidade Ready
por app, zero reinícios, PVC Bound/Retain, diretórios1000:1000/0700 e bancos1000:1000/0600.
A limpeza parametrizada removeu exclusivamente as duas linhas sintéticas de zero pontos; os três placares reais
em homologação foram preservados. Seis POSTs inválidos em produção, variando cabeçalhos falsos de IP, receberam
cinco400 e um429/Retry-After60, comprovando que os cabeçalhos não contornam o limite.

Às11:07:02 UTC de 08/10, o daemon cron gerou snapshots age de ambas apps e a restauração em tmpfs validou
`quick_check=ok`, uma migração e contagens coerentes. Diretórios0700, arquivos0600, sem SQLite em claro ou temporários
residuais. O ensaio antecipou somente o job do Snake para o próximo minuto e restaurou integralmente o cron
original `17 * * * *`, root/0644/PATH explícito; serviço enabled/active. Snapshot manual não foi confundido com esse ensaio.

| App | Snapshot cron | SHA-256 cifrado |
| --- | --- | --- |
| Homologação | `20261008T110702077613Z.sqlite.age` | `ccfa213640162f776b963fb5f3bd6d84daf873f0c2e8dd854d3dd92ff38945cb` |
| Produção | `20261008T110702077613Z.sqlite.age` | `2ae3e3f491731167633f9c569bc3b11c1584b2d03f90508bcb3ca30baa0c489f` |

Backups e chave permanecem no mesmo host; cópia/custódia externas e recuperação após perda total do servidor
não foram comprovadas. A revisão documental do Snake segue o [épico #65](https://github.com/BrunodosSantosVaz/snake-3310/issues/65),
sem versão nova da aplicação. A manutenção e documentação do Tsuru foram revisadas e mescladas pelo
[PR #2 do OracleCloud](https://github.com/BrunodosSantosVaz/oraclecloud/pull/2).
