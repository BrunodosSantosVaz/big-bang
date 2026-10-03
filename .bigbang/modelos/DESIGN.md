# {{projeto.nome}} — Design

> Escrito na Fundação (F3). Só muda com decisão do dono registrada em ADR.
>
> **Regra para o front (`FE-01`): todo componente novo usa só os tokens e componentes daqui.** Cor, espaçamento e
> fonte literais no código são reprovados pelo lint.

## Identidade

- **Nome visual:**
- **Logo:** `docs/design/logo.svg` <!-- e as variações -->
- **Uso:** <!-- área de respiro, tamanho mínimo, fundo claro/escuro -->

## Paleta

Contraste verificado no nível **AA** (4,5:1 para texto normal; 3:1 para texto grande e componentes).

| Token | Valor | Uso | Contraste sobre o fundo |
| --- | --- | --- | --- |
| `--cor-fundo` | | | — |
| `--cor-texto` | | | |
| `--cor-primaria` | | | |
| `--cor-erro` | | | |
| `--cor-sucesso` | | | |
| `--cor-alerta` | | | |

## Tipografia

| Token | Família | Tamanho | Peso | Altura de linha |
| --- | --- | --- | --- | --- |
| `--fonte-titulo` | | | | |
| `--fonte-corpo` | | | | |

## Espaçamento, raio e sombra

| Token | Valor |
| --- | --- |
| `--espaco-1` … `--espaco-n` | |
| `--raio-padrao` | |
| `--sombra-padrao` | |

## Ícones

<!-- Biblioteca, tamanho padrão, quando usar ícone com e sem texto. Ícone sozinho sempre tem rótulo acessível. -->

## Componentes base

| Componente | Quando usar |
| --- | --- |
| Botão (primário, secundário, perigo) | |
| Campo de formulário | |
| Tabela / lista | |
| Modal de confirmação | Toda confirmação e todo aviso (nunca `alert()`/`confirm()`) |
| Aviso (toast) | |

## Padrões de tela

| Situação | Padrão |
| --- | --- |
| Lista | |
| Formulário | |
| Detalhe | |
| Vazio | |
| Erro | |
| Carregando | |
| Confirmação | Modal do design kit; **nunca** `alert()` ou `confirm()` |

## Responsividade

- Usável a partir de **360 px** de largura, sem rolagem horizontal da página.
- Área de toque de pelo menos **44×44** px.

## Acessibilidade

**WCAG 2.2 nível AA**: contraste, navegação por teclado, foco visível, rótulos em todos os campos, verificador
automático na CI.

## Formatos pt-BR

| Tipo | Formato |
| --- | --- |
| Data | `03/10/2026` |
| Hora | `14:05` (fuso do usuário) |
| Moeda | `R$ 1.234,56` |
| Número | `1.234,5` |

## Protótipo aprovado

<!-- Link para docs/prototipos/ e para a issue da Fundação F3. -->

## Histórico de mudanças

| Data | O que mudou | ADR |
| --- | --- | --- |
| | Versão inicial (Fundação F3) | — |
