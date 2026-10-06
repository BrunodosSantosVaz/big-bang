# ADR-0016: Deploy multiplataforma por contratos instalados

- **Situação:** aceita como direção arquitetural no refinamento #174; implementação por tarefa e PR revisado pelo dono
- **Data:** 2026-10-06
- **Decisores:** Bruno dos Santos Vaz (dono); Codex (`codex-1`, implementação)

## Contexto e problema

O piloto Snake 3310 precisa de Tsuru. O dono ampliou o requisito para diferentes formas de deploy com Actions
geradas conforme a entrega, de modo semelhante ao perfil compilado, e aprovou o refinamento do épico #174 com
“sim, aprovado”, registrado por `bb decisao`. O enum antigo aceitava `aws` e `paas` sem haver adaptadores para eles;
as Actions de deploy também injetavam credenciais de VPS em todos os destinos.

## Fatores de decisão

Extensão sem mudar o núcleo a cada provedor; compatibilidade com projetos existentes; disponibilidade comprovada
antes da geração; mesmo artefato em staging/produção; configuração estrita e biblioteca padrão do Python.

## Opções consideradas

1. Ampliar o enum e copiar workflows inteiros por provedor: simples no início, mas mistura credenciais e duplica
   portões de publicação.
2. Contratos instalados com descoberta de alvos e formatos, composição por camadas e validação antes de escrever.
3. Aceitar qualquer nome/comando sem contrato: flexível, mas permite uma esteira aparentemente pronta e inválida.

## Decisão e justificativa

Opção 2. Separar **destino**, **formato do artefato** e **acesso à rede**. Os contratos TOML do framework declaram
estado (`implementado` ou `reservado`), capacidades e interface da implementação. O catálogo é consultável com
`bb alvos`, sem Fundação ou acesso externo. Nomes reservados, scripts ausentes e combinações incompatíveis são
recusados pelo gerador antes de qualquer escrita. A validação de sintaxe do `bigbang.toml` permanece sem I/O;
capacidades são verificadas na fronteira de geração/verificação usando o pacote instalado.

`deploy.artefato` usa `imagem` por padrão. A entrega OCI existente mantém digest e scripts atuais. O contrato
prevê identidade por SHA-256 para pacotes/arquivos, mas o perfil recusa essa identidade enquanto sua execução não
estiver implementada. A ordem de composição passa a ser núcleo → perfil → formato → alvo. Contrato válido não
dispensa os testes do adaptador: metadata e existência de script, sozinhas, não comprovam um deploy correto.

As tarefas #176–#180 completam a preparação e as Actions por alvo, o personalizado, Tsuru, os formatos por hashes
e o serviço AWS escolhido. O suporte nativo não é anunciado antes de implementação e teste. O serviço AWS e as
características do Tsuru real não são inferidos da palavra “Amazon” nem do domínio do painel.

## Consequências

### Positivas

- Um alvo novo é descoberto sem alteração de enum ou do núcleo.
- Os projetos VPS atuais e o perfil compilado conservam o comportamento.
- Reservas ficam visíveis sem passarem pela geração como integrações prontas.
- A atualização continua trocando só framework/camada gerada, sem scripts próprios do projeto.

### Negativas

- Metadados passam a fazer parte do contrato e precisam de teste, documentação e checksums.
- `aws` e `paas`, antes aceitos nominalmente, passam a ser recusados por não terem implementação.
- A arquitetura é entregue em etapas: o primeiro PR não é o deploy Tsuru nem a entrega universal concluída.

## Referências

- [Épico #174 e decisão do dono](https://github.com/BrunodosSantosVaz/big-bang/issues/174)
- [Contrato de deploy](../../esteira/perfis/deploy/README.md)
- [ADR-0013](ADR-0013-perfil-deploy.md), especificação §5.1/14.4; ARQ-07/09/11, DAD-02/03, SEG-15/18, OBS-04

## Composição de Actions (#176)

O gerador usa variáveis/segredos declarados no alvo, sem nomes de VPS no núcleo. Nomes reservados ao processo e à
esteira são recusados para impedir sobreposição de credenciais e identidade de artefato. O contrato de artefato
seleciona os scripts de construção e candidata. `deploy.runner` decide o acesso de rede dos jobs de publicação;
`deploy.preparar_rede` executa um script aprovado do projeto. Uma preparação falha antes de acionar o alvo.
A simulação não prepara rede nem autentica. Builds/testes permanecem no runner público e os portões humanos de
produção/rollback continuam no GitHub. Segredos só nos ambientes; ferramentas específicas podem usar o script
opcional `scripts/preparar.sh` do adaptador instalado.
