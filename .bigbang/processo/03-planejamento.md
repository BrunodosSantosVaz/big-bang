# 03 · Planejamento

Do pedido solto ao épico pronto para a sprint. Painel: **Planejamento** (veja [04-paineis.md](04-paineis.md)).

```
Ideia → Brainstorm → Backlog (decisão do dono) → Backlog Refinement → Validar protótipo (se houver) → Próxima sprint
```

## Passo a passo

| Passo | Quem | O que acontece | Coluna |
| --- | --- | --- | --- |
| 1. Ideia | Dono diz "Ideia: …" | A IA confere se já existe épico parecido e cria o épico (formulário *Épico*) com o problema em 1 a 3 frases | Brainstorm |
| 2. Decisão de implementar | **Dono** arrasta o cartão | Única coluna que o dono move à mão | Backlog |
| 3. Refinamento | Dono diz "vamos refinar o backlog" | A IA lista os épicos em *Backlog* e *Backlog Refinement*, pergunta a ordem e refina um por vez | Backlog Refinement |
| 4. Aprovação | **Dono** diz "aprovado" | A IA roda `bb decisao refinamento-aprovado` com a frase do dono | Validar protótipo ou Próxima sprint |
| 5. Protótipo | Dono diz "vamos montar o protótipo" | A IA monta o protótipo navegável em `docs/prototipos/<épico>/` | Validar protótipo |
| 6. Aprovação do protótipo | **Dono** diz "aprovado" | `bb decisao prototipo-aprovado`; o protótipo entra nos critérios | Próxima sprint |

## Como a IA refina um épico

Uma pergunta por vez, sempre propondo uma resposta para o dono aceitar ou corrigir:

1. Problema e objetivo, escopo dentro e fora.
2. As cinco perguntas do formulário: muda o artefato?; precisa de protótipo?; quem revisa os testes de aceite?; quem
   revisa os PRs?; depende de outro épico ainda não publicado?
3. Regras de negócio envolvidas (`RN-NNNN` existentes e novas). A IA nunca inventa regra: pergunta.
4. Critérios de aceite `CA-n`, no formato Dado/Quando/Então.
5. Análise de ameaças STRIDE, se o épico toca zona sensível.
6. Tarefas previstas, cada uma do tamanho de um PR, com `(depende de: k)` quando uma depende de outra. Tarefas que
   mexem nos mesmos arquivos ficam dependentes, para não conflitarem em paralelo.
7. Se o trabalho é crítico (dinheiro, dado pessoal, autenticação), a IA marca `revisao-humana`.

No fim, a IA mostra o resumo completo e pede a aprovação.

## Definition of Ready (épico pronto para a sprint)

O *Iniciar sprint* recusa o épico que não cumpre todos os itens (lendo labels e corpo da issue):

- [ ] Problema e objetivo claros
- [ ] Escopo dentro e fora
- [ ] Regras de negócio listadas
- [ ] Critérios de aceite `CA-n` em Dado/Quando/Então
- [ ] Tarefas previstas, cada uma do tamanho de um PR, com dependências marcadas
- [ ] As cinco perguntas do formulário respondidas
- [ ] STRIDE, se tocar zona sensível
- [ ] Protótipo aprovado (`prototipo-aprovado`), se `com-prototipo`
- [ ] Label `refinamento-aprovado`

## Protótipo

- Feito no padrão do `DESIGN.md` (só tokens e componentes de lá), navegável, em `docs/prototipos/<épico>/`.
- Ligado no corpo do épico.
- A IA itera com os comentários do dono até o "aprovado".
- Aprovado, o protótipo vira referência dos critérios de aceite das telas.

## O que a automação faz sozinha

Converte as respostas dos dropdowns do formulário em labels (`sem-release`, `com-prototipo`/`sem-prototipo`,
`testes-revisao-*`, `revisao-*`, `tem-dependencia`) ao abrir e ao editar o épico, e move o cartão quando as labels de
decisão aparecem.
